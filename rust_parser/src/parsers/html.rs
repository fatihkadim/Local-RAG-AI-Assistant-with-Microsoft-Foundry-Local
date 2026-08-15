/// HTML parser — HTML dosyalarından temiz metin çıkarır.
///
/// `scraper` crate'i ile DOM'u parse eder, ardından:
/// - `<script>`, `<style>`, `<nav>`, `<footer>`, `<header>` gibi
///   non-content elementlerini atlar
/// - Blok elementleri (p, div, h1-h6, li) arasına newline ekler
/// - Inline elementlerin metnini birleştirir
use std::fs;
use scraper::{Html, Node, ElementRef};

/// Atlanacak tag'ler (içerik olmayan bölümler).
const SKIP_TAGS: &[&str] = &[
    "script", "style", "nav", "footer", "noscript",
    "svg", "iframe", "object", "embed", "form", "head",
];

pub fn parse(file_path: &str) -> Result<String, String> {
    let html_content = fs::read_to_string(file_path)
        .or_else(|_| {
            let bytes = fs::read(file_path)
                .map_err(|e| format!("HTML dosyası okunamadı: {}", e))?;
            Ok::<String, String>(String::from_utf8_lossy(&bytes).to_string())
        })
        .map_err(|e| format!("HTML dosyası okunamadı: {}", e))?;

    extract_text_from_html(&html_content)
}

/// HTML'den temiz metin çıkarır.
fn extract_text_from_html(html: &str) -> Result<String, String> {
    let document = Html::parse_document(html);
    let mut parts: Vec<String> = Vec::new();

    // Root node'dan başlayarak ağacı gez
    let root = document.root_element();
    walk_node(&root, &mut parts);

    let result = parts
        .into_iter()
        .map(|p| p.trim().to_string())
        .filter(|p| !p.is_empty())
        .collect::<Vec<_>>()
        .join("\n\n");

    if result.is_empty() {
        return Err("HTML dosyasından metin çıkarılamadı".to_string());
    }

    Ok(result)
}

/// DOM ağacında recursive olarak düğümleri dolaşır.
fn walk_node(element: &ElementRef, parts: &mut Vec<String>) {
    for child in element.children() {
        match child.value() {
            Node::Element(el) => {
                let tag = el.name();
                if SKIP_TAGS.contains(&tag) {
                    continue;
                }

                if let Some(child_ref) = ElementRef::wrap(child) {
                    match tag {
                        "h1" => {
                            let text = get_inner_text(&child_ref);
                            if !text.is_empty() {
                                parts.push(format!("# {}", text));
                            }
                        }
                        "h2" => {
                            let text = get_inner_text(&child_ref);
                            if !text.is_empty() {
                                parts.push(format!("## {}", text));
                            }
                        }
                        "h3" => {
                            let text = get_inner_text(&child_ref);
                            if !text.is_empty() {
                                parts.push(format!("### {}", text));
                            }
                        }
                        "h4" | "h5" | "h6" => {
                            let text = get_inner_text(&child_ref);
                            if !text.is_empty() {
                                parts.push(format!("#### {}", text));
                            }
                        }
                        "p" | "blockquote" | "pre" => {
                            let text = get_inner_text(&child_ref);
                            if !text.is_empty() {
                                parts.push(text);
                            }
                        }
                        "li" => {
                            let text = get_inner_text(&child_ref);
                            if !text.is_empty() {
                                parts.push(format!("• {}", text));
                            }
                        }
                        _ => {
                            // div, section, article, body, table vb. -> içine devam et
                            walk_node(&child_ref, parts);
                        }
                    }
                }
            }
            Node::Text(t) => {
                let text = t.trim();
                if !text.is_empty() {
                    parts.push(text.to_string());
                }
            }
            _ => {}
        }
    }
}

/// Bir elementin altındaki tüm metinleri birleştirir.
fn get_inner_text(element: &ElementRef) -> String {
    element
        .text()
        .collect::<Vec<_>>()
        .join(" ")
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}
