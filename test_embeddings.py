"""
Sprint 2 -- embeddings.py Manuel Test Scripti

Bu script, embeddings.py'deki tum fonksiyonlari test eder:
1. Lazy initialization (SDK ve model yukleme)
2. get_embedding() -- Tek metin icin embedding
3. get_embeddings_batch() -- Toplu embedding
4. Edge case'ler -- Bos metin, None, bos liste
5. Benzer metinlerin embedding'lerinin yakin oldugu

Not: Bu test Foundry Local SDK'nin yuklu ve calisir durumda olmasini gerektirir.
"""

import sys
import math

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


def cosine_similarity(vec_a, vec_b):
    """Iki vektor arasindaki cosine similarity hesapla (test yardimcisi)."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── TEST 1: get_embedding() ─────────────────────────────────────
print("=" * 60)
print("TEST 1: get_embedding() -- Tek metin embedding")
print("=" * 60)

import embeddings

embedding1 = embeddings.get_embedding("Python bir programlama dilidir.")
test("Embedding dondu (None degil)", embedding1 is not None)
test("Embedding tipi list", isinstance(embedding1, list))
test("Embedding bos degil", len(embedding1) > 0)
test("Embedding elemanlari float", all(isinstance(v, float) for v in embedding1))

embedding_dim = len(embedding1)
print(f"  [INFO] Embedding boyutu: {embedding_dim}")

# Ikinci bir embedding
embedding2 = embeddings.get_embedding("JavaScript web tarayicilarinda calisir.")
test("Ikinci embedding ayni boyutta",
     len(embedding2) == embedding_dim,
     f"Beklenen: {embedding_dim}, Gelen: {len(embedding2)}")

print()


# ── TEST 2: get_embeddings_batch() ──────────────────────────────
print("=" * 60)
print("TEST 2: get_embeddings_batch() -- Toplu embedding")
print("=" * 60)

metinler = [
    "Kediler tatli hayvanlardir.",
    "Python populer bir dildir.",
    "Bugun hava gunesli.",
]

batch_result = embeddings.get_embeddings_batch(metinler)
test("Batch sonuc tipi list", isinstance(batch_result, list))
test("Batch sonuc sayisi dogru",
     len(batch_result) == len(metinler),
     f"Beklenen: {len(metinler)}, Gelen: {len(batch_result)}")

# Her embedding ayni boyutta mi?
sizes = [len(emb) for emb in batch_result]
test("Tum embedding'ler ayni boyutta",
     len(set(sizes)) == 1,
     f"Boyutlar: {sizes}")
test("Batch embedding boyutu tek embedding ile ayni",
     sizes[0] == embedding_dim,
     f"Batch: {sizes[0]}, Tek: {embedding_dim}")

print()


# ── TEST 3: Benzerlik Kontrolu ──────────────────────────────────
print("=" * 60)
print("TEST 3: Benzer metinlerin embedding yakınligi")
print("=" * 60)

emb_kedi1 = embeddings.get_embedding("Kediler tatli hayvanlardir.")
emb_kedi2 = embeddings.get_embedding("Kediler sevimli canlilardir.")
emb_hava = embeddings.get_embedding("Bugun hava cok sicak.")

sim_benzer = cosine_similarity(emb_kedi1, emb_kedi2)
sim_farkli = cosine_similarity(emb_kedi1, emb_hava)

print(f"  [INFO] Benzer metinler arasi similarity: {sim_benzer:.4f}")
print(f"  [INFO] Farkli metinler arasi similarity: {sim_farkli:.4f}")

test("Benzer metinler daha yuksek similarity",
     sim_benzer > sim_farkli,
     f"Benzer: {sim_benzer:.4f}, Farkli: {sim_farkli:.4f}")

print()


# ── TEST 4: Edge Case'ler ───────────────────────────────────────
print("=" * 60)
print("TEST 4: Edge case'ler -- Hatali girdiler")
print("=" * 60)

# Bos string
try:
    embeddings.get_embedding("")
    test("Bos string reddedildi", False, "ValueError beklendi")
except ValueError:
    test("Bos string reddedildi (ValueError)", True)

# None
try:
    embeddings.get_embedding(None)
    test("None reddedildi", False, "ValueError beklendi")
except ValueError:
    test("None reddedildi (ValueError)", True)

# Sadece bosluk
try:
    embeddings.get_embedding("   ")
    test("Sadece bosluk reddedildi", False, "ValueError beklendi")
except ValueError:
    test("Sadece bosluk reddedildi (ValueError)", True)

# Bos liste batch
try:
    embeddings.get_embeddings_batch([])
    test("Bos liste reddedildi", False, "ValueError beklendi")
except ValueError:
    test("Bos liste reddedildi (ValueError)", True)

# None batch
try:
    embeddings.get_embeddings_batch(None)
    test("None batch reddedildi", False, "ValueError beklendi")
except ValueError:
    test("None batch reddedildi (ValueError)", True)

# Batch icerisinde bos eleman
try:
    embeddings.get_embeddings_batch(["gecerli metin", ""])
    test("Batch icinde bos metin reddedildi", False, "ValueError beklendi")
except ValueError:
    test("Batch icinde bos metin reddedildi (ValueError)", True)

print()


# ── TEST 5: Manager tekrar initialize edilmiyor mu? ─────────────
print("=" * 60)
print("TEST 5: Lazy initialization -- Manager tekrar yuklenmemeli")
print("=" * 60)

# _embedding_client None degilse, zaten initialize edilmis demektir
test("Embedding client initialize edilmis",
     embeddings._embedding_client is not None)

# Tekrar get_embedding cagirmak crash etmemeli
emb_test = embeddings.get_embedding("Test metni.")
test("Tekrar cagirilinca sorun yok", emb_test is not None and len(emb_test) > 0)

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
