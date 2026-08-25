"""
Encrypted Document Vault Kapsamlı Test Paketi.

Test Kapsamı:
1. Crypto modülü (salt üretimi, PBKDF2 anahtar türetme, AES-256-GCM şifreleme/çözme, Base64)
2. Hata & güvenlik senaryoları (yanlış anahtar, bozuk veri, geçersiz girdiler)
3. VaultManager (oluşturma, şifre doğrulama, yanlış şifre engeli, metadata)
4. Dosya şifreleme/çözme (.vault formatı, metin ve binary)
5. Vault durumu (get_vault_status) ve göç (migrate_documents)
6. Ingestion şifreli dosya ayrıştırma (_parse_vault_file)
7. Database payload şifreleme entegrasyonu (_encrypt_payload_text, _decrypt_payload_text)
"""

import os
import sys
import shutil
import tempfile
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import config
from src import crypto
from src.vault import (
    VaultManager,
    get_vault_manager,
    set_vault_manager,
    init_vault_with_password,
)
from src import ingestion
from src import database


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def temp_vault_dir():
    """Geçici vault klasörü oluşturur ve test sonunda temizler."""
    temp_dir = tempfile.mkdtemp(prefix="test_vault_")
    yield temp_dir
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_docs_dir():
    """Geçici belgeler klasörü oluşturur ve test sonunda temizler."""
    temp_dir = tempfile.mkdtemp(prefix="test_docs_")
    yield temp_dir
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)


# ── 1. Crypto Modülü Testleri ─────────────────────────────────

def test_crypto_generate_salt():
    """Rastgele 16 byte salt üretildiğini ve her seferinde farklı olduğunu doğrular."""
    salt1 = crypto.generate_salt()
    salt2 = crypto.generate_salt()
    assert isinstance(salt1, bytes)
    assert len(salt1) == crypto.SALT_SIZE
    assert salt1 != salt2


def test_crypto_derive_key_determinism():
    """Aynı şifre ve salt ile her zaman aynı 32 byte anahtarın üretildiğini doğrular."""
    salt = crypto.generate_salt()
    password = "MasterPassword123!"

    key1 = crypto.derive_key(password, salt, iterations=10_000)
    key2 = crypto.derive_key(password, salt, iterations=10_000)

    assert isinstance(key1, bytes)
    assert len(key1) == crypto.KEY_SIZE
    assert key1 == key2


def test_crypto_derive_key_different_inputs():
    """Farklı şifre veya salt ile farklı anahtarlar üretildiğini doğrular."""
    salt1 = crypto.generate_salt()
    salt2 = crypto.generate_salt()

    key_pass1 = crypto.derive_key("PasswordOne", salt1, iterations=10_000)
    key_pass2 = crypto.derive_key("PasswordTwo", salt1, iterations=10_000)
    key_salt2 = crypto.derive_key("PasswordOne", salt2, iterations=10_000)

    assert key_pass1 != key_pass2
    assert key_pass1 != key_salt2


def test_crypto_derive_key_invalid_inputs():
    """Geçersiz şifre veya salt verildiğinde ValueError fırlatıldığını doğrular."""
    salt = crypto.generate_salt()
    with pytest.raises(ValueError):
        crypto.derive_key("", salt)
    with pytest.raises(ValueError):
        crypto.derive_key(None, salt)
    with pytest.raises(ValueError):
        crypto.derive_key("valid_password", b"short")


def test_crypto_encrypt_decrypt_text():
    """Metin şifreleme ve çözme döngüsünün (roundtrip) doğruluğunu test eder."""
    salt = crypto.generate_salt()
    key = crypto.derive_key("my_secret", salt, iterations=10_000)

    original_text = "Gizli belge: Türkçe karakterler çşğüöı İĞÜŞÖÇ ve özel semboller @#$%^&*()"
    encrypted = crypto.encrypt(original_text, key)

    assert isinstance(encrypted, bytes)
    assert encrypted != original_text.encode("utf-8")
    assert len(encrypted) > len(original_text)

    decrypted = crypto.decrypt(encrypted, key)
    assert decrypted == original_text


def test_crypto_encrypt_decrypt_bytes():
    """Ham bayt verisi şifreleme ve çözme döngüsünü test eder."""
    salt = crypto.generate_salt()
    key = crypto.derive_key("my_secret", salt, iterations=10_000)

    raw_data = bytes([0x00, 0xFF, 0xAA, 0x55, 0x12, 0x34])
    encrypted = crypto.encrypt_bytes(raw_data, key)

    assert isinstance(encrypted, bytes)
    assert encrypted != raw_data

    decrypted = crypto.decrypt_bytes(encrypted, key)
    assert decrypted == raw_data


