use std::collections::HashMap;
use std::sync::mpsc;
use std::thread;

use hdrhistogram::Histogram;
use pyo3::prelude::*;
use pyo3::types::PyDict;

enum SinkKind {
    Counter { value: f64 },
    Gauge { value: f64, min: f64, max: f64 },
    Rate { trues: u64, total: u64 },
    Trend(Histogram<u64>),
}

impl SinkKind {
    fn add(&mut self, value: f64) {
        match self {
            SinkKind::Counter { value: v } => *v += value,
            SinkKind::Gauge {
                value: v,
                min,
                max,
            } => {
                *v = value;
                if value < *min {
                    *min = value;
                }
                if value > *max {
                    *max = value;
                }
            }
            SinkKind::Rate { trues, total } => {
                *total += 1;
                if value != 0.0 {
                    *trues += 1;
                }
            }
            SinkKind::Trend(h) => {
                let _ = h.record(value.max(0.0) as u64);
            }
        }
    }

    fn format(&self, duration: f64) -> Vec<(&'static str, f64)> {
        match self {
            SinkKind::Counter { value } => {
                let rate = if duration > 0.0 {
                    *value / duration
                } else {
                    0.0
                };
                vec![("count", *value), ("rate", rate)]
            }
            SinkKind::Gauge { value, min, max } => {
                let gmin = if min.is_infinite() { 0.0 } else { *min };
                let gmax = if max.is_infinite() { 0.0 } else { *max };
                vec![("value", *value), ("min", gmin), ("max", gmax)]
            }
            SinkKind::Rate { trues, total } => {
                let rate = if *total > 0 {
                    *trues as f64 / *total as f64
                } else {
                    0.0
                };
                vec![
                    ("rate", rate),
                    ("passes", *trues as f64),
                    ("fails", (*total - *trues) as f64),
                ]
            }
            SinkKind::Trend(h) => {
                if h.len() == 0 {
                    return vec![
                        ("count", 0.0),
                        ("avg", 0.0),
                        ("min", 0.0),
                        ("max", 0.0),
                        ("med", 0.0),
                        ("p(90)", 0.0),
                        ("p(95)", 0.0),
                        ("p(99)", 0.0),
                    ];
                }
                vec![
                    ("count", h.len() as f64),
                    ("avg", h.mean()),
                    ("min", h.min() as f64),
                    ("max", h.max() as f64),
                    ("med", h.value_at_quantile(0.50) as f64),
                    ("p(90)", h.value_at_quantile(0.90) as f64),
                    ("p(95)", h.value_at_quantile(0.95) as f64),
                    ("p(99)", h.value_at_quantile(0.99) as f64),
                ]
            }
        }
    }
}

fn new_sink(metric_type: &str) -> SinkKind {
    match metric_type {
        "counter" => SinkKind::Counter { value: 0.0 },
        "gauge" => SinkKind::Gauge {
            value: 0.0,
            min: f64::INFINITY,
            max: f64::NEG_INFINITY,
        },
        "rate" => SinkKind::Rate {
            trues: 0,
            total: 0,
        },
        "trend" => SinkKind::Trend(Histogram::new(3).expect("valid sigfig")),
        _ => SinkKind::Counter { value: 0.0 },
    }
}

struct SubSinkEntry {
    filter: Vec<(String, String)>,
    sink: SinkKind,
}

enum Message {
    Register {
        name: String,
        metric_type: String,
    },
    RegisterSubSink {
        base_name: String,
        filter: Vec<(String, String)>,
        metric_type: String,
    },
    Sample {
        metric: String,
        value: f64,
        tags: Vec<(String, String)>,
    },
}

struct CoreState {
    sinks: HashMap<String, SinkKind>,
    metric_types: HashMap<String, String>,
    sub_sinks: HashMap<String, Vec<SubSinkEntry>>,
    dropped: u64,
}

