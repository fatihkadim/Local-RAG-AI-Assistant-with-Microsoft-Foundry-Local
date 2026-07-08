"""
Proje konfigürasyon dosyası.
Tüm ayarları buradan merkezi olarak yönetin.
"""

# ── Foundry Local Model Ayarları ──────────────────────────
CHAT_MODEL = "phi-3.5-mini"           # Sohbet/cevap üretme modeli
EMBEDDING_MODEL = "qwen3-embedding-0.6b"  # Embedding modeli

# ── Veritabanı Ayarları ──────────────────────────────────
DATABASE_PATH = "knowledge_base.db"    # SQLite veritabanı dosya yolu

# ── Belge İşleme Ayarları ────────────────────────────────
DOCUMENTS_DIR = "documents"            # Belgelerin bulunduğu klasör
CHUNK_SIZE = 500                       # Her belge parçasının yaklaşık karakter uzunluğu
CHUNK_OVERLAP = 50                     # Parçalar arası örtüşme (bağlam kaybını önler)

# ── Retrieval Ayarları ───────────────────────────────────
TOP_K = 3                             # Kaç adet en ilgili belge parçası getirilsin

# ── Prompt Ayarları ──────────────────────────────────────
SYSTEM_PROMPT = """Sen yardımcı bir asistansın. Sana verilen bağlam bilgilerini kullanarak kullanıcının sorularını cevapla.
Kurallar:
1. Yalnızca verilen bağlam bilgilerini kullan.
2. Bağlamda cevap yoksa, "Bu konuda yeterli bilgim yok." de.
3. Cevabında kaynak belge adını belirt.
4. Kısa ve net cevaplar ver."""