def test_crypto_encrypt_decrypt_b64():
    """Base64 string formatında şifreleme ve çözmeyi test eder."""
    salt = crypto.generate_salt()
    key = crypto.derive_key("my_secret", salt, iterations=10_000)

    original_text = "Qdrant payload gizli metin chunk'ı"
    b64_enc = crypto.encrypt_to_b64(original_text, key)

    assert isinstance(b64_enc, str)
    assert b64_enc != original_text

    decrypted = crypto.decrypt_from_b64(b64_enc, key)
    assert decrypted == original_text


def test_crypto_wrong_key_fails():
    """Yanlış anahtarla şifre çözülmeye çalışıldığında RuntimeError fırlatıldığını doğrular."""
    salt = crypto.generate_salt()
    key_correct = crypto.derive_key("CorrectPassword", salt, iterations=10_000)
    key_wrong = crypto.derive_key("WrongPassword", salt, iterations=10_000)

    encrypted = crypto.encrypt("Çok gizli veri", key_correct)

    with pytest.raises(RuntimeError):
        crypto.decrypt(encrypted, key_wrong)


def test_crypto_tampered_ciphertext_fails():
    """Bozulmuş şifreli veri (tampered ciphertext) ile çözmenin başarısız olduğunu doğrular."""
    salt = crypto.generate_salt()
    key = crypto.derive_key("Password", salt, iterations=10_000)

    encrypted = bytearray(crypto.encrypt("Bozulacak metin", key))
    # Şifreli metnin ortasında 1 baytı değiştir
    encrypted[15] ^= 0xFF

    with pytest.raises(RuntimeError):
        crypto.decrypt(bytes(encrypted), key)


def test_crypto_invalid_data_length():
    """Çok kısa veya boş şifreli verinin reddedildiğini doğrular."""
    salt = crypto.generate_salt()
    key = crypto.derive_key("Password", salt, iterations=10_000)

    with pytest.raises(ValueError):
        crypto.decrypt(b"short", key)
    with pytest.raises(ValueError):
        crypto.decrypt(b"", key)


# ── 2. VaultManager Testleri ──────────────────────────────────

def test_vault_manager_init_new(temp_vault_dir):
    """Yeni bir vault oluşturulduğunda metadata dosyasının yazıldığını test eder."""
    vm = VaultManager("SafePassword123!", vault_dir=temp_vault_dir)

    assert os.path.exists(vm.meta_path)
    assert vm.key is not None
    assert len(vm.key) == 32
    assert vm.salt is not None
    assert len(vm.salt) == 16


def test_vault_manager_open_existing(temp_vault_dir):
    """Mevcut vault'un doğru şifre ile başarıyla açılabildiğini test eder."""
    password = "MySecurePassword!"
    # İlk kez oluştur
    vm1 = VaultManager(password, vault_dir=temp_vault_dir)
    original_salt = vm1.salt

    # Aynı dizindeki mevcut vault'u tekrar aç
    vm2 = VaultManager(password, vault_dir=temp_vault_dir)
    assert vm2.salt == original_salt
    assert vm2.key == vm1.key


def test_vault_manager_wrong_password(temp_vault_dir):
    """Mevcut bir vault'a yanlış şifre girildiğinde RuntimeError fırlatıldığını test eder."""
    VaultManager("CorrectPassword123!", vault_dir=temp_vault_dir)

    with pytest.raises(RuntimeError, match="Vault sifresi yanlis"):
        VaultManager("IncorrectPassword!", vault_dir=temp_vault_dir)


def test_vault_manager_empty_password(temp_vault_dir):
    """Boş şifre girildiğinde ValueError fırlatıldığını test eder."""
    with pytest.raises(ValueError):
        VaultManager("", vault_dir=temp_vault_dir)
    with pytest.raises(ValueError):
        VaultManager("   ", vault_dir=temp_vault_dir)


def test_vault_manager_text_encryption(temp_vault_dir):
    """VaultManager üzerinden metin şifreleme ve çözmeyi test eder."""
    vm = VaultManager("Pass12345", vault_dir=temp_vault_dir)
    text = "Vault yöneticisi metin şifreleme testi"

    enc = vm.encrypt_text(text)
    assert isinstance(enc, str)
    assert enc != text

    dec = vm.decrypt_text(enc)
    assert dec == text


def test_vault_manager_file_encryption_text(temp_vault_dir, temp_docs_dir):
    """Metin dosyasını şifreleme (.vault oluşturma) ve geri çözme testini yapar."""
    vm = VaultManager("FilePassword123!", vault_dir=temp_vault_dir)

    # Örnek dosya oluştur
    sample_path = os.path.join(temp_docs_dir, "gizli_not.txt")
    sample_content = "Bu dosya son derece gizli bilgiler içermektedir."
    with open(sample_path, "w", encoding="utf-8") as f:
        f.write(sample_content)

    # Şifrele
    vault_file_path = vm.encrypt_file(sample_path)
    assert os.path.exists(vault_file_path)
    assert vault_file_path.endswith("gizli_not.txt.vault")

    # Çöz
    orig_name, dec_content = vm.decrypt_file_to_text(vault_file_path)
    assert orig_name == "gizli_not.txt"
    assert dec_content == sample_content