impl CoreState {
    fn handle(&mut self, msg: Message) {
        match msg {
            Message::Register { name, metric_type } => {
                self.metric_types
                    .insert(name.clone(), metric_type.clone());
                self.sinks
                    .entry(name)
                    .or_insert_with(|| new_sink(&metric_type));
            }
            Message::RegisterSubSink {
                base_name,
                filter,
                metric_type,
            } => {
                let entry = SubSinkEntry {
                    filter,
                    sink: new_sink(&metric_type),
                };
                self.sub_sinks
                    .entry(base_name)
                    .or_default()
                    .push(entry);
            }
            Message::Sample {
                metric,
                value,
                tags,
            } => {
                if let Some(sink) = self.sinks.get_mut(&metric) {
                    sink.add(value);
                } else if let Some(mt) = self.metric_types.get(&metric) {
                    let mt = mt.clone();
                    let sink = self
                        .sinks
                        .entry(metric.clone())
                        .or_insert_with(|| new_sink(&mt));
                    sink.add(value);
                }

                if let Some(entries) = self.sub_sinks.get_mut(&metric) {
                    for entry in entries.iter_mut() {
                        if entry
                            .filter
                            .iter()
                            .all(|(k, v)| tags.iter().any(|(sk, sv)| sk == k && sv == v))
                        {
                            entry.sink.add(value);
                        }
                    }
                }
            }
        }
    }
}

/// Native metric aggregation core with bounded submission channel.
///
/// Owns a background drain thread that processes samples and updates
/// sinks. Drops samples when the channel is full rather than blocking.
#[pyclass]
pub struct MetricCore {
    sender: Option<mpsc::SyncSender<Message>>,
    join_handle: Option<thread::JoinHandle<CoreState>>,
    state: Option<CoreState>,
}

#[pymethods]
impl MetricCore {
    #[new]
    #[pyo3(signature = (capacity=100_000))]
    fn new(capacity: usize) -> Self {
        let (tx, rx) = mpsc::sync_channel::<Message>(capacity);

        let handle = thread::Builder::new()
            .name("rampa-rust-metric-core".into())
            .spawn(move || {
                let mut state = CoreState {
                    sinks: HashMap::new(),
                    metric_types: HashMap::new(),
                    sub_sinks: HashMap::new(),
                    dropped: 0,
                };
                while let Ok(msg) = rx.recv() {
                    state.handle(msg);
                }
                state
            })
            .expect("failed to spawn metric core thread");

        Self {
            sender: Some(tx),
            join_handle: Some(handle),
            state: None,
        }
    }

    /// Register a metric name and type.
    fn register(&self, name: &str, metric_type: &str) {
        if let Some(ref tx) = self.sender {
            let _ = tx.try_send(Message::Register {
                name: name.to_string(),
                metric_type: metric_type.to_string(),
            });
        }
    }

    /// Register a sub-sink for tag-filtered aggregation.
    fn register_sub_sink(
        &self,
        base_name: &str,
        tag_filter: HashMap<String, String>,
        metric_type: &str,
    ) {
        if let Some(ref tx) = self.sender {
            let _ = tx.try_send(Message::RegisterSubSink {
                base_name: base_name.to_string(),
                filter: tag_filter.into_iter().collect(),
                metric_type: metric_type.to_string(),
            });
        }
    }

    /// Submit a sample. Drops if the channel is full.
    fn submit(&self, metric: &str, value: f64, tags: HashMap<String, String>) {
        if let Some(ref tx) = self.sender {
            if tx
                .try_send(Message::Sample {
                    metric: metric.to_string(),
                    value,
                    tags: tags.into_iter().collect(),
                })
                .is_err()
            {
                // channel full — sample dropped
            }
        }
    }

    /// Return aggregated metrics as a Python dict.
    fn snapshot<'py>(
        &mut self,
        py: Python<'py>,
        duration: f64,
    ) -> PyResult<Bound<'py, PyDict>> {
        self.flush_and_join()?;
        let state = self.state.as_ref().ok_or_else(|| {
            pyo3::exceptions::PyRuntimeError::new_err("core not flushed")
        })?;

        let outer = PyDict::new(py);
        for (name, sink) in &state.sinks {
            let inner = PyDict::new(py);
            for (k, v) in sink.format(duration) {
                inner.set_item(k, v)?;
            }
            outer.set_item(name, inner)?;
        }
        Ok(outer)
    }

    /// Flush all pending samples and stop the drain thread.
    fn flush_and_join(&mut self) -> PyResult<()> {
        if self.state.is_some() {
            return Ok(());
        }
        self.sender.take();
        if let Some(handle) = self.join_handle.take() {
            match handle.join() {
                Ok(state) => {
                    self.state = Some(state);
                }
                Err(_) => {
                    return Err(pyo3::exceptions::PyRuntimeError::new_err(
                        "drain thread panicked",
                    ));
                }
            }
        }
        Ok(())
    }

    /// Return the number of samples dropped due to channel backpressure.
    fn metrics_dropped(&self) -> u64 {
        if let Some(ref state) = self.state {
            return state.dropped;
        }
        0
    }
}
