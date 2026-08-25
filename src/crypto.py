"""
Kriptografik islemler modulu.
AES-256-GCM sifreleme/cozme ve PBKDF2 anahtar turetme islemlerini yonetir.

Bu modul, Encrypted Document Vault sisteminin temelini olusturur.
Tum sifreleme islemleri Python 'cryptography' kutuphanesi ile yapilir.

Kullanim:
    from src.crypto import derive_key, encrypt, decrypt, generate_salt

    salt = generate_salt()
    key = derive_key("master_password", salt)
    encrypted = encrypt("gizli metin", key)
    plaintext = decrypt(encrypted, key)
"""

import os
import base64

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# ── Sabitler ──────────────────────────────────────────────────

# PBKDF2 varsayilan iterasyon sayisi (config'ten override edilebilir)
DEFAULT_PBKDF2_ITERATIONS = 600_000

# AES-256 icin anahtar boyutu (32 byte = 256 bit)
KEY_SIZE = 32

# GCM nonce boyutu (12 byte, NIST onerisi)
NONCE_SIZE = 12

# Salt boyutu (16 byte)
SALT_SIZE = 16


# ── Salt Uretimi ─────────────────────────────────────────────

def generate_salt():
    """
    Kriptografik olarak guvenli rastgele 16-byte salt uretir.

    Returns:
        bytes: 16-byte rastgele salt.
    """
    return os.urandom(SALT_SIZE)


# ── Anahtar Turetme (Key Derivation) ─────────────────────────

def derive_key(password, salt, iterations=None):
    """
    PBKDF2-HMAC-SHA256 ile kullanici sifresinden 256-bit AES anahtari turetir.

    Args:
        password (str): Kullanicinin master sifresi.
        salt (bytes): Rastgele salt degeri (generate_salt() ile uretilir).
        iterations (int, optional): PBKDF2 iterasyon sayisi.
                                    Varsayilan: DEFAULT_PBKDF2_ITERATIONS

    Returns:
        bytes: 32-byte (256-bit) AES anahtari.

    Raises:
        ValueError: password veya salt gecersiz ise.
    """
    if not password:
        raise ValueError("Sifre (password) bos olamaz.")
    if not salt or len(salt) < SALT_SIZE:
        raise ValueError(f"Salt en az {SALT_SIZE} byte olmalidir.")

    if iterations is None:
        iterations = DEFAULT_PBKDF2_ITERATIONS

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=iterations,
    )

    return kdf.derive(password.encode("utf-8"))


# ── AES-256-GCM Sifreleme ────────────────────────────────────

def encrypt(plaintext, key):
    """
    Metni AES-256-GCM ile sifreler.

    Cikti formati: nonce (12 byte) + ciphertext + auth_tag (16 byte)
    Tum bunlar tek bir bytes nesnesinde birlestirilir.

    Args:
        plaintext (str): Sifrelenecek duz metin.
        key (bytes): 32-byte AES anahtari (derive_key() ile uretilir).

    Returns:
        bytes: nonce + sifrelenmis veri + auth_tag.

    Raises:
        ValueError: plaintext veya key gecersiz ise.
        RuntimeError: Sifreleme basarisiz olursa.
    """
    if plaintext is None:
        raise ValueError("Sifrelenecek metin (plaintext) None olamaz.")
    if not key or len(key) != KEY_SIZE:
        raise ValueError(f"Anahtar {KEY_SIZE} byte olmalidir.")

    try:
        nonce = os.urandom(NONCE_SIZE)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        # nonce + ciphertext (ciphertext icinde 16-byte auth_tag var)
        return nonce + ciphertext
    except Exception as e:
        raise RuntimeError(f"Sifreleme basarisiz: {e}") from e


