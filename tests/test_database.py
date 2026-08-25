"""
Veritabanı Katmanı (Qdrant & Payload Encryption) Test Modülü.

Testler:
1. Payload şifreleme ve çözme yardımcı fonksiyonları
2. insert_chunk & insert_chunks_batch girdi doğrulamaları
3. Qdrant bağlantısı varsa uçtan uca ekleme, sayma ve arama testleri
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import config
from src import database
from src.vault import VaultManager, set_vault_manager


def test_database_payload_encryption_without_vault():
    """Vault yöneticisi yokken metnin şifrelenmeden aynı döndüğünü doğrular."""
    set_vault_manager(None)
    plain = "Test düz metin chunk"
    assert database._encrypt_payload_text(plain) == plain
    assert database._decrypt_payload_text(plain) == plain


def test_database_payload_encryption_with_vault():
    """Vault aktifken metnin şifrelenip çözülebildiğini doğrular."""
    import tempfile, shutil
    td = tempfile.mkdtemp()
    try:
        vm = VaultManager("DBTestPassword123!", vault_dir=td)
        set_vault_manager(vm)

        plain = "Bu metin şifreli payload olmalıdır."
        encrypted = database._encrypt_payload_text(plain)
        assert encrypted != plain

        decrypted = database._decrypt_payload_text(encrypted)
        assert decrypted == plain
    finally:
        set_vault_manager(None)
        shutil.rmtree(td, ignore_errors=True)


def test_database_insert_chunk_validation():
    """insert_chunk fonksiyonunun boş text veya embedding'i reddettiğini doğrular."""
    with pytest.raises(ValueError, match="boş olamaz"):
        database.insert_chunk(text="", embedding=[0.1, 0.2], source_file="doc.txt", chunk_index=0)

    with pytest.raises(ValueError, match="boş olamaz"):
        database.insert_chunk(text="metin", embedding=[], source_file="doc.txt", chunk_index=0)


def test_qdrant_integration_if_available():
    """Qdrant sunucusu erişilebilirse temel DB operasyonlarını test eder."""
    try:
        database.init_db()
    except Exception as e:
        pytest.skip(f"Qdrant sunucusuna bağlanılamadı (Docker kapalı olabilir): {e}")

    # Temel CRUD kontrolü
    try:
        database.insert_chunk(
            text="Qdrant entegrasyon test parçası.",
            embedding=[0.01] * 1024,
            source_file="__test_qdrant_doc__.txt",
            chunk_index=0
        )
        count = database.get_chunk_count()
        assert count > 0

        sources = database.get_sources()
        assert "__test_qdrant_doc__.txt" in sources

        # Arama
        results = database.search_chunks([0.01] * 1024, top_k=1)
        assert len(results) >= 1

        # Temizlik
        database.delete_file_chunks("__test_qdrant_doc__.txt")
    except Exception as e:
        pytest.fail(f"Qdrant operasyonu başarısız: {e}")
