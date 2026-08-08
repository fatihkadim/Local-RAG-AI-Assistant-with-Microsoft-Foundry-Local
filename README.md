# 🤖 Local RAG AI Assistant with Microsoft Foundry Local

Tamamen **offline** çalışan, yerel bir Soru-Cevap (Q&A) chatbot.  
Microsoft Foundry Local kullanarak belgelerden bilgi alır ve **RAG** (Retrieval-Augmented Generation) deseniyle cevap üretir — internet bağlantısı veya bulut servisi gerektirmez.

---

## ✨ Özellikler

- 🔒 **Tamamen offline** — Tüm model çalıştırma Foundry Local üzerinden yerelde yapılır
- 📄 **Esnek belge desteği** — `.txt`, `.md` ve `.pdf` dosyalarını otomatik işler
- 🔍 **Semantik arama** — Cosine similarity ile anlam tabanlı belge arama
- 📚 **Kaynak gösterimi** — Her cevabın hangi belgeden geldiği belirtilir
- 💬 **İki arayüz** — Terminal (CLI) ve tarayıcı (Streamlit web UI)
- ⚡ **GPU/NPU hızlandırma** — Desteklenen donanımda otomatik aktifleşir

---

## 🏗️ Mimari

```
Kullanıcı Sorusu
      │
      ▼
[embeddings.py]  →  Soruyu vektöre çevir (qwen3-embedding-0.6b)
      │
      ▼
[retrieval.py]   →  En benzer belge parçalarını bul (cosine similarity)
      │
      ▼
[llm.py]         →  Bağlamla birlikte LLM'e gönder (phi-3.5-mini)
      │
      ▼
    Cevap + Kaynak Bilgisi

─────────────────────────────────────────────────────
Belge Yükleme (tek seferlik):
[ingestion.py]  →  Oku → Parçala → Embed et → [database.py] SQLite'a kaydet
```

### Proje Dosya Yapısı

```
Local-RAG-AI-Assistant-with-Microsoft-Foundry-Local/
├── config.py          # Merkezi konfigürasyon (model alias, DB, chunk ayarları)
├── database.py        # SQLite CRUD katmanı
├── embeddings.py      # Foundry Local embedding servisi
├── ingestion.py       # Belge okuma & parçalama pipeline'ı
├── retrieval.py       # Cosine similarity ile semantik arama
├── llm.py             # Foundry Local LLM entegrasyonu
├── main.py            # CLI giriş noktası (argparse + REPL)
├── app.py             # Streamlit web arayüzü
├── requirements.txt   # Python bağımlılıkları
├── documents/         # ← Belgelerinizi buraya koyun (.txt, .md, .pdf)
├── docs/
│   └── sprint_plan.md # Agile sprint planı (geliştirme süreci)
└── tests/
    ├── test_database.py
    ├── test_embeddings.py
    ├── test_sprint3.py
    └── test_sprint4.py
```

---

## ⚙️ Gereksinimler

