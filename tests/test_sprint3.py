import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
"""
Sprint 3 -- ingestion.py + retrieval.py Manuel Test Scripti
Kullanım: python tests/test_sprint3.py
"""

import os
import sys
import math

PASSED = 0
FAILED = 0

def check(name, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  [OK] {name}")
    else:
        FAILED += 1
        print(f"  [FAIL] {name} -- {detail}")


def main():
    global PASSED, FAILED
    from src import config
    from src import database
    try:
        database.init_db()
    except Exception:
        pass

    # ── TEST 1: load_documents() ────────────────────────────────────
    print("=" * 60)
    print("TEST 1: load_documents() -- Belge okuma")
    print("=" * 60)

    from src import ingestion

    docs = ingestion.load_documents()
    check("Belgeler yuklendi (None degil)", docs is not None)
    check("En az 1 belge okundu", len(docs) >= 1, f"Bulunan: {len(docs)}")

    for doc in docs:
        check(f"'{doc['filename']}' -- filename alani var", "filename" in doc)
        check(f"'{doc['filename']}' -- content alani var", "content" in doc)
        check(f"'{doc['filename']}' -- content bos degil", len(doc["content"]) > 0)

    print()

    # ── TEST 2: chunk_text() ────────────────────────────────────────
    print("=" * 60)
    print("TEST 2: chunk_text() -- Metin parcalama")
    print("=" * 60)

    short_text = "Bu cok kisa bir metin."
    short_chunks = ingestion.chunk_text(short_text, "test.txt")
    check("Kisa metin -> en az 1 parca", len(short_chunks) >= 1)
    check("Parca metni dogru", short_chunks[0]["text"] == short_text)
    check("source_file dogru", short_chunks[0]["source_file"] == "test.txt")
    check("chunk_index 0'dan baslar", short_chunks[0]["chunk_index"] == 0)

    long_text = "Bu bir test cumlesidir. " * 100
    long_chunks = ingestion.chunk_text(long_text, "uzun.txt", chunk_size=500, chunk_overlap=50)
    check("Uzun metin -> birden fazla parca", len(long_chunks) > 1, f"Beklenen: >1, Gelen: {len(long_chunks)}")

    indexes = [c["chunk_index"] for c in long_chunks]
    check("chunk_index'ler sirali", indexes == list(range(len(long_chunks))), f"Indexes: {indexes}")

    try:
        ingestion.chunk_text("", "test.txt")
        check("Bos metin reddedildi", False, "ValueError beklendi")
    except ValueError:
        check("Bos metin reddedildi (ValueError)", True)

    print()

    # ── TEST 3: ingest_all() ────────────────────────────────────────
    print("=" * 60)
    print("TEST 3: ingest_all() -- Tam pipeline")
    print("=" * 60)

    stats = ingestion.ingest_all()
    check("Stats dondu (None degil)", stats is not None)
    check("documents_loaded > 0", stats["documents_loaded"] > 0)
    check("total_chunks > 0", stats["total_chunks"] > 0)
    check("files listesi bos degil", len(stats["files"]) > 0)

    count = database.get_chunk_count()
    check("DB'deki parca sayisi > 0", count > 0, f"DB: {count}")

    print()

    # ── TEST 4: format_context() ────────────────────────────────────
    print("=" * 60)
    print("TEST 4: format_context() -- Baglam formatlama")
    print("=" * 60)

    from src import retrieval
    sample_chunks = [{"source_file": "a.txt", "chunk_index": 0, "text": "ornek"}]
    context = retrieval.format_context(sample_chunks)
    check("Context bos degil", len(context) > 0)
    check("Context '[Kaynak:' iceriyor", "[Kaynak:" in context)

    empty_context = retrieval.format_context([])
    check("Bos liste -> bos string", empty_context == "")

    print()

    # ── SONUC ────────────────────────────────────────────────────────
    print("=" * 60)
    total = PASSED + FAILED
    print(f"SONUC: {PASSED}/{total} test GECTI", end="")
    if FAILED > 0:
        print(f", {FAILED} BASARISIZ")
    else:
        print(" -- TUMU BASARILI!")
    print("=" * 60)

    sys.exit(0 if FAILED == 0 else 1)


if __name__ == "__main__":
    main()
