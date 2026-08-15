/// Format-specific parser modülleri.
///
/// Her parser aynı interface'i kullanır:
///   fn parse(file_path: &str) -> Result<String, String>
///
/// Dosyayı okur ve düz metin (plain text) olarak döndürür.
pub mod plaintext;
pub mod docx;
pub mod pptx;
pub mod html;
pub mod csv_tsv;
pub mod xlsx;
pub mod epub;
pub mod json_parser;
