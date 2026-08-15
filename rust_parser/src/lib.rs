/// High-performance document parser for Local RAG AI Assistant.
///
/// Bu modül, çeşitli dosya formatlarını (DOCX, PPTX, HTML, CSV, XLSX, EPUB,
/// JSON, TXT, MD) parse ederek düz metin çıktısı üretir. PyO3 ile Python'a
/// expose edilir ve mevcut ingestion pipeline'a entegre olur.
use pyo3::prelude::*;
use pyo3::exceptions::PyValueError;

mod parsers;
mod cleaner;

/// Bir dosyayı parse ederek ParseResult döndürür.
///
/// # Arguments
/// * `file_path` - Dosyanın mutlak yolu
///
/// # Returns
/// * `ParseResult` - Dosya adı, çıkarılan metin, format bilgisi ve metadata
///
/// # Errors
/// * Desteklenmeyen format
/// * Dosya okunamıyorsa
/// * Parse hatası
#[pyfunction]
fn parse_document(file_path: &str) -> PyResult<ParseResult> {
    let path = std::path::Path::new(file_path);

    if !path.exists() {
        return Err(PyValueError::new_err(format!(
            "Dosya bulunamadı: {}",
            file_path
        )));
    }

    let extension = path
        .extension()
        .and_then(|e| e.to_str())
        .map(|e| e.to_lowercase())
        .unwrap_or_default();

    let filename = path
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("unknown")
        .to_string();

    let result = match extension.as_str() {
        "txt" | "md" | "rst" => parsers::plaintext::parse(file_path),
        "docx" => parsers::docx::parse(file_path),
        "pptx" => parsers::pptx::parse(file_path),
        "html" | "htm" => parsers::html::parse(file_path),
        "csv" => parsers::csv_tsv::parse(file_path, b','),
        "tsv" => parsers::csv_tsv::parse(file_path, b'\t'),
        "xlsx" | "xls" => parsers::xlsx::parse(file_path),
        "epub" => parsers::epub::parse(file_path),
        "json" => parsers::json_parser::parse(file_path),
        "jsonl" => parsers::json_parser::parse_jsonl(file_path),
        _ => {
            return Err(PyValueError::new_err(format!(
                "Desteklenmeyen dosya formatı: .{}",
                extension
            )));
        }
    };

    match result {
        Ok(content) => {
            let cleaned = cleaner::clean_text(&content);
            if cleaned.trim().is_empty() {
                return Err(PyValueError::new_err(format!(
                    "Dosyadan metin çıkarılamadı (boş içerik): {}",
                    file_path
                )));
            }
            Ok(ParseResult {
                filename,
                content: cleaned,
                format: extension,
                char_count: content.len(),
            })
        }
        Err(e) => Err(PyValueError::new_err(format!(
            "Dosya parse hatası ({}): {}",
            file_path, e
        ))),
    }
}

/// Birden fazla dosyayı paralel olarak parse eder.
///
/// `rayon` ile thread pool kullanarak tüm CPU core'larını kullanır.
/// Parse edilemeyen dosyalar hata listesine eklenir, diğerleri etkilenmez.
#[pyfunction]
fn parse_documents_batch(file_paths: Vec<String>) -> PyResult<BatchParseResult> {
    use rayon::prelude::*;

    let results: Vec<_> = file_paths
        .par_iter()
        .map(|path| {
            match parse_document_internal(path) {
                Ok(result) => BatchItem::Success(result),
                Err(e) => BatchItem::Error {
                    file_path: path.clone(),
                    error: e,
                },
            }
        })
        .collect();

    let mut successes = Vec::new();
    let mut errors = Vec::new();

    for item in results {
        match item {
            BatchItem::Success(r) => successes.push(r),
            BatchItem::Error { file_path, error } => {
                errors.push(ParseError { file_path, error });
            }
        }
    }

    Ok(BatchParseResult {
        results: successes,
        errors,
        total: file_paths.len(),
    })
}

