"""
Sprint 3 -- ingestion.py + retrieval.py Manuel Test Scripti

Bu script, Sprint 3 icerigini test eder:
1. Ingestion Pipeline (belge yukleme, parcalama, embedding, kaydetme)
2. Retrieval (cosine similarity ile en benzer parcalari bulma)
3. Uçtan uca test (belge yukle -> sorgu yap -> sonuc al)

Not: Bu test Foundry Local SDK'nin yuklu ve calisir durumda olmasini gerektirir.
"""

import os
import sys
import math

# Test icin mevcut veritabanini temizle
import config
if os.path.exists(config.DATABASE_PATH):
    os.remove(config.DATABASE_PATH)
    print(f"[TEMIZLIK] Eski {config.DATABASE_PATH} silindi.\n")

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


# ── TEST 1: load_documents() ────────────────────────────────────
print("=" * 60)
print("TEST 1: load_documents() -- Belge okuma")
print("=" * 60)

import ingestion

docs = ingestion.load_documents()
test("Belgeler yuklendi (None degil)", docs is not None)
test("En az 1 belge okundu", len(docs) >= 1, f"Bulunan: {len(docs)}")

# Her belgenin dogru yapida oldugunu kontrol et
for doc in docs:
    test(f"'{doc['filename']}' -- filename alani var", "filename" in doc)
    test(f"'{doc['filename']}' -- content alani var", "content" in doc)
    test(f"'{doc['filename']}' -- content bos degil", len(doc["content"]) > 0)

print()


# ── TEST 2: chunk_text() ────────────────────────────────────────
print("=" * 60)
print("TEST 2: chunk_text() -- Metin parcalama")
print("=" * 60)

# Kisa metin (tek parca olmali)
short_text = "Bu cok kisa bir metin."
short_chunks = ingestion.chunk_text(short_text, "test.txt")
test("Kisa metin -> en az 1 parca", len(short_chunks) >= 1)
test("Parca metni dogru", short_chunks[0]["text"] == short_text)
test("source_file dogru", short_chunks[0]["source_file"] == "test.txt")
test("chunk_index 0'dan baslar", short_chunks[0]["chunk_index"] == 0)

# Uzun metin (birden fazla parca olmali)
long_text = "Bu bir test cumlesidir. " * 100  # ~2400 karakter
long_chunks = ingestion.chunk_text(long_text, "uzun.txt", chunk_size=500, chunk_overlap=50)
test("Uzun metin -> birden fazla parca",
     len(long_chunks) > 1,
     f"Beklenen: >1, Gelen: {len(long_chunks)}")

# chunk_index sirali mi?
indexes = [c["chunk_index"] for c in long_chunks]
test("chunk_index'ler sirali",
     indexes == list(range(len(long_chunks))),
     f"Indexes: {indexes}")

# Bos metin hata vermeli
try:
    ingestion.chunk_text("", "test.txt")
    test("Bos metin reddedildi", False, "ValueError beklendi")
except ValueError:
    test("Bos metin reddedildi (ValueError)", True)

print()


# ── TEST 3: ingest_all() ────────────────────────────────────────
print("=" * 60)
print("TEST 3: ingest_all() -- Tam pipeline")
print("=" * 60)

stats = ingestion.ingest_all()
test("Stats dondu (None degil)", stats is not None)
test("documents_loaded > 0", stats["documents_loaded"] > 0)
test("total_chunks > 0", stats["total_chunks"] > 0)
test("files listesi bos degil", len(stats["files"]) > 0)

print(f"  [INFO] {stats['documents_loaded']} belge, {stats['total_chunks']} parca")
print(f"  [INFO] Dosyalar: {', '.join(stats['files'])}")

# DB'de gercekten veri var mi?
import database
all_chunks = database.get_all_chunks()
test("DB'deki parca sayisi stats ile eslesir",
     len(all_chunks) == stats["total_chunks"],
     f"DB: {len(all_chunks)}, Stats: {stats['total_chunks']}")

# Embedding'ler kayitli mi?
first_chunk = all_chunks[0]
test("Ilk parca embedding iceriyor",
     len(first_chunk["embedding"]) > 0,
     "Embedding bos!")
test("Embedding boyutu makul (>100)",
     len(first_chunk["embedding"]) > 100,
     f"Boyut: {len(first_chunk['embedding'])}")

print()


# ── TEST 4: cosine_similarity() ─────────────────────────────────
print("=" * 60)
print("TEST 4: cosine_similarity() -- Vektor benzerligi")
print("=" * 60)

import retrieval

# Ayni vektor -> similarity = 1.0
vec = [1.0, 2.0, 3.0]
sim_same = retrieval.cosine_similarity(vec, vec)
test("Ayni vektor similarity ~= 1.0",
     abs(sim_same - 1.0) < 0.0001,
     f"Beklenen: 1.0, Gelen: {sim_same}")

# Ortogonal vektorler -> similarity = 0.0
vec_a = [1.0, 0.0]
vec_b = [0.0, 1.0]
sim_ortho = retrieval.cosine_similarity(vec_a, vec_b)
test("Ortogonal vektorler similarity ~= 0.0",
     abs(sim_ortho) < 0.0001,
     f"Beklenen: 0.0, Gelen: {sim_ortho}")

