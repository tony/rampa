use hdrhistogram::Histogram;
use pyo3::prelude::*;

/// HDR histogram for memory-efficient trend aggregation.
///
/// Fixed ~20KB memory regardless of sample count. O(1) insert, O(1)
/// percentile queries. Replaces TrendSink's list[float] + sort approach
/// which is O(n) memory and O(n log n) per snapshot.
///
/// Values are recorded as integers (microseconds for time metrics).
/// The Python layer handles float-to-int conversion.
#[pyclass]
pub struct HdrHistogram {
    inner: Histogram<u64>,
}

#[pymethods]
impl HdrHistogram {
    /// Create a new histogram with the given significant figures.
    ///
    /// Parameters:
    ///     sigfig: Significant figures of precision (1-5). Default 3
    ///         gives 0.1% error. Higher values use more memory.
    #[new]
    #[pyo3(signature = (sigfig=3))]
    fn new(sigfig: u8) -> PyResult<Self> {
        let inner = Histogram::new(sigfig)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        Ok(Self { inner })
    }

    /// Record a single value.
    fn record(&mut self, value: u64) -> PyResult<()> {
        self.inner
            .record(value)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    /// Record a value with a count (bulk insert).
    fn record_n(&mut self, value: u64, count: u64) -> PyResult<()> {
        self.inner
            .record_n(value, count)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    /// Return the value at a given percentile (0.0 - 100.0).
    fn percentile(&self, p: f64) -> u64 {
        self.inner.value_at_quantile(p / 100.0)
    }

    /// Return the arithmetic mean.
    fn mean(&self) -> f64 {
        self.inner.mean()
    }

    /// Return the minimum recorded value.
    fn min(&self) -> u64 {
        self.inner.min()
    }

    /// Return the maximum recorded value.
    fn max(&self) -> u64 {
        self.inner.max()
    }

    /// Return the total number of recorded values.
    fn count(&self) -> u64 {
        self.inner.len()
    }

    /// Return the standard deviation.
    fn stdev(&self) -> f64 {
        self.inner.stdev()
    }

    /// Reset the histogram, discarding all recorded values.
    fn reset(&mut self) {
        self.inner.reset();
    }

    /// Return all standard stats in one call (avoids repeated Python→Rust crossings).
    ///
    /// Returns (count, mean, min, max, median, p90, p95, p99) as a tuple.
    fn format_stats(&self) -> (u64, f64, u64, u64, u64, u64, u64, u64) {
        (
            self.inner.len(),
            self.inner.mean(),
            self.inner.min(),
            self.inner.max(),
            self.inner.value_at_quantile(0.50),
            self.inner.value_at_quantile(0.90),
            self.inner.value_at_quantile(0.95),
            self.inner.value_at_quantile(0.99),
        )
    }
}
