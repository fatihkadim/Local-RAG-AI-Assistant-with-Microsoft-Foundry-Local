/// XLSX/XLS parser — Excel dosyalarını parse eder.
///
/// `calamine` crate'i ile Excel dosyalarını okur.
/// Her sheet'i ayrı bölüm olarak, her satırı sütun başlıklarıyla
/// birlikte düz metne dönüştürür.
use calamine::{open_workbook_auto, Reader, Data};

pub fn parse(file_path: &str) -> Result<String, String> {
    let mut workbook = open_workbook_auto(file_path)
        .map_err(|e| format!("Excel dosyası açılamadı: {}", e))?;

    let sheet_names: Vec<String> = workbook.sheet_names().to_vec();

    if sheet_names.is_empty() {
        return Err("Excel dosyasında sheet bulunamadı".to_string());
    }

    let mut all_parts: Vec<String> = Vec::new();

    for sheet_name in &sheet_names {
        let range = workbook
            .worksheet_range(sheet_name)
            .map_err(|e| format!("Sheet '{}' okunamadı: {}", sheet_name, e))?;

        let rows: Vec<Vec<String>> = range
            .rows()
            .map(|row| {
                row.iter()
                    .map(|cell| cell_to_string(cell))
                    .collect()
            })
            .collect();

        if rows.is_empty() {
            continue;
        }

        let mut sheet_text = Vec::new();

        // Sheet başlığı (birden fazla sheet varsa)
        if sheet_names.len() > 1 {
            sheet_text.push(format!("[Sheet: {}]", sheet_name));
        }

        // İlk satır başlık kabul edilir
        let headers = &rows[0];
        let header_line = format!("Sütunlar: {}", headers.join(", "));
        sheet_text.push(header_line);

        // Veri satırları
        for (row_idx, row) in rows.iter().skip(1).enumerate() {
            let mut row_text = format!("Satır {}:", row_idx + 1);
            let mut has_value = false;

            for (col_idx, value) in row.iter().enumerate() {
                if !value.is_empty() {
                    let header = headers
                        .get(col_idx)
                        .map(|h| h.as_str())
                        .unwrap_or("?");
                    row_text.push_str(&format!("\n  {}: {}", header, value));
                    has_value = true;
                }
            }

            if has_value {
                sheet_text.push(row_text);
            }
        }

        if sheet_text.len() > 1 {
            // Başlık + en az bir satır
            all_parts.push(sheet_text.join("\n\n"));
        }
    }

    if all_parts.is_empty() {
        return Err("Excel dosyasından metin çıkarılamadı".to_string());
    }

    Ok(all_parts.join("\n\n---\n\n"))
}

/// Calamine Data hücresini String'e dönüştürür.
fn cell_to_string(cell: &Data) -> String {
    match cell {
        Data::Empty => String::new(),
        Data::String(s) => s.trim().to_string(),
        Data::Int(i) => i.to_string(),
        Data::Float(f) => {
            // Tam sayı ise kesirli gösterme
            if *f == (*f as i64) as f64 {
                format!("{}", *f as i64)
            } else {
                format!("{:.4}", f)
            }
        }
        Data::Bool(b) => if *b { "Evet" } else { "Hayır" }.to_string(),
        Data::DateTime(dt) => format!("{}", dt),
        Data::DateTimeIso(s) => s.to_string(),
        Data::DurationIso(s) => s.to_string(),
        Data::Error(e) => format!("[Hata: {:?}]", e),
    }
}
