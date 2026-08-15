"""
Proje konfigürasyon dosyası.
Tüm ayarları buradan merkezi olarak yönetin.
"""

# ── Foundry Local Model Ayarları ──────────────────────────
CHAT_MODEL = "phi-3.5-mini"                        # Sohbet modeli alias'ı (catalog.get_model ile kullanılır)
EMBEDDING_MODEL = "qwen3-embedding-0.6b"           # Embedding modeli alias'ı

# ── Veritabanı Ayarları ──────────────────────────────────
QDRANT_URL = "http://localhost:6333"       # Qdrant Docker adresi
QDRANT_COLLECTION = "documents"            # Qdrant koleksiyon adı

# ── Belge İşleme Ayarları ────────────────────────────────
DOCUMENTS_DIR = "documents"            # Belgelerin bulunduğu klasör

# Desteklenen dosya uzantıları (Rust parser + Python fallback)
SUPPORTED_EXTENSIONS = [
    ".txt", ".md", ".pdf",                     # Temel metin formatları
    ".docx", ".pptx",                          # Microsoft Office
    ".html", ".htm",                           # Web sayfaları
    ".csv", ".tsv",                            # Tablolu veri
    ".xlsx", ".xls",                           # Excel
    ".epub",                                   # E-kitap
    ".json", ".jsonl",                         # Yapısal veri
    ".rst",                                    # reStructuredText
]

CHUNK_SIZE = 500                       # Her belge parçasının yaklaşık karakter uzunluğu
CHUNK_OVERLAP = 50                     # Parçalar arası örtüşme (bağlam kaybını önler)

# ── Retrieval Ayarları ───────────────────────────────────
TOP_K = 3                             # Kaç adet en ilgili belge parçası getirilsin

# ── Prompt Ayarları ──────────────────────────────────────
SYSTEM_PROMPT = """Sen Türkçe konuşan, nazik ve yardımsever bir asistansın.
Sana verilen bağlam (doküman) bilgilerini inceleyerek kullanıcının sorusuna doğrudan ve net yanıt ver.

Kurallar:
1. Yalnızca sağlanan bağlam bilgisinde yer alan gerçeklere dayanarak cevap ver.
2. Bağlamda sorunun cevabı yoksa sadece "Bu konuda verilen belgelerde yeterli bilgi bulunmamaktadır." yaz.
3. Ekstra başlık, etiket ("Parça:", "Soru:", "Cevap:") veya kendini tekrarlayan şablon metinler üretme. Doğrudan tek bir akıcı cevap cümlesi/paragrafı yaz.
4. Cevap haricinde kaynak adı veya parça numarası yazmana gerek yoktur; bu bilgi arayüz tarafından otomatik gösterilir."""