def test_vault_manager_file_encryption_binary(temp_vault_dir, temp_docs_dir):
    """Binary dosya şifreleme ve bayt olarak çözme testini yapar."""
    vm = VaultManager("BinaryPass123!", vault_dir=temp_vault_dir)

    binary_path = os.path.join(temp_docs_dir, "sample.bin")
    binary_data = b"\x00\x01\x02\x03\xFF\xFE\xFD\xFC" * 100
    with open(binary_path, "wb") as f:
        f.write(binary_data)

    vault_file_path = vm.encrypt_file(binary_path)
    assert os.path.exists(vault_file_path)

    orig_name, dec_bytes = vm.decrypt_file(vault_file_path)
    assert orig_name == "sample.bin"
    assert dec_bytes == binary_data


def test_vault_manager_status(temp_vault_dir, temp_docs_dir):
    """get_vault_status fonksiyonunun doğru istatistikler döndürdüğünü test eder."""
    vm = VaultManager("StatusPassword123!", vault_dir=temp_vault_dir)

    # Başlangıç durumu
    status = vm.get_vault_status()
    assert status["vault_dir"] == temp_vault_dir
    assert status["meta_exists"] is True
    assert status["vault_files_count"] == 0

    # 1 dosya ekle
    doc_path = os.path.join(temp_docs_dir, "test.md")
    with open(doc_path, "w", encoding="utf-8") as f:
        f.write("# Markdown Dokümanı")
    vm.encrypt_file(doc_path)

    status_after = vm.get_vault_status()
    assert status_after["vault_files_count"] == 1
    assert "test.md.vault" in status_after["vault_files"]


def test_vault_manager_migration(temp_vault_dir, temp_docs_dir):
    """migrate_documents fonksiyonunun tüm desteklenen belgeleri şifrelediğini test eder."""
    vm = VaultManager("MigrationPassword123!", vault_dir=temp_vault_dir)

    # 3 farklı formatta belge oluştur
    files = {
        "doc1.txt": "Metin dokümanı 1",
        "doc2.md": "# Başlık 2",
        "doc3.csv": "col1,col2\nval1,val2",
    }
    for fname, content in files.items():
        with open(os.path.join(temp_docs_dir, fname), "w", encoding="utf-8") as f:
            f.write(content)

    migration_stats = vm.migrate_documents(documents_dir=temp_docs_dir)

    assert migration_stats["migrated_count"] == 3
    assert migration_stats["failed_count"] == 0

    # Vault içindeki dosyaları kontrol et
    status = vm.get_vault_status()
    assert status["vault_files_count"] == 3


def test_vault_manager_singleton():
    """Modül seviyesi get_vault_manager / set_vault_manager singleton işleyişini test eder."""
    temp_dir = tempfile.mkdtemp()
    try:
        vm = VaultManager("SingletonTestPass!", vault_dir=temp_dir)
        set_vault_manager(vm)
        assert get_vault_manager() is vm

        set_vault_manager(None)
        assert get_vault_manager() is None
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ── 3. Ingestion & Database Entegrasyon Testleri ───────────────

def test_ingestion_parse_vault_file(temp_vault_dir, temp_docs_dir):
    """ingestion._parse_vault_file fonksiyonunun şifreli dosyayı çözüp ayrıştırdığını test eder."""
    vm = VaultManager("IngestPassword123!", vault_dir=temp_vault_dir)

    # Metin dosyası şifrele
    txt_path = os.path.join(temp_docs_dir, "test_ingest.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("Bu metin parçalanmak ve embed edilmek üzere hazırlandı.")

    vault_path = vm.encrypt_file(txt_path)

    orig_name, content = ingestion._parse_vault_file(vault_path, vm)
    assert orig_name == "test_ingest.txt"
    assert "Bu metin parçalanmak" in content


def test_database_payload_encryption_helpers(temp_vault_dir):
    """database._encrypt_payload_text ve _decrypt_payload_text entegrasyonunu test eder."""
    vm = VaultManager("DBPayloadPass123!", vault_dir=temp_vault_dir)
    set_vault_manager(vm)

    try:
        sample_text = "Qdrant vektör veritabanına kaydedilecek hassas chunk."

        # Şifrele
        encrypted_payload = database._encrypt_payload_text(sample_text)
        assert encrypted_payload != sample_text

        # Çöz
        decrypted_payload = database._decrypt_payload_text(encrypted_payload)
        assert decrypted_payload == sample_text

    finally:
        set_vault_manager(None)
