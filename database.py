"""
Veritabanı (veri kalıcılık) katmanı.
SQLite kullanarak belge parçalarını (chunk) ve embedding vektörlerini
kaydetme, okuma ve silme işlemlerini yönetir.

Bu modül, projenin temel veri katmanıdır. Diğer tüm modüller
(ingestion, retrieval) veritabanı işlemleri için bu modülü kullanır.
"""

import sqlite3
import json
from datetime import datetime

import config


def init_db():
    """
    Veritabanını ve 'documents' tablosunu oluşturur.

    - config.DATABASE_PATH'teki yolda SQLite veritabanı dosyasını oluşturur.
    - 'documents' tablosu yoksa yeni oluşturur (CREATE TABLE IF NOT EXISTS).
    - Birden fazla çağrılması güvenlidir (idempotent).

    Tablo şeması:
        id            INTEGER PRIMARY KEY AUTOINCREMENT
        text          TEXT NOT NULL       — Belge parçasının metni
        embedding     TEXT NOT NULL       — JSON formatında embedding vektörü
        source_file   TEXT NOT NULL       — Kaynak dosya adı (ör: "konu1.txt")
        chunk_index   INTEGER NOT NULL    — Aynı dosyadaki parça sırası (0, 1, 2...)
        created_at    TEXT NOT NULL       — Ekleme tarihi (ISO 8601 formatı)

    Raises:
        sqlite3.OperationalError: Veritabanı dosyası oluşturulamaz veya
                                   yazma izni yoksa.
    """
    try:
        with sqlite3.connect(config.DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    source_file TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
            ''')
            conn.commit()
    except sqlite3.OperationalError as e:
        raise sqlite3.OperationalError(
            f"Veritabanı oluşturulamadı ({config.DATABASE_PATH}): {e}"
        ) from e


def insert_chunk(text, embedding, source_file, chunk_index):
    """
    Bir belge parçasını (chunk) ve embedding vektörünü veritabanına ekler.

    Args:
        text (str): Belge parçasının metni.
        embedding (list[float]): Embedding vektörü (ör: 1024 boyutlu float listesi).
        source_file (str): Kaynak dosya adı (ör: "konu1.txt").
        chunk_index (int): Aynı dosyadaki parça sırası (0'dan başlar).

    Raises:
        ValueError: text veya embedding boş/None ise.
        sqlite3.OperationalError: Veritabanına yazılamıyorsa.
        sqlite3.IntegrityError: NOT NULL kısıtlaması ihlal ediliyorsa.
    """
    if not text:
        raise ValueError("Belge parçası metni (text) boş olamaz.")
    if not embedding:
        raise ValueError("Embedding vektörü boş olamaz.")

    json_embedding = json.dumps(embedding)
    created_at = datetime.now().isoformat()

    try:
        with sqlite3.connect(config.DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO documents (text, embedding, source_file, chunk_index, created_at)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (text, json_embedding, source_file, chunk_index, created_at)
            )
            conn.commit()
    except sqlite3.OperationalError as e:
        raise sqlite3.OperationalError(
            f"Belge parçası eklenemedi: {e}"
        ) from e
    except sqlite3.IntegrityError as e:
        raise sqlite3.IntegrityError(
            f"Veri bütünlüğü hatası (NOT NULL ihlali?): {e}"
        ) from e


def get_all_chunks():
    """
    Veritabanındaki tüm belge parçalarını okur ve döndürür.

    Her satır için embedding JSON'dan deserialize edilerek
    list[float] tipine dönüştürülür.

    Returns:
        list[dict]: Her eleman şu anahtarları içeren bir dict:
            - "id" (int): Veritabanı satır ID'si
            - "text" (str): Belge parçasının metni
            - "embedding" (list[float]): Embedding vektörü
            - "source_file" (str): Kaynak dosya adı
            - "chunk_index" (int): Dosya içi parça sırası
            - "created_at" (str): Ekleme tarihi (ISO 8601)

        Veritabanı boşsa boş liste döner.

    Raises:
        sqlite3.OperationalError: Veritabanı veya tablo bulunamazsa.
    """
    try:
        with sqlite3.connect(config.DATABASE_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM documents')
            rows = cursor.fetchall()

            chunks = []
            for row in rows:
                chunks.append({
                    "id": row["id"],
                    "text": row["text"],
                    "embedding": json.loads(row["embedding"]),
                    "source_file": row["source_file"],
                    "chunk_index": row["chunk_index"],
                    "created_at": row["created_at"],
                })
            return chunks

    except sqlite3.OperationalError as e:
        raise sqlite3.OperationalError(
            f"Belge parçaları okunamadı: {e}"
        ) from e


def clear_db():
    """
    'documents' tablosundaki tüm verileri siler.

    Yeniden ingestion senaryosu için kullanılır. Silme işleminden
    sonra VACUUM çalıştırarak disk alanını geri kazanır.

    Not: Tablo yapısı (şema) korunur, sadece veriler silinir.

    Raises:
        sqlite3.OperationalError: Veritabanı veya tablo bulunamazsa.
    """
    try:
        with sqlite3.connect(config.DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM documents')
            conn.commit()
            cursor.execute('VACUUM')
    except sqlite3.OperationalError as e:
        raise sqlite3.OperationalError(
            f"Veritabanı temizlenemedi: {e}"
        ) from e