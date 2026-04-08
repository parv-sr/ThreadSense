use pyo3::prelude::*;

///Every time you change Rust code, just re-run maturin develop --release 


/// A Python module implemented in Rust.
#[pymodule]
mod wpt {
    use pyo3::prelude::*;

    /// Formats the sum of two numbers as string.
    #[pyfunction]
    fn sum_as_string(a: usize, b: usize) -> PyResult<String> {
        Ok((a + b).to_string())
    }
}
