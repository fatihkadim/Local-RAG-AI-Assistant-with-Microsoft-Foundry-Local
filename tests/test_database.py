import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
"""
Sprint 1 — database.py Manuel Test Scripti

Bu script, database.py'deki tüm fonksiyonları test eder:
1. init_db()        → Veritabanı ve tablo oluşturma
2. insert_chunk()   → Belge parçası ekleme
3. get_all_chunks() → Tüm parçaları okuma
4. clear_db()       → Veritabanını temizleme
5. Edge case'ler    → Boş DB, tekrar init, hatalı girdi
"""

import os
import sys

# Test için mevcut veritabanı dosyasını temizle
from src import config
if os.path.exists(config.DATABASE_PATH):
    os.remove(config.DATABASE_PATH)
    print(f"[TEMIZLIK] Eski {config.DATABASE_PATH} silindi.\n")

from src import database

PASSED = 0
FAILED = 0

def test(name, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  [OK] {name}")
    else:
        FAILED += 1
        print(f"  [FAIL] {name} -- {detail}")


# ─── TEST 1: init_db() ──────────────────────────────────────────
print("=" * 60)
print("TEST 1: init_db()")
print("=" * 60)

database.init_db()
test("DB dosyasi olusturuldu", os.path.exists(config.DATABASE_PATH))

# Tekrar cagirmak guvenli olmali (idempotent)
database.init_db()
test("Tekrar init_db() cagirmak hata vermedi (idempotent)", True)

print()


# ─── TEST 2: insert_chunk() ─────────────────────────────────────
print("=" * 60)
print("TEST 2: insert_chunk()")
print("=" * 60)

test_embedding_1 = [0.1, 0.2, 0.3, 0.4, 0.5]
test_embedding_2 = [0.6, 0.7, 0.8, 0.9, 1.0]
test_embedding_3 = [1.1, 1.2, 1.3, 1.4, 1.5]

database.insert_chunk(
    text="Python bir programlama dilidir.",
    embedding=test_embedding_1,
    source_file="python.txt",
    chunk_index=0
)
test("Ilk chunk eklendi", True)

database.insert_chunk(
    text="Python Guido van Rossum tarafindan gelistirilmistir.",
    embedding=test_embedding_2,
    source_file="python.txt",
    chunk_index=1
)
test("Ikinci chunk (ayni dosya) eklendi", True)

database.insert_chunk(
    text="JavaScript web tarayicilarinda calisir.",
    embedding=test_embedding_3,
    source_file="javascript.md",
    chunk_index=0
)
test("Ucuncu chunk (farkli dosya) eklendi", True)

# Bos text ile eklemeye calisma
try:
    database.insert_chunk(text="", embedding=[1.0], source_file="x.txt", chunk_index=0)
    test("Bos text reddedildi", False, "ValueError beklendi ama hata firlamadi")
except ValueError:
    test("Bos text reddedildi (ValueError)", True)

# Bos embedding ile eklemeye calisma
try:
    database.insert_chunk(text="test", embedding=[], source_file="x.txt", chunk_index=0)
    test("Bos embedding reddedildi", False, "ValueError beklendi ama hata firlamadi")
except ValueError:
    test("Bos embedding reddedildi (ValueError)", True)

print()


# ─── TEST 3: get_all_chunks() ───────────────────────────────────
print("=" * 60)
print("TEST 3: get_all_chunks()")
print("=" * 60)

chunks = database.get_all_chunks()
test("3 chunk donduruldu", len(chunks) == 3, f"Beklenen: 3, Gelen: {len(chunks)}")

# Ilk chunk'in yapisini kontrol et
chunk = chunks[0]
test("'id' alani var", "id" in chunk)
test("'text' alani var", "text" in chunk)
test("'embedding' alani var", "embedding" in chunk)
test("'source_file' alani var", "source_file" in chunk)
test("'chunk_index' alani var", "chunk_index" in chunk)
test("'created_at' alani var", "created_at" in chunk)

# Deger kontrolu
test("text dogru", chunk["text"] == "Python bir programlama dilidir.")
test("source_file dogru", chunk["source_file"] == "python.txt")
test("chunk_index dogru", chunk["chunk_index"] == 0)

# Embedding deserializasyonu kontrolu
test("embedding tipi list", isinstance(chunk["embedding"], list))
test("embedding icerigi dogru", chunk["embedding"] == test_embedding_1,
     f"Beklenen: {test_embedding_1}, Gelen: {chunk['embedding']}")
test("embedding elemanlari float", all(isinstance(v, float) for v in chunk["embedding"]))

# Source file filtreleme (programatik)
python_chunks = [c for c in chunks if c["source_file"] == "python.txt"]
js_chunks = [c for c in chunks if c["source_file"] == "javascript.md"]
test("python.txt icin 2 chunk", len(python_chunks) == 2)
test("javascript.md icin 1 chunk", len(js_chunks) == 1)

print()


# ─── TEST 4: clear_db() ─────────────────────────────────────────
print("=" * 60)
print("TEST 4: clear_db()")
print("=" * 60)

database.clear_db()
chunks_after_clear = database.get_all_chunks()
test("Temizleme sonrasi 0 chunk", len(chunks_after_clear) == 0,
     f"Beklenen: 0, Gelen: {len(chunks_after_clear)}")

# Bos DB'den tekrar okuma
chunks_empty = database.get_all_chunks()
test("Bos DB'den okuma bos liste dondurur", chunks_empty == [])

print()


# ─── TEST 5: Buyuk embedding ────────────────────────────────────
print("=" * 60)
print("TEST 5: Buyuk embedding (1024 boyut)")
print("=" * 60)

big_embedding = [float(i) * 0.001 for i in range(1024)]
database.insert_chunk(
    text="Buyuk embedding testi.",
    embedding=big_embedding,
    source_file="test.txt",
    chunk_index=0
)

chunks = database.get_all_chunks()
test("1024 boyutlu embedding kaydedildi", len(chunks) == 1)
test("Embedding boyutu korundu",
     len(chunks[0]["embedding"]) == 1024,
     f"Beklenen: 1024, Gelen: {len(chunks[0]['embedding'])}")
test("Embedding degerleri korundu",
     chunks[0]["embedding"][:3] == [0.0, 0.001, 0.002])

print()


# ─── SONUC ───────────────────────────────────────────────────────
print("=" * 60)
total = PASSED + FAILED
print(f"SONUC: {PASSED}/{total} test GECTI", end="")
if FAILED > 0:
    print(f", {FAILED} BASARISIZ")
else:
    print(" -- TUMU BASARILI!")
print("=" * 60)

# Temizle — test DB dosyasini sil
database.clear_db()
try:
    if os.path.exists(config.DATABASE_PATH):
        os.remove(config.DATABASE_PATH)
        print(f"\n[TEMIZLIK] Test DB ({config.DATABASE_PATH}) silindi.")
except PermissionError:
    print(f"\n[TEMIZLIK] {config.DATABASE_PATH} silinemedi (dosya kilitli), sorun yok.")

sys.exit(0 if FAILED == 0 else 1)
