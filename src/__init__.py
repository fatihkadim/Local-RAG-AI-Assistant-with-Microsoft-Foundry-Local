"""
src — Local RAG AI Assistant kaynak kod paketi.

Bu paket, projenin tüm iş mantığı modüllerini içerir:
- config: Merkezi konfigürasyon ayarları
- sdk_manager: Foundry Local SDK singleton yönetimi
- database: SQLite veritabanı katmanı
- embeddings: Embedding vektör servisi
- ingestion: Belge yükleme pipeline'ı
- retrieval: Belge arama (cosine similarity)
- llm: LLM entegrasyonu ve cevap üretimi
"""