def encrypt_bytes(data, key):
    """
    Ham bytes verisini AES-256-GCM ile sifreler.

    Args:
        data (bytes): Sifrelenecek ham veri.
        key (bytes): 32-byte AES anahtari.

    Returns:
        bytes: nonce + sifrelenmis veri + auth_tag.
    """
    if data is None:
        raise ValueError("Sifrelenecek veri (data) None olamaz.")
    if not key or len(key) != KEY_SIZE:
        raise ValueError(f"Anahtar {KEY_SIZE} byte olmalidir.")

    try:
        nonce = os.urandom(NONCE_SIZE)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, data, None)
        return nonce + ciphertext
    except Exception as e:
        raise RuntimeError(f"Sifreleme basarisiz: {e}") from e


# ── AES-256-GCM Cozme ────────────────────────────────────────

def decrypt(encrypted_data, key):
    """
    AES-256-GCM ile sifrelenmis veriyi cozer.

    Girdi formati: nonce (12 byte) + ciphertext + auth_tag (16 byte)

    Args:
        encrypted_data (bytes): encrypt() fonksiyonunun ciktisi.
        key (bytes): 32-byte AES anahtari (sifreleme ile ayni anahtar).

    Returns:
        str: Cozulmus duz metin.

    Raises:
        ValueError: encrypted_data veya key gecersiz ise.
        RuntimeError: Cozme basarisiz olursa (yanlis anahtar, bozuk veri vb).
    """
    if not encrypted_data:
        raise ValueError("Cozulecek veri (encrypted_data) bos olamaz.")
    if not key or len(key) != KEY_SIZE:
        raise ValueError(f"Anahtar {KEY_SIZE} byte olmalidir.")
    if len(encrypted_data) < NONCE_SIZE + 16:
        raise ValueError("Sifrelenmis veri cok kisa (bozulmus olabilir).")

    try:
        nonce = encrypted_data[:NONCE_SIZE]
        ciphertext = encrypted_data[NONCE_SIZE:]
        aesgcm = AESGCM(key)
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext_bytes.decode("utf-8")
    except Exception as e:
        raise RuntimeError(
            "Sifre cozme basarisiz — yanlis sifre veya bozulmus veri."
        ) from e


def decrypt_bytes(encrypted_data, key):
    """
    AES-256-GCM ile sifrelenmis ham bytes verisini cozer.

    Args:
        encrypted_data (bytes): encrypt_bytes() fonksiyonunun ciktisi.
        key (bytes): 32-byte AES anahtari.

    Returns:
        bytes: Cozulmus ham veri.
    """
    if not encrypted_data:
        raise ValueError("Cozulecek veri (encrypted_data) bos olamaz.")
    if not key or len(key) != KEY_SIZE:
        raise ValueError(f"Anahtar {KEY_SIZE} byte olmalidir.")
    if len(encrypted_data) < NONCE_SIZE + 16:
        raise ValueError("Sifrelenmis veri cok kisa (bozulmus olabilir).")

    try:
        nonce = encrypted_data[:NONCE_SIZE]
        ciphertext = encrypted_data[NONCE_SIZE:]
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, None)
    except Exception as e:
        raise RuntimeError(
            "Sifre cozme basarisiz — yanlis sifre veya bozulmus veri."
        ) from e


# ── Base64 Yardimci Fonksiyonlari ────────────────────────────

def encrypt_to_b64(plaintext, key):
    """
    Metni sifreler ve sonucu base64 string olarak dondurur.
    Qdrant payload'larinda saklamak icin idealdir.

    Args:
        plaintext (str): Sifrelenecek metin.
        key (bytes): 32-byte AES anahtari.

    Returns:
        str: Base64-encoded sifrelenmis veri.
    """
    encrypted = encrypt(plaintext, key)
    return base64.b64encode(encrypted).decode("ascii")


def decrypt_from_b64(encrypted_b64, key):
    """
    Base64-encoded sifrelenmis veriyi cozer.

    Args:
        encrypted_b64 (str): Base64-encoded sifrelenmis veri.
        key (bytes): 32-byte AES anahtari.

    Returns:
        str: Cozulmus duz metin.
    """
    if not encrypted_b64:
        raise ValueError("Cozulecek base64 verisi bos olamaz.")
    encrypted_data = base64.b64decode(encrypted_b64)
    return decrypt(encrypted_data, key)
