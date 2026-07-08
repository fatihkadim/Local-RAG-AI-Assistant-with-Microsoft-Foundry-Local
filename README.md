# Local RAG AI Assistant with Microsoft Foundry Local

Tamamen offline çalışan, yerel bir Soru-Cevap (Q&A) chatbot. Microsoft Foundry Local kullanarak belgelerden bilgi alıp, RAG (Retrieval-Augmented Generation) deseni ile cevap üretir.

## 🏗️ Proje Yapısı

```
├── config.py          # Merkezi konfigürasyon (model, DB, chunk ayarları)
├── main.py            # CLI giriş noktası
├── app.py             # Streamlit web arayüzü (opsiyonel)
├── ingestion.py       # Belge yükleme ve parçalama pipeline'ı
├── embeddings.py      # Foundry Local ile embedding hesaplama
├── database.py        # SQLite veritabanı işlemleri
├── retrieval.py       # Vektör benzerliği ile belge arama
├── llm.py             # Foundry Local LLM ile cevap üretme
├── requirements.txt   # Python bağımlılıkları
└── documents/         # Soru cevaplanacak belgeler (buraya koyun)
```

## 🚀 Kurulum

```bash
pip install -r requirements.txt
```

## 📖 Kullanım

### 1. Belgeleri Yükle
`documents/` klasörüne belgelerinizi (.txt, .md) koyun, ardından:
```bash
python main.py --ingest
```

### 2. Soru Sor (CLI)
```bash
python main.py
```

### 3. Web Arayüzü (Opsiyonel)
```bash
streamlit run app.py
```

## 🔧 Teknolojiler

- **Microsoft Foundry Local** — Yerelde LLM çalıştırma
- **RAG** — Retrieval-Augmented Generation deseni
- **SQLite** — Hafif yerel veritabanı
- **Python** — Ana geliştirme dili
