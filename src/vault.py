"""
Encrypted Document Vault yonetim modulu.
Belge sifreleme/cozme, anahtar yonetimi ve vault durumu orkestre eder.

VaultManager sinifi, uygulamanin tum vault islemlerini yonetir:
- Vault olusturma (init) ve sifre dogrulama
- Dosya sifreleme/cozme (.vault uzantili)
- Qdrant payload sifreleme/cozme (base64)
- Vault'a goc (migration) islemi

Kullanim:
    from src.vault import VaultManager

    vm = VaultManager("master_sifre")
    encrypted = vm.encrypt_text("gizli belge icerik")
    plaintext = vm.decrypt_text(encrypted)
"""

import os
import json
import time
import base64
import getpass
import hashlib

from . import config
from . import crypto


# ── Vault Metadata ────────────────────────────────────────────

VAULT_VERSION = "1.0"
VERIFICATION_MARKER = "VAULT_VERIFICATION_OK"


class VaultManager:
    """
    End-to-End Encrypted Document Vault yoneticisi.

    Sorumluluklar:
        - Master sifre ile AES-256 anahtari turetme
        - Metin ve dosya sifreleme/cozme
        - Vault metadata yonetimi (salt, verification)
        - Sifre dogrulama

    Attributes:
        vault_dir (str): Vault dosyalarinin saklandigi klasor.
        key (bytes): PBKDF2 ile turetilmis 32-byte AES anahtari.
        salt (bytes): Anahtar turetmede kullanilan salt.
    """

    def __init__(self, password, vault_dir=None):
        """
        VaultManager'i baslatir.

        Eger vault metadata dosyasi varsa salt'i yukler ve anahtari turetir.
        Yoksa yeni salt olusturur, anahtari turetir ve metadata'yi kaydeder.

        Args:
            password (str): Kullanicinin master sifresi.
            vault_dir (str, optional): Vault klasor yolu.
                                       Varsayilan: config.VAULT_DIR

        Raises:
            ValueError: Sifre bos ise.
            RuntimeError: Vault sifre dogrulamasi basarisiz ise
                         (mevcut vault icin yanlis sifre).
        """
        if not password or not password.strip():
            raise ValueError("Vault sifresi bos olamaz.")

        self.vault_dir = vault_dir or config.VAULT_DIR
        self.meta_path = os.path.join(self.vault_dir, config.VAULT_META_FILE)

        # Vault klasorunu olustur
        os.makedirs(self.vault_dir, exist_ok=True)

        # Metadata yukle veya olustur
        if os.path.exists(self.meta_path):
            # Mevcut vault — salt'i yukle ve dogrula
            meta = self._load_metadata()
            self.salt = base64.b64decode(meta["salt"])
            self.key = crypto.derive_key(
                password, self.salt,
                iterations=config.VAULT_PBKDF2_ITERATIONS
            )
            # Sifre dogrulamasi
            if not self._verify_password(meta):
                raise RuntimeError(
                    "Vault sifresi yanlis! Dogru sifreyi girdiginizden emin olun."
                )
        else:
            # Yeni vault — salt olustur ve metadata kaydet
            self.salt = crypto.generate_salt()
            self.key = crypto.derive_key(
                password, self.salt,
                iterations=config.VAULT_PBKDF2_ITERATIONS
            )
            self._save_metadata()

    # ── Metadata Yonetimi ─────────────────────────────────────

    def _load_metadata(self):
        """Vault metadata dosyasini yukler."""
        try:
            with open(self.meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise RuntimeError(f"Vault metadata okunamadi: {e}") from e

    def _save_metadata(self):
        """Vault metadata dosyasini kaydeder (salt, verification, versiyon)."""
        # Verification: Bilinen bir metni sifreliyoruz.
        # Cozulecegi zaman sifre dogrulama icin kullanilir.
        verification_encrypted = crypto.encrypt_to_b64(
            VERIFICATION_MARKER, self.key
        )

        meta = {
            "version": VAULT_VERSION,
            "salt": base64.b64encode(self.salt).decode("ascii"),
            "verification": verification_encrypted,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "pbkdf2_iterations": config.VAULT_PBKDF2_ITERATIONS,
        }

        try:
            with open(self.meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise RuntimeError(f"Vault metadata kaydedilemedi: {e}") from e

    def _verify_password(self, meta):
        """
        Sifrenin dogru olup olmadigini verification marker ile kontrol eder.

        Args:
            meta (dict): Vault metadata.

        Returns:
            bool: Sifre dogru ise True.
        """
        try:
            decrypted = crypto.decrypt_from_b64(
                meta["verification"], self.key
            )
            return decrypted == VERIFICATION_MARKER
        except Exception:
            return False

    # ── Metin Sifreleme/Cozme ─────────────────────────────────

    def encrypt_text(self, plaintext):
        """
        Metni sifreler ve base64 string olarak dondurur.
        Qdrant payload'larinda saklamak icin idealdir.

        Args:
            plaintext (str): Sifrelenecek metin.

        Returns:
            str: Base64-encoded sifrelenmis veri.
        """
        return crypto.encrypt_to_b64(plaintext, self.key)

    def decrypt_text(self, encrypted_b64):
        """
        Base64-encoded sifrelenmis metni cozer.

        Args:
            encrypted_b64 (str): encrypt_text() ciktisi.

        Returns:
            str: Cozulmus duz metin.
        """
        return crypto.decrypt_from_b64(encrypted_b64, self.key)

    # ── Dosya Sifreleme/Cozme ─────────────────────────────────

    def encrypt_file(self, filepath):
        """
        Bir dosyayi okur, sifreler ve vault klasorune .vault uzantisiyla kaydeder.

        Args:
            filepath (str): Sifrelenecek dosyanin yolu.

        Returns:
            str: Olusturulan .vault dosyasinin yolu.

        Raises:
            FileNotFoundError: Dosya bulunamazsa.
            RuntimeError: Sifreleme basarisiz olursa.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Dosya bulunamadi: {filepath}")

        try:
            with open(filepath, "rb") as f:
                raw_data = f.read()

            encrypted = crypto.encrypt_bytes(raw_data, self.key)

            # Orijinal dosya adini ve uzantisini metadata olarak sakla
            filename = os.path.basename(filepath)
            file_meta = {
                "original_name": filename,
                "original_size": len(raw_data),
                "encrypted_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            }
            meta_json = json.dumps(file_meta).encode("utf-8")

            # Format: [4-byte meta uzunlugu] + [meta JSON] + [sifrelenmis veri]
            meta_len = len(meta_json).to_bytes(4, byteorder="big")

            vault_filename = filename + ".vault"
            vault_path = os.path.join(self.vault_dir, vault_filename)

            with open(vault_path, "wb") as f:
                f.write(meta_len)
                f.write(meta_json)
                f.write(encrypted)

            return vault_path

        except Exception as e:
            raise RuntimeError(f"Dosya sifrelenemedi ({filepath}): {e}") from e

    def decrypt_file(self, vault_filepath):
        """
        .vault dosyasini okur ve icerigini cozer.

        Args:
            vault_filepath (str): .vault dosyasinin yolu.

        Returns:
            tuple: (original_filename, decrypted_content_bytes)

        Raises:
            FileNotFoundError: Dosya bulunamazsa.
            RuntimeError: Cozme basarisiz olursa.
        """
        if not os.path.exists(vault_filepath):
            raise FileNotFoundError(f"Vault dosyasi bulunamadi: {vault_filepath}")

        try:
            with open(vault_filepath, "rb") as f:
                # Meta uzunlugunu oku
                meta_len_bytes = f.read(4)
                meta_len = int.from_bytes(meta_len_bytes, byteorder="big")

                # Meta JSON'u oku
                meta_json = f.read(meta_len)
                file_meta = json.loads(meta_json.decode("utf-8"))

                # Sifrelenmis veriyi oku
                encrypted = f.read()

            decrypted = crypto.decrypt_bytes(encrypted, self.key)

            return file_meta["original_name"], decrypted

        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(
                f"Vault dosyasi cozulemedi ({vault_filepath}): {e}"
            ) from e

    def decrypt_file_to_text(self, vault_filepath):
        """
        .vault dosyasini cozer ve metin olarak dondurur.

        Args:
            vault_filepath (str): .vault dosyasinin yolu.

        Returns:
            tuple: (original_filename, decrypted_text_str)
        """
        filename, raw_bytes = self.decrypt_file(vault_filepath)
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = raw_bytes.decode("latin-1")
        return filename, text

    # ── Yardimci Fonksiyonlar ─────────────────────────────────

    @staticmethod
    def is_vault_file(filepath):
        """Dosyanin vault dosyasi (.vault uzantili) olup olmadigini kontrol eder."""
        return filepath.lower().endswith(".vault")

    def get_vault_status(self):
        """
        Vault durumunu dondurur.

        Returns:
            dict: Vault durum bilgisi.
        """
        vault_files = []
        if os.path.isdir(self.vault_dir):
            vault_files = [
                f for f in os.listdir(self.vault_dir)
                if f.endswith(".vault")
            ]

        return {
            "vault_dir": self.vault_dir,
            "meta_exists": os.path.exists(self.meta_path),
            "vault_files_count": len(vault_files),
            "vault_files": vault_files,
            "version": VAULT_VERSION,
        }

    def migrate_documents(self, documents_dir=None):
        """
        Mevcut sifrenmemis belgeleri vault'a tasir.

        documents/ klasorundeki tum desteklenen dosyalari okur,
        sifreler ve vault/ klasorune kaydeder.

        Args:
            documents_dir (str, optional): Belge klasoru.
                                           Varsayilan: config.DOCUMENTS_DIR

        Returns:
            dict: Goc istatistikleri.
        """
        if documents_dir is None:
            documents_dir = config.DOCUMENTS_DIR

        if not os.path.isdir(documents_dir):
            raise FileNotFoundError(f"Belge klasoru bulunamadi: {documents_dir}")

        import glob

        migrated = []
        failed = []

        for ext in config.SUPPORTED_EXTENSIONS:
            pattern = os.path.join(documents_dir, f"*{ext}")
            for filepath in sorted(glob.glob(pattern)):
                filename = os.path.basename(filepath)
                if filename.startswith("."):
                    continue

                try:
                    vault_path = self.encrypt_file(filepath)
                    migrated.append({
                        "original": filename,
                        "vault_file": os.path.basename(vault_path),
                    })
                    print(f"  [OK] {filename} → vault'a sifrelendi")
                except Exception as e:
                    failed.append({"file": filename, "error": str(e)})
                    print(f"  [HATA] {filename} sifrelenemedi: {e}")

        return {
            "migrated_count": len(migrated),
            "failed_count": len(failed),
            "migrated": migrated,
            "failed": failed,
        }


# ── Modul Seviyesi Yardimci Fonksiyonlar ──────────────────────

# Singleton vault manager (oturum boyunca tekrar sifre sormamak icin)
_vault_manager = None


def get_vault_manager():
    """
    Mevcut oturumdaki VaultManager'i dondurur.
    Henuz olusturulmamissa None dondurur.
    """
    return _vault_manager


def set_vault_manager(manager):
    """
    Modul seviyesinde VaultManager'i ayarlar.
    """
    global _vault_manager
    _vault_manager = manager


def init_vault_interactive():
    """
    Interaktif olarak vault'u baslatir (terminal'den sifre sorar).

    Returns:
        VaultManager: Olusturulan vault manager.
    """
    meta_path = os.path.join(config.VAULT_DIR, config.VAULT_META_FILE)

    if os.path.exists(meta_path):
        print("🔐 Vault sifresini girin:")
        password = getpass.getpass("   Sifre: ")
    else:
        print("🔐 Yeni vault olusturuluyor. Master sifre belirleyin:")
        password = getpass.getpass("   Yeni sifre: ")
        confirm = getpass.getpass("   Sifre tekrar: ")
        if password != confirm:
            raise ValueError("Sifreler eslesmiyor!")
        if len(password) < 8:
            raise ValueError("Sifre en az 8 karakter olmalidir.")

    vm = VaultManager(password)
    set_vault_manager(vm)
    print("🔓 Vault basariyla acildi.\n")
    return vm


def init_vault_with_password(password):
    """
    Programatik olarak vault'u baslatir (UI'dan sifre alindi).

    Args:
        password (str): Vault sifresi.

    Returns:
        VaultManager: Olusturulan vault manager.
    """
    vm = VaultManager(password)
    set_vault_manager(vm)
    return vm
