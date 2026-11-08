use pyo3::prelude::*;

mod histogram;
mod metric_core;
mod rate_controller;

/// Native acceleration for rampa.
///
/// Provides HDR histogram, rate controllers, and metric core.
/// Pure-Python fallback exists — this module is optional.
#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<histogram::HdrHistogram>()?;
    m.add_class::<metric_core::MetricCore>()?;
    m.add_class::<rate_controller::RateController>()?;
    m.add_class::<rate_controller::RampingRateController>()?;
    m.add_function(wrap_pyfunction!(rust_info, m)?)?;
    Ok(())
}

/// Return Rust build metadata for diagnostics.
#[pyfunction]
fn rust_info() -> String {
    format!("rampa-core {}", env!("CARGO_PKG_VERSION"))
}