- **Python** 3.10+
- **Microsoft Foundry Local** — [İndir](https://aka.ms/foundry-local)
  - `phi-3.5-mini` (chat modeli) — Foundry Local üzerinden otomatik indirilir
  - `qwen3-embedding-0.6b` (embedding modeli) — Foundry Local üzerinden otomatik indirilir
- **İşletim Sistemi:** Windows 10/11

---

## 🚀 Kurulum

### 1. Repoyu klonla

```bash
git clone https://github.com/fatihkadim/Local-RAG-AI-Assistant-with-Microsoft-Foundry-Local.git
cd Local-RAG-AI-Assistant-with-Microsoft-Foundry-Local
```

### 2. Sanal ortam oluştur ve aktifleştir

```bash
python -m venv venv

# Windows
.\venv\Scripts\Activate.ps1
```

### 3. Bağımlılıkları yükle

```bash
pip install -r requirements.txt
```

### 4. Microsoft Foundry Local'ı yükle ve başlat

[https://aka.ms/foundry-local](https://aka.ms/foundry-local) adresinden Foundry Local'ı indir ve kur.  
Kurulum sonrası Foundry Local arka planda servis olarak çalışır — uygulama her başlatıldığında SDK otomatik bağlanır.

---

## 📖 Kullanım

### Adım 1 — Belgelerini yükle

`documents/` klasörüne `.txt`, `.md` veya `.pdf` dosyalarını koy, ardından:

```bash
python main.py --ingest
```

Çıktı örneği:
```
[1/4] Veritabani hazirlaniyor...
[2/4] Belgeler okunuyor...  3 belge okundu.
[3/4] Belgeler parcalaniyor...  17 parca olusturuldu.
[4/4] Embedding'ler uretiliyor...
✅ Ingestion tamamlandı: 17 parça yüklendi.
```

### Adım 2 — Soru sor

#### CLI (Terminal)
```bash
python main.py
```

```
══════════════════════════════════════════════════════════
  🤖 Local RAG AI Assistant
  Microsoft Foundry Local ile çalışır (tamamen offline)
══════════════════════════════════════════════════════════

📌 Sorunuz: Python nedir?

📝 Cevap:
Python, yüksek seviyeli, genel amaçlı bir programlama dilidir...
(Kaynak: python_temelleri.txt, Parça: 1)
```

#### Web Arayüzü (Tarayıcı)
```bash
streamlit run app.py
```
Tarayıcı otomatik açılır: **http://localhost:8501**

#### Tek soru modu
```bash
python main.py -q "Python nedir?"
```

---

## ⚙️ Konfigürasyon

Tüm ayarlar [`config.py`](config.py) üzerinden yönetilir:

| Ayar | Varsayılan | Açıklama |
|---|---|---|
| `CHAT_MODEL` | `phi-3.5-mini` | Foundry Local chat modeli alias'ı |
| `EMBEDDING_MODEL` | `qwen3-embedding-0.6b` | Embedding modeli alias'ı |
| `DATABASE_PATH` | `knowledge_base.db` | SQLite veritabanı dosya yolu |
| `DOCUMENTS_DIR` | `documents` | Belgelerin bulunduğu klasör |
| `CHUNK_SIZE` | `500` | Belge parçası karakter uzunluğu |
| `CHUNK_OVERLAP` | `50` | Parçalar arası örtüşme (karakter) |
| `TOP_K` | `3` | Her sorgu için getirilen en ilgili parça sayısı |

---

## 🧪 Testleri Çalıştırma

```bash
# Veritabanı testleri (SDK gerektirmez, hızlı)
python test_database.py

# Embedding testleri (Foundry Local gerekir)
python test_embeddings.py

# Ingestion + Retrieval testleri (Foundry Local gerekir)
python test_sprint3.py

# LLM + Uçtan uca testler (Foundry Local gerekir)
python test_sprint4.py
```

---

## 🔧 Kullanılan Teknolojiler

| Teknoloji | Kullanım |
|---|---|
| [Microsoft Foundry Local](https://aka.ms/foundry-local) | Yerelde LLM ve embedding çalıştırma |
| [Phi-3.5-mini](https://huggingface.co/microsoft/Phi-3.5-mini-instruct) | Cevap üretme (chat modeli) |
| [Qwen3-Embedding-0.6b](https://huggingface.co/Qwen/Qwen3-Embedding) | Semantik vektör temsili |
| SQLite (`sqlite3`) | Vektör ve metadata depolama |
| [Streamlit](https://streamlit.io) | Web arayüzü |
| Python 3.10+ | Ana geliştirme dili |

---

## 📋 Bilinen Sınırlamalar

- `.txt`, `.md` ve `.pdf` (metin tabanlı) dosyaları desteklenir
- Büyük dil modelleri (7B+) yavaş çalışabilir — `phi-3.5-mini` CPU için optimize edilmiştir
- Çok uzun sorular/bağlamlar bellek sınırını zorlayabilir (`max_tokens=512` ile sınırlandırılmıştır)
- Streaming yanıtlar Streamlit arayüzünde henüz gösterilmemektedir

---

## 📄 Lisans

MIT License
