/// PPTX parser — Microsoft PowerPoint dosyalarını parse eder.
///
/// PPTX formatı ZIP arşividir. `ppt/slides/slide{N}.xml` dosyalarından
/// metin çıkarır. Slide sıralamasını korur.
///
/// Yapı:
///   .pptx (ZIP)
///   ├── ppt/
///   │   ├── slides/
///   │   │   ├── slide1.xml
///   │   │   ├── slide2.xml
///   │   │   └── ...
///   │   └── ...
///   └── ...
use std::fs::File;
use std::io::Read;
use quick_xml::events::Event;
use quick_xml::Reader;

pub fn parse(file_path: &str) -> Result<String, String> {
    let file = File::open(file_path)
        .map_err(|e| format!("PPTX dosyası açılamadı: {}", e))?;

    let mut archive = zip::ZipArchive::new(file)
        .map_err(|e| format!("PPTX ZIP arşivi okunamadı: {}", e))?;

    // Slide dosyalarını bul ve sırala
    let mut slide_names: Vec<String> = Vec::new();
    for i in 0..archive.len() {
        if let Ok(entry) = archive.by_index(i) {
            let name = entry.name().to_string();
            if name.starts_with("ppt/slides/slide") && name.ends_with(".xml") {
                slide_names.push(name);
            }
        }
    }

    // Doğal sıralama: slide1, slide2, ..., slide10, slide11
    slide_names.sort_by(|a, b| {
        let num_a = extract_slide_number(a);
        let num_b = extract_slide_number(b);
        num_a.cmp(&num_b)
    });

    if slide_names.is_empty() {
        return Err("PPTX içinde slide bulunamadı".to_string());
    }

    let mut all_text = Vec::new();

    for (idx, slide_name) in slide_names.iter().enumerate() {
        let mut xml_content = String::new();
        {
            let mut slide_file = archive
                .by_name(slide_name)
                .map_err(|e| format!("Slide okunamadı ({}): {}", slide_name, e))?;
            slide_file
                .read_to_string(&mut xml_content)
                .map_err(|e| format!("Slide XML okunamadı: {}", e))?;
        }

        let slide_text = extract_text_from_slide_xml(&xml_content)?;
        if !slide_text.trim().is_empty() {
            all_text.push(format!("[Slide {}]\n{}", idx + 1, slide_text));
        }
    }

    if all_text.is_empty() {
        return Err("PPTX'ten metin çıkarılamadı".to_string());
    }

    Ok(all_text.join("\n\n"))
}

/// Slide numarasını dosya adından çıkarır.
/// "ppt/slides/slide12.xml" -> 12
fn extract_slide_number(name: &str) -> u32 {
    let stem = name
        .trim_start_matches("ppt/slides/slide")
        .trim_end_matches(".xml");
    stem.parse::<u32>().unwrap_or(0)
}

/// Slide XML'inden metin çıkarır.
///
/// PowerPoint'te metin `<a:t>` etiketleri içindedir.
/// Paragraflar `<a:p>` ile sarılıdır.
fn extract_text_from_slide_xml(xml: &str) -> Result<String, String> {
    let mut reader = Reader::from_str(xml);
    reader.config_mut().trim_text(false);

    let mut paragraphs: Vec<String> = Vec::new();
    let mut current_paragraph = String::new();
    let mut in_paragraph = false;
    let mut in_text = false;
    let mut buf = Vec::new();

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(ref e)) => {
                let name = e.name();
                let local = local_name(name.as_ref());
                match local {
                    "p" => {
                        in_paragraph = true;
                        current_paragraph.clear();
                    }
                    "t" => {
                        in_text = true;
                    }
                    _ => {}
                }
            }
            Ok(Event::Text(ref e)) => {
                if in_text && in_paragraph {
                    if let Ok(text) = e.unescape() {
                        current_paragraph.push_str(&text);
                    }
                }
            }
            Ok(Event::End(ref e)) => {
                let name = e.name();
                let local = local_name(name.as_ref());
                match local {
                    "p" => {
                        in_paragraph = false;
                        let trimmed = current_paragraph.trim().to_string();
                        if !trimmed.is_empty() {
                            paragraphs.push(trimmed);
                        }
                        current_paragraph.clear();
                    }
                    "t" => {
                        in_text = false;
                    }
                    _ => {}
                }
            }
            Ok(Event::Eof) => break,
            Err(e) => {
                return Err(format!("Slide XML parse hatası: {}", e));
            }
            _ => {}
        }
        buf.clear();
    }

    Ok(paragraphs.join("\n"))
}

/// XML tag adından namespace prefix'ini kaldırır.
fn local_name(name: &[u8]) -> &str {
    let full = std::str::from_utf8(name).unwrap_or("");
    if let Some(pos) = full.rfind(':') {
        &full[pos + 1..]
    } else {
        full
    }
}
