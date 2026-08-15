/// DOCX parser — Microsoft Word dosyalarını parse eder.
///
/// DOCX formatı bir ZIP arşividir. İçindeki `word/document.xml` dosyasından
/// paragraf metinlerini çıkarır. Paragraf sıralamasını korur.
///
/// Yapı:
///   .docx (ZIP)
///   ├── word/
///   │   ├── document.xml    ← Ana metin burada
///   │   ├── styles.xml
///   │   └── ...
///   ├── [Content_Types].xml
///   └── ...
use std::fs::File;
use std::io::Read;
use quick_xml::events::Event;
use quick_xml::Reader;

pub fn parse(file_path: &str) -> Result<String, String> {
    let file = File::open(file_path)
        .map_err(|e| format!("DOCX dosyası açılamadı: {}", e))?;

    let mut archive = zip::ZipArchive::new(file)
        .map_err(|e| format!("DOCX ZIP arşivi okunamadı (geçerli bir .docx dosyası mı?): {}", e))?;

    // word/document.xml'i bul ve oku
    let mut xml_content = String::new();
    {
        let mut doc_file = archive
            .by_name("word/document.xml")
            .map_err(|_| "DOCX içinde word/document.xml bulunamadı".to_string())?;
        doc_file
            .read_to_string(&mut xml_content)
            .map_err(|e| format!("document.xml okunamadı: {}", e))?;
    }

    // XML'den paragraf metinlerini çıkar
    extract_text_from_docx_xml(&xml_content)
}

/// DOCX XML'inden paragraf metinlerini çıkarır.
///
/// OOXML yapısında metin `<w:t>` etiketleri içindedir.
/// Paragraflar `<w:p>` ile sarılıdır.
/// Tab karakterleri `<w:tab/>` ile temsil edilir.
fn extract_text_from_docx_xml(xml: &str) -> Result<String, String> {
    let mut reader = Reader::from_str(xml);
    reader.config_mut().trim_text(false);

    let mut paragraphs: Vec<String> = Vec::new();
    let mut current_paragraph = String::new();
    let mut in_paragraph = false;
    let mut in_text = false;
    let mut depth = 0;
    let mut buf = Vec::new();

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(ref e)) => {
                let name = e.name();
                let local = local_name(name.as_ref());
                match local {
                    "p" => {
                        in_paragraph = true;
                        depth += 1;
                        current_paragraph.clear();
                    }
                    "t" => {
                        in_text = true;
                    }
                    _ => {}
                }
            }
            Ok(Event::Empty(ref e)) => {
                let name = e.name();
                let local = local_name(name.as_ref());
                match local {
                    "tab" => {
                        if in_paragraph {
                            current_paragraph.push('\t');
                        }
                    }
                    "br" => {
                        if in_paragraph {
                            current_paragraph.push('\n');
                        }
                    }
                    _ => {}
                }
            }
            Ok(Event::Text(ref e)) => {
                if in_text && in_paragraph {
                    let text = e.unescape()
                        .map_err(|err| format!("XML text unescape hatası: {}", err))?;
                    current_paragraph.push_str(&text);
                }
            }
            Ok(Event::End(ref e)) => {
                let name = e.name();
                let local = local_name(name.as_ref());
                match local {
                    "p" => {
                        depth -= 1;
                        if depth <= 0 {
                            in_paragraph = false;
                            let trimmed = current_paragraph.trim().to_string();
                            if !trimmed.is_empty() {
                                paragraphs.push(trimmed);
                            }
                            current_paragraph.clear();
                        }
                    }
                    "t" => {
                        in_text = false;
                    }
                    _ => {}
                }
            }
            Ok(Event::Eof) => break,
            Err(e) => {
                return Err(format!("XML parse hatası: {}", e));
            }
            _ => {}
        }
        buf.clear();
    }

    Ok(paragraphs.join("\n\n"))
}

/// XML tag adından namespace prefix'ini kaldırır.
/// Örn: "w:p" -> "p", "w:t" -> "t"
fn local_name(name: &[u8]) -> &str {
    let full = std::str::from_utf8(name).unwrap_or("");
    if let Some(pos) = full.rfind(':') {
        &full[pos + 1..]
    } else {
        full
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_text_simple() {
        let xml = r#"<?xml version="1.0" encoding="UTF-8"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body>
                <w:p>
                    <w:r><w:t>Merhaba dünya!</w:t></w:r>
                </w:p>
                <w:p>
                    <w:r><w:t>İkinci paragraf.</w:t></w:r>
                </w:p>
            </w:body>
        </w:document>"#;

        let result = extract_text_from_docx_xml(xml).unwrap();
        assert!(result.contains("Merhaba dünya!"));
        assert!(result.contains("İkinci paragraf."));
    }

    #[test]
    fn test_extract_empty_paragraphs_skipped() {
        let xml = r#"<?xml version="1.0" encoding="UTF-8"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body>
                <w:p></w:p>
                <w:p><w:r><w:t>Metin</w:t></w:r></w:p>
                <w:p></w:p>
            </w:body>
        </w:document>"#;

        let result = extract_text_from_docx_xml(xml).unwrap();
        assert_eq!(result.trim(), "Metin");
    }
}