# Zit vektorler -> similarity = -1.0
vec_c = [1.0, 0.0]
vec_d = [-1.0, 0.0]
sim_opposite = retrieval.cosine_similarity(vec_c, vec_d)
test("Zit vektorler similarity ~= -1.0",
     abs(sim_opposite + 1.0) < 0.0001,
     f"Beklenen: -1.0, Gelen: {sim_opposite}")

# Hata kontrolleri
try:
    retrieval.cosine_similarity(None, [1.0])
    test("None vektor reddedildi", False, "ValueError beklendi")
except ValueError:
    test("None vektor reddedildi (ValueError)", True)

try:
    retrieval.cosine_similarity([1.0], [1.0, 2.0])
    test("Farkli boyut reddedildi", False, "ValueError beklendi")
except ValueError:
    test("Farkli boyut reddedildi (ValueError)", True)

print()


# ── TEST 5: get_top_chunks() ────────────────────────────────────
print("=" * 60)
print("TEST 5: get_top_chunks() -- Belge arama")
print("=" * 60)

# Python ile ilgili soru
results = retrieval.get_top_chunks("Python programlama dili nedir?", top_k=3)
test("Sonuclar dondu", results is not None)
test("En az 1 sonuc var", len(results) >= 1, f"Gelen: {len(results)}")
test("En fazla 3 sonuc var (top_k=3)", len(results) <= 3)

# Sonuc yapisi kontrol
if results:
    r = results[0]
    test("'id' alani var", "id" in r)
    test("'text' alani var", "text" in r)
    test("'source_file' alani var", "source_file" in r)
    test("'score' alani var", "score" in r)
    test("Score 0-1 arasinda", 0.0 <= r["score"] <= 1.0,
         f"Score: {r['score']}")

    print(f"  [INFO] En iyi eslesme: {r['source_file']} (score: {r['score']:.4f})")
    print(f"  [INFO] Metin (ilk 100 kar.): {r['text'][:100]}...")

# Sonuclar skora gore sirali mi?
if len(results) >= 2:
    scores = [r["score"] for r in results]
    test("Sonuclar azalan skora gore sirali",
         all(scores[i] >= scores[i+1] for i in range(len(scores)-1)),
         f"Skorlar: {scores}")

print()


# ── TEST 6: Farkli sorgular farkli sonuclar getirmeli ─────────
print("=" * 60)
print("TEST 6: Farkli sorgular -> farkli en iyi sonuclar")
print("=" * 60)

q1_results = retrieval.get_top_chunks("Python web gelistirme Django Flask", top_k=1)
q2_results = retrieval.get_top_chunks("Yapay zeka makine ogrenimi derin ogrenme", top_k=1)
q3_results = retrieval.get_top_chunks("SQLite veritabani SQL sorgu", top_k=1)

if q1_results:
    print(f"  [INFO] Python sorgusu -> {q1_results[0]['source_file']} (score: {q1_results[0]['score']:.4f})")
if q2_results:
    print(f"  [INFO] YZ sorgusu -> {q2_results[0]['source_file']} (score: {q2_results[0]['score']:.4f})")
if q3_results:
    print(f"  [INFO] DB sorgusu -> {q3_results[0]['source_file']} (score: {q3_results[0]['score']:.4f})")

# En azindan farkli kaynaklar dondurmeli (kesin garanti degil ama beklenti)
sources = set()
if q1_results:
    sources.add(q1_results[0]["source_file"])
if q2_results:
    sources.add(q2_results[0]["source_file"])
if q3_results:
    sources.add(q3_results[0]["source_file"])

test("Farkli sorgular en az 2 farkli kaynak dondurdu",
     len(sources) >= 2,
     f"Kaynaklar: {sources}")

print()


# ── TEST 7: format_context() ────────────────────────────────────
print("=" * 60)
print("TEST 7: format_context() -- Baglam formatlama")
print("=" * 60)

context = retrieval.format_context(results)
test("Context bos degil", len(context) > 0)
test("Context '[Kaynak:' iceriyor", "[Kaynak:" in context)

# Bos liste ile
empty_context = retrieval.format_context([])
test("Bos liste -> bos string", empty_context == "")

print()


# ── TEST 8: Edge case'ler ───────────────────────────────────────
print("=" * 60)
print("TEST 8: Edge case'ler")
print("=" * 60)

# Bos sorgu
try:
    retrieval.get_top_chunks("")
    test("Bos sorgu reddedildi", False, "ValueError beklendi")
except ValueError:
    test("Bos sorgu reddedildi (ValueError)", True)

# None sorgu
try:
    retrieval.get_top_chunks(None)
    test("None sorgu reddedildi", False, "ValueError beklendi")
except ValueError:
    test("None sorgu reddedildi (ValueError)", True)

# Olmayan klasor
try:
    ingestion.load_documents("olmayan_klasor")
    test("Olmayan klasor reddedildi", False, "FileNotFoundError beklendi")
except FileNotFoundError:
    test("Olmayan klasor reddedildi (FileNotFoundError)", True)

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
