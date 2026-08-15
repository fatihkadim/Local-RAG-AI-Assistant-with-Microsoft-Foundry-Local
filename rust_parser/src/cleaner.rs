/// Metin temizleme ve normalleştirme modülü.
///
/// Parse edilen ham metin çıktısını normalize eder:
/// - Unicode normalization (NFC)
/// - Fazla whitespace temizleme
/// - Boilerplate kaldırma
/// - Kontrol karakterleri temizleme
use unicode_normalization::UnicodeNormalization;

/// Ham metni temizleyip normalize eder.
pub fn clean_text(text: &str) -> String {
    let mut result = text.to_string();

    // 1. Unicode NFC normalization
    result = result.nfc().collect::<String>();

    // 2. Kontrol karakterlerini temizle (newline ve tab hariç)
    result = result
        .chars()
        .map(|c| {
            if c.is_control() && c != '\n' && c != '\t' && c != '\r' {
                ' '
            } else {
                c
            }
        })
        .collect();

    // 3. \r\n -> \n
    result = result.replace("\r\n", "\n");

    // 4. 3'ten fazla ardışık newline'ı 2'ye düşür
    while result.contains("\n\n\n") {
        result = result.replace("\n\n\n", "\n\n");
    }

    // 5. Satır içi fazla boşlukları tekle (ama newline'ları koru)
    let lines: Vec<String> = result
        .lines()
        .map(|line| {
            let trimmed = line.trim();
            if trimmed.is_empty() {
                String::new()
            } else {
                // Satır içi çoklu boşlukları tekle
                collapse_spaces(trimmed)
            }
        })
        .collect();

    result = lines.join("\n");

    // 6. Baş ve sondaki whitespace'i temizle
    result.trim().to_string()
}

/// Ardışık boşlukları tek boşluğa indirger.
fn collapse_spaces(s: &str) -> String {
    let mut result = String::with_capacity(s.len());
    let mut prev_space = false;

    for c in s.chars() {
        if c == ' ' || c == '\t' {
            if !prev_space {
                result.push(' ');
                prev_space = true;
            }
        } else {
            result.push(c);
            prev_space = false;
        }
    }

    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_clean_basic() {
        assert_eq!(clean_text("  hello   world  "), "hello world");
    }

    #[test]
    fn test_clean_multiple_newlines() {
        assert_eq!(clean_text("a\n\n\n\n\nb"), "a\n\nb");
    }

    #[test]
    fn test_clean_crlf() {
        assert_eq!(clean_text("a\r\nb"), "a\nb");
    }

    #[test]
    fn test_clean_control_chars() {
        assert_eq!(clean_text("hello\x00world"), "hello world");
    }

    #[test]
    fn test_clean_empty() {
        assert_eq!(clean_text(""), "");
    }

    #[test]
    fn test_clean_unicode_normalization() {
        // é (e + combining accent) vs é (precomposed)
        let composed = "caf\u{00e9}";
        let decomposed = "cafe\u{0301}";
        assert_eq!(clean_text(composed), clean_text(decomposed));
    }
}
