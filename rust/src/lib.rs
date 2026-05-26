use pyo3::prelude::*;

mod histogram;

/// Native acceleration for rampa.
///
/// Provides HDR histogram for memory-efficient trend aggregation.
/// Pure-Python fallback exists — this module is optional.
#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<histogram::HdrHistogram>()?;
    m.add_function(wrap_pyfunction!(rust_info, m)?)?;
    Ok(())
}

/// Return Rust build metadata for diagnostics.
#[pyfunction]
fn rust_info() -> String {
    format!("rampa-core {}", env!("CARGO_PKG_VERSION"))
}
