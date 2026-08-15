/// JSON/JSONL parser — Yapısal veri dosyalarını metin olarak parse eder.
///
/// İki format desteklenir:
/// - `.json`  — Tek JSON objesi veya array
/// - `.jsonl` — Satır bazlı JSON (her satır ayrı obje)
///
/// JSON objelerini "anahtar: değer" formatında düz metne dönüştürür.
/// Nested objeler indentli olarak gösterilir.
use std::fs;
use serde_json::Value;

/// Tek bir JSON dosyasını parse eder.
pub fn parse(file_path: &str) -> Result<String, String> {
    let content = fs::read_to_string(file_path)
        .map_err(|e| format!("JSON dosyası okunamadı: {}", e))?;

    let value: Value = serde_json::from_str(&content)
        .map_err(|e| format!("JSON parse hatası: {}", e))?;

    Ok(value_to_text(&value, 0))
}

/// JSONL (JSON Lines) dosyasını parse eder.
pub fn parse_jsonl(file_path: &str) -> Result<String, String> {
    let content = fs::read_to_string(file_path)
        .map_err(|e| format!("JSONL dosyası okunamadı: {}", e))?;

    let mut entries: Vec<String> = Vec::new();

    for (idx, line) in content.lines().enumerate() {
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }

        match serde_json::from_str::<Value>(trimmed) {
            Ok(value) => {
                let text = value_to_text(&value, 0);
                if !text.is_empty() {
                    entries.push(format!("Kayıt {}:\n{}", idx + 1, text));
                }
            }
            Err(e) => {
                eprintln!("JSONL satır {} parse hatası: {}", idx + 1, e);
                continue;
            }
        }
    }

    if entries.is_empty() {
        return Err("JSONL dosyasından metin çıkarılamadı".to_string());
    }

    Ok(entries.join("\n\n"))
}

/// JSON Value'yu okunabilir düz metne dönüştürür.
fn value_to_text(value: &Value, indent: usize) -> String {
    let prefix = "  ".repeat(indent);

    match value {
        Value::Null => String::new(),
        Value::Bool(b) => {
            if *b { "Evet".to_string() } else { "Hayır".to_string() }
        }
        Value::Number(n) => n.to_string(),
        Value::String(s) => s.clone(),
        Value::Array(arr) => {
            if arr.is_empty() {
                return String::new();
            }

            // Basit değer dizisi mi? (string/number)
            let all_simple = arr.iter().all(|v| matches!(v, Value::String(_) | Value::Number(_) | Value::Bool(_)));

            if all_simple {
                let items: Vec<String> = arr
                    .iter()
                    .filter_map(|v| {
                        let text = value_to_text(v, 0);
                        if text.is_empty() { None } else { Some(text) }
                    })
                    .collect();
                items.join(", ")
            } else {
                let items: Vec<String> = arr
                    .iter()
                    .enumerate()
                    .filter_map(|(i, v)| {
                        let text = value_to_text(v, indent + 1);
                        if text.is_empty() {
                            None
                        } else {
                            Some(format!("{}[{}]\n{}", prefix, i + 1, text))
                        }
                    })
                    .collect();
                items.join("\n")
            }
        }
        Value::Object(map) => {
            let parts: Vec<String> = map
                .iter()
                .filter_map(|(key, val)| {
                    let text = value_to_text(val, indent + 1);
                    if text.is_empty() {
                        None
                    } else if matches!(val, Value::Object(_) | Value::Array(_))
                        && !matches!(val, Value::Array(_) if val.as_array().map_or(true, |a| a.iter().all(|v| matches!(v, Value::String(_) | Value::Number(_) | Value::Bool(_)))))
                    {
                        Some(format!("{}{}:\n{}", prefix, format_key(key), text))
                    } else {
                        Some(format!("{}{}: {}", prefix, format_key(key), text))
                    }
                })
                .collect();
            parts.join("\n")
        }
    }
}

/// JSON anahtarını okunabilir formata dönüştürür.
/// "first_name" -> "First Name"
fn format_key(key: &str) -> String {
    key.replace('_', " ")
        .replace('-', " ")
        .split_whitespace()
        .map(|word| {
            let mut c = word.chars();
            match c.next() {
                None => String::new(),
                Some(first) => {
                    let upper: String = first.to_uppercase().collect();
                    upper + c.as_str()
                }
            }
        })
        .collect::<Vec<_>>()
        .join(" ")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_format_key() {
        assert_eq!(format_key("first_name"), "First Name");
        assert_eq!(format_key("user-id"), "User Id");
        assert_eq!(format_key("email"), "Email");
    }

    #[test]
    fn test_simple_object() {
        let json = r#"{"name": "Ahmet", "age": 30}"#;
        let value: Value = serde_json::from_str(json).unwrap();
        let text = value_to_text(&value, 0);
        assert!(text.contains("Name: Ahmet"));
        assert!(text.contains("Age: 30"));
    }

    #[test]
    fn test_array() {
        let json = r#"[{"name": "Ali"}, {"name": "Veli"}]"#;
        let value: Value = serde_json::from_str(json).unwrap();
        let text = value_to_text(&value, 0);
        assert!(text.contains("Ali"));
        assert!(text.contains("Veli"));
    }
}
