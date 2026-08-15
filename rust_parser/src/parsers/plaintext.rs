/// Düz metin dosyası parser'ı (.txt, .md, .rst).
///
/// UTF-8 ile okur, encoding hatalarını tolere eder (lossy).
use std::fs;

pub fn parse(file_path: &str) -> Result<String, String> {
    // Önce UTF-8 olarak oku
    match fs::read_to_string(file_path) {
        Ok(content) => Ok(content),
        Err(_) => {
            // UTF-8 değilse, lossy olarak oku
            let bytes = fs::read(file_path)
                .map_err(|e| format!("Dosya okunamadı: {}", e))?;
            Ok(String::from_utf8_lossy(&bytes).to_string())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    #[test]
    fn test_parse_txt() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test.txt");
        let mut file = fs::File::create(&path).unwrap();
        writeln!(file, "Merhaba dünya!").unwrap();
        writeln!(file, "Bu bir test dosyasıdır.").unwrap();

        let result = parse(path.to_str().unwrap()).unwrap();
        assert!(result.contains("Merhaba dünya!"));
        assert!(result.contains("test dosyasıdır"));
    }

    #[test]
    fn test_parse_nonexistent() {
        let result = parse("/nonexistent/file.txt");
        assert!(result.is_err());
    }
}