/// Desteklenen dosya uzantılarını döndürür.
#[pyfunction]
fn supported_extensions() -> Vec<String> {
    vec![
        ".txt", ".md", ".rst", ".docx", ".pptx", ".html", ".htm",
        ".csv", ".tsv", ".xlsx", ".xls", ".epub", ".json", ".jsonl",
    ]
    .into_iter()
    .map(String::from)
    .collect()
}

// ── İç fonksiyonlar ──────────────────────────────────────────

enum BatchItem {
    Success(ParseResult),
    Error { file_path: String, error: String },
}

fn parse_document_internal(file_path: &str) -> Result<ParseResult, String> {
    let path = std::path::Path::new(file_path);

    if !path.exists() {
        return Err(format!("Dosya bulunamadı: {}", file_path));
    }

    let extension = path
        .extension()
        .and_then(|e| e.to_str())
        .map(|e| e.to_lowercase())
        .unwrap_or_default();

    let filename = path
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("unknown")
        .to_string();

    let content = match extension.as_str() {
        "txt" | "md" | "rst" => parsers::plaintext::parse(file_path),
        "docx" => parsers::docx::parse(file_path),
        "pptx" => parsers::pptx::parse(file_path),
        "html" | "htm" => parsers::html::parse(file_path),
        "csv" => parsers::csv_tsv::parse(file_path, b','),
        "tsv" => parsers::csv_tsv::parse(file_path, b'\t'),
        "xlsx" | "xls" => parsers::xlsx::parse(file_path),
        "epub" => parsers::epub::parse(file_path),
        "json" => parsers::json_parser::parse(file_path),
        "jsonl" => parsers::json_parser::parse_jsonl(file_path),
        _ => return Err(format!("Desteklenmeyen format: .{}", extension)),
    }?;

    let cleaned = cleaner::clean_text(&content);
    if cleaned.trim().is_empty() {
        return Err(format!("Boş içerik: {}", file_path));
    }

    Ok(ParseResult {
        filename,
        content: cleaned.clone(),
        format: extension,
        char_count: cleaned.len(),
    })
}

// ── Python Sınıfları ─────────────────────────────────────────

/// Tek bir dosyanın parse sonucu.
#[pyclass]
#[derive(Clone)]
struct ParseResult {
    #[pyo3(get)]
    filename: String,
    #[pyo3(get)]
    content: String,
    #[pyo3(get)]
    format: String,
    #[pyo3(get)]
    char_count: usize,
}

#[pymethods]
impl ParseResult {
    fn __repr__(&self) -> String {
        format!(
            "ParseResult(filename='{}', format='{}', chars={})",
            self.filename, self.format, self.char_count
        )
    }
}

/// Toplu parse hata bilgisi.
#[pyclass]
#[derive(Clone)]
struct ParseError {
    #[pyo3(get)]
    file_path: String,
    #[pyo3(get)]
    error: String,
}

/// Toplu parse sonucu.
#[pyclass]
struct BatchParseResult {
    #[pyo3(get)]
    results: Vec<ParseResult>,
    #[pyo3(get)]
    errors: Vec<ParseError>,
    #[pyo3(get)]
    total: usize,
}

#[pymethods]
impl BatchParseResult {
    fn __repr__(&self) -> String {
        format!(
            "BatchParseResult(success={}, errors={}, total={})",
            self.results.len(),
            self.errors.len(),
            self.total
        )
    }
}

// ── PyO3 Modül Tanımı ────────────────────────────────────────

/// Python modülü: rust_parser
#[pymodule]
fn rust_parser(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_document, m)?)?;
    m.add_function(wrap_pyfunction!(parse_documents_batch, m)?)?;
    m.add_function(wrap_pyfunction!(supported_extensions, m)?)?;
    m.add_class::<ParseResult>()?;
    m.add_class::<ParseError>()?;
    m.add_class::<BatchParseResult>()?;
    Ok(())
}
