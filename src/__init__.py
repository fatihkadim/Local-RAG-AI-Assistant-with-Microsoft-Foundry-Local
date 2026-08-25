"""
src — Local RAG AI Assistant kaynak kod paketi.

Bu paket, projenin tüm iş mantığı modüllerini içerir:
- config: Merkezi konfigürasyon ayarları
- sdk_manager: Foundry Local SDK singleton yönetimi
- crypto: Kriptografik işlemler (AES-256-GCM, PBKDF2)
- vault: Encrypted Document Vault yöneticisi (VaultManager)
- database: Qdrant vektör veritabanı katmanı ve payload şifreleme
- embeddings: Embedding vektör servisi
- ingestion: Belge yükleme, akıllı önbellek ve parçalama pipeline'ı
- retrieval: Belge arama ve bağlam oluşturma
- llm: LLM entegrasyonu ve cevap üretimi
- telemetry: OpenTelemetry & Prometheus observability katmanı
"""

