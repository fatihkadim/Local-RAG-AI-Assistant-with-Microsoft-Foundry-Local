/// CSV/TSV parser — Tablolu veri dosyalarını metin olarak parse eder.
///
/// Her satırı "Sütun: Değer" formatında düz metne dönüştürür.
/// Bu format, embedding modeline en iyi bağlamı sağlar çünkü
/// sütun başlıkları her satırda tekrarlanarak semantik anlam korunur.
///
/// Örnek çıktı:
/// ```
/// Satır 1:
///   Ad: Ahmet
///   Soyad: Yılmaz
///   Yaş: 30
///
/// Satır 2:
///   Ad: Ayşe
///   ...
/// ```
use std::fs::File;
use std::io::BufReader;

pub fn parse(file_path: &str, delimiter: u8) -> Result<String, String> {
    let file = File::open(file_path)
        .map_err(|e| format!("CSV/TSV dosyası açılamadı: {}", e))?;

    let reader = BufReader::new(file);
    let mut csv_reader = csv::ReaderBuilder::new()
        .delimiter(delimiter)
        .has_headers(true)
        .flexible(true)
        .from_reader(reader);

    // Başlıkları al
    let headers: Vec<String> = csv_reader
        .headers()
        .map_err(|e| format!("CSV başlıkları okunamadı: {}", e))?
        .iter()
        .map(|h| h.trim().to_string())
        .collect();

    if headers.is_empty() {
        return Err("CSV/TSV dosyası boş veya başlık satırı yok".to_string());
    }

    let mut output_parts: Vec<String> = Vec::new();
    let mut row_num = 0;

    for result in csv_reader.records() {
        match result {
            Ok(record) => {
                row_num += 1;
                let mut row_text = format!("Satır {}:", row_num);

                for (i, field) in record.iter().enumerate() {
                    let header = headers.get(i).map(|h| h.as_str()).unwrap_or("?");
                    let value = field.trim();
                    if !value.is_empty() {
                        row_text.push_str(&format!("\n  {}: {}", header, value));
                    }
                }

                if row_text.contains('\n') {
                    // En az bir değer var
                    output_parts.push(row_text);
                }
            }
            Err(e) => {
                // Bozuk satırı atla, devam et
                eprintln!("CSV satır {} parse hatası: {}", row_num + 1, e);
                continue;
            }
        }
    }

    if output_parts.is_empty() {
        // Başlıkları hiç veri olmasa bile döndür
        return Ok(format!("Sütunlar: {}", headers.join(", ")));
    }

    // Başlık bilgisini de ekle
    let header_line = format!("Tablo Sütunları: {}", headers.join(", "));
    let mut result = vec![header_line];
    result.extend(output_parts);

    Ok(result.join("\n\n"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    #[test]
    fn test_parse_csv() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test.csv");
        let mut file = std::fs::File::create(&path).unwrap();
        writeln!(file, "Ad,Soyad,Yaş").unwrap();
        writeln!(file, "Ahmet,Yılmaz,30").unwrap();
        writeln!(file, "Ayşe,Kaya,25").unwrap();

        let result = parse(path.to_str().unwrap(), b',').unwrap();
        assert!(result.contains("Ad: Ahmet"));
        assert!(result.contains("Soyad: Yılmaz"));
        assert!(result.contains("Yaş: 30"));
        assert!(result.contains("Satır 1:"));
        assert!(result.contains("Satır 2:"));
    }

    #[test]
    fn test_parse_tsv() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test.tsv");
        let mut file = std::fs::File::create(&path).unwrap();
        writeln!(file, "İsim\tŞehir").unwrap();
        writeln!(file, "Ali\tİstanbul").unwrap();

        let result = parse(path.to_str().unwrap(), b'\t').unwrap();
        assert!(result.contains("İsim: Ali"));
        assert!(result.contains("Şehir: İstanbul"));
    }
}
