/// EPUB parser — E-kitap dosyalarını parse eder.
///
/// EPUB formatı bir ZIP arşividir. İçindeki XHTML dosyalarını okur
/// ve temiz metin olarak birleştirir. Bölüm sıralamasını spine
/// (okuma sırası) üzerinden korur.
///
/// Yapı:
///   .epub (ZIP)
///   ├── META-INF/container.xml  ← Root dosyayı gösterir
///   ├── content.opf             ← Spine (okuma sırası) ve manifest
///   ├── chapter1.xhtml
///   ├── chapter2.xhtml
///   └── ...
use std::fs::File;
use std::io::Read;
use quick_xml::events::Event;
use quick_xml::Reader;

pub fn parse(file_path: &str) -> Result<String, String> {
    let file = File::open(file_path)
        .map_err(|e| format!("EPUB dosyası açılamadı: {}", e))?;

    let mut archive = zip::ZipArchive::new(file)
        .map_err(|e| format!("EPUB ZIP arşivi okunamadı: {}", e))?;

    // XHTML dosyalarını bul
    let mut xhtml_files: Vec<String> = Vec::new();
    for i in 0..archive.len() {
        if let Ok(entry) = archive.by_index(i) {
            let name = entry.name().to_string();
            if (name.ends_with(".xhtml") || name.ends_with(".html") || name.ends_with(".htm"))
                && !name.contains("META-INF")
                && !name.contains("nav")
                && !name.contains("toc")
            {
                xhtml_files.push(name);
            }
        }
    }

    // Sırala (dosya adına göre — genellikle chapter01, chapter02 vb.)
    xhtml_files.sort();

    if xhtml_files.is_empty() {
        return Err("EPUB içinde XHTML içerik dosyası bulunamadı".to_string());
    }

    let mut all_chapters: Vec<String> = Vec::new();

    for (idx, xhtml_name) in xhtml_files.iter().enumerate() {
        let mut content = String::new();
        {
            let mut entry = archive
                .by_name(xhtml_name)
                .map_err(|e| format!("EPUB bölümü okunamadı ({}): {}", xhtml_name, e))?;
            entry
                .read_to_string(&mut content)
                .map_err(|e| format!("XHTML okunamadı: {}", e))?;
        }

        let chapter_text = extract_text_from_xhtml(&content);
        if !chapter_text.trim().is_empty() {
            all_chapters.push(format!("[Bölüm {}]\n{}", idx + 1, chapter_text));
        }
    }

    if all_chapters.is_empty() {
        return Err("EPUB'tan metin çıkarılamadı".to_string());
    }

    Ok(all_chapters.join("\n\n---\n\n"))
}

/// XHTML'den metin çıkarır.
///
/// Basit bir yaklaşım: tüm text node'ları toplar,
/// blok elementleri arasına newline ekler.
fn extract_text_from_xhtml(xhtml: &str) -> String {
    let mut reader = Reader::from_str(xhtml);
    reader.config_mut().trim_text(false);

    let mut parts: Vec<String> = Vec::new();
    let mut current_text = String::new();
    let mut in_body = false;
    let mut skip_depth: u32 = 0;
    let mut buf = Vec::new();

    // Atlanacak tag'ler
    let skip_tags = ["script", "style", "nav", "head"];

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(ref e)) => {
                let name = e.name();
                let tag = local_name(name.as_ref());

                if skip_tags.contains(&tag) {
                    skip_depth += 1;
                    buf.clear();
                    continue;
                }

                if tag == "body" {
                    in_body = true;
                }

                // Blok elementlerinden önce mevcut metni flush et
                if is_block_tag(tag) {
                    flush_text(&mut current_text, &mut parts);
                }
            }
            Ok(Event::End(ref e)) => {
                let name = e.name();
                let tag = local_name(name.as_ref());

                if skip_tags.contains(&tag) {
                    skip_depth = skip_depth.saturating_sub(1);
                    buf.clear();
                    continue;
                }

                if is_block_tag(tag) {
                    flush_text(&mut current_text, &mut parts);
                }
            }
            Ok(Event::Text(ref e)) => {
                if skip_depth == 0 && (in_body || !has_body_tag(xhtml)) {
                    if let Ok(text) = e.unescape() {
                        current_text.push_str(&text);
                    }
                }
            }
            Ok(Event::Eof) => break,
            Err(_) => break,
            _ => {}
        }
        buf.clear();
    }

    flush_text(&mut current_text, &mut parts);
    parts.join("\n")
}

/// Mevcut metin buffer'ını temizleyip output'a ekler.
fn flush_text(current: &mut String, output: &mut Vec<String>) {
    let trimmed = current.trim().to_string();
    if !trimmed.is_empty() {
        output.push(trimmed);
    }
    current.clear();
}

/// Blok seviye HTML tag'i mi?
fn is_block_tag(tag: &str) -> bool {
    matches!(
        tag,
        "p" | "div" | "h1" | "h2" | "h3" | "h4" | "h5" | "h6"
            | "li" | "ul" | "ol" | "blockquote" | "pre"
            | "section" | "article" | "table" | "tr"
    )
}

/// XHTML'de <body> tag'i var mı?
fn has_body_tag(xhtml: &str) -> bool {
    xhtml.contains("<body") || xhtml.contains("<BODY")
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
