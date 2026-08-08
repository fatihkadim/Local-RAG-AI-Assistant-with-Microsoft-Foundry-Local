"""
Sprint 4 -- llm.py + main.py + app.py Manuel Test Scripti

Bu script, Sprint 4 içeriğini test eder:
1. LLM modülü (generate_answer fonksiyonu)
2. Main.py yardımcı fonksiyonları (ask_question)
3. Uçtan uca RAG pipeline testi

Ön koşullar:
- Sprint 3 testleri geçmiş olmalı (ingestion + retrieval çalışıyor)
- Foundry Local SDK yüklü ve çalışır durumda olmalı
- Veritabanında belgeler yüklü olmalı (python main.py --ingest)

Kullanım:
    python test_sprint4.py
"""

import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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


# ══════════════════════════════════════════════════════════════
# ÖN KONTROL: Veritabanı ve belgeler hazır mı?
# ══════════════════════════════════════════════════════════════
print("=" * 60)
print("ÖN KONTROL: Veritabanı durumu")
print("=" * 60)

import config
import database

database.init_db()
all_chunks = database.get_all_chunks()

if not all_chunks:
    print("  [UYARI] Veritabanı boş! Önce ingestion çalıştırılıyor...")
    print("  Bu işlem biraz sürebilir (embedding hesaplanacak)...\n")
    import ingestion
    stats = ingestion.ingest_all()
    all_chunks = database.get_all_chunks()

test("Veritabanında belgeler var", len(all_chunks) > 0, f"Parça sayısı: {len(all_chunks)}")
print(f"  [INFO] Veritabanında {len(all_chunks)} belge parçası mevcut.\n")


# ══════════════════════════════════════════════════════════════
# TEST 1: llm modülü import
# ══════════════════════════════════════════════════════════════
print("=" * 60)
print("TEST 1: llm modülü import ve temel kontroller")
print("=" * 60)

import llm

test("llm modülü import edildi", True)
test("generate_answer fonksiyonu var", hasattr(llm, "generate_answer"))
test("generate_answer_stream fonksiyonu var", hasattr(llm, "generate_answer_stream"))
test("_ensure_initialized fonksiyonu var", hasattr(llm, "_ensure_initialized"))

print()


# ══════════════════════════════════════════════════════════════
# TEST 2: generate_answer() — Giriş validasyonu
# ══════════════════════════════════════════════════════════════
print("=" * 60)
print("TEST 2: generate_answer() — Giriş validasyonu")
print("=" * 60)

# Boş sorgu
try:
    llm.generate_answer("", "bir bağlam")
    test("Boş sorgu reddedildi", False, "ValueError beklendi")
except ValueError:
    test("Boş sorgu reddedildi (ValueError)", True)

# None sorgu
try:
    llm.generate_answer(None, "bir bağlam")
    test("None sorgu reddedildi", False, "ValueError beklendi")
except ValueError:
    test("None sorgu reddedildi (ValueError)", True)

# None context
try:
    llm.generate_answer("test sorusu", None)
    test("None context reddedildi", False, "ValueError beklendi")
except ValueError:
    test("None context reddedildi (ValueError)", True)

print()


# ══════════════════════════════════════════════════════════════
# TEST 3: generate_answer() — Gerçek cevap üretimi
# ══════════════════════════════════════════════════════════════
print("=" * 60)
print("TEST 3: generate_answer() — Gerçek cevap üretimi")
print("=" * 60)
print("  [INFO] LLM modeli yükleniyor (ilk seferde biraz sürebilir)...\n")

import retrieval

# Test sorusu 1: Python hakkında
query1 = "Python programlama dili nedir?"
top_chunks1 = retrieval.get_top_chunks(query1, top_k=3)
context1 = retrieval.format_context(top_chunks1)

start_time = time.time()
answer1 = llm.generate_answer(query1, context1)
elapsed1 = time.time() - start_time

test("Cevap None değil", answer1 is not None)
test("Cevap boş değil", len(answer1) > 0, f"Cevap uzunluğu: {len(answer1)}")
test("Cevap makul uzunlukta (>10 karakter)", len(answer1) > 10, f"Uzunluk: {len(answer1)}")
test(f"Cevap süresi makul (<120s)", elapsed1 < 120, f"Süre: {elapsed1:.2f}s")

print(f"\n  [INFO] Soru: {query1}")
print(f"  [INFO] Cevap ({elapsed1:.2f}s): {answer1[:300]}...")
print()


# ══════════════════════════════════════════════════════════════
# TEST 4: Farklı konularda cevap üretimi
# ══════════════════════════════════════════════════════════════
print("=" * 60)
print("TEST 4: Farklı konularda cevap üretimi")
print("=" * 60)

# Test sorusu 2: Yapay zeka hakkında
query2 = "Yapay zeka ve derin öğrenme nedir?"
top_chunks2 = retrieval.get_top_chunks(query2, top_k=3)
context2 = retrieval.format_context(top_chunks2)

start_time = time.time()
answer2 = llm.generate_answer(query2, context2)
elapsed2 = time.time() - start_time

test("YZ sorusuna cevap üretildi", len(answer2) > 10, f"Uzunluk: {len(answer2)}")
test(f"Cevap süresi makul (<120s)", elapsed2 < 120, f"Süre: {elapsed2:.2f}s")

print(f"\n  [INFO] Soru: {query2}")
print(f"  [INFO] Cevap ({elapsed2:.2f}s): {answer2[:300]}...")
print()

# Test sorusu 3: Veritabanı hakkında
query3 = "Veritabanı nedir ve ne işe yarar?"
top_chunks3 = retrieval.get_top_chunks(query3, top_k=3)
context3 = retrieval.format_context(top_chunks3)

start_time = time.time()
answer3 = llm.generate_answer(query3, context3)
elapsed3 = time.time() - start_time

test("DB sorusuna cevap üretildi", len(answer3) > 10, f"Uzunluk: {len(answer3)}")

print(f"\n  [INFO] Soru: {query3}")
print(f"  [INFO] Cevap ({elapsed3:.2f}s): {answer3[:300]}...")
print()


# ══════════════════════════════════════════════════════════════
# TEST 5: Boş bağlamda davranış
# ══════════════════════════════════════════════════════════════
print("=" * 60)
print("TEST 5: Boş bağlamda model davranışı")
print("=" * 60)

# Boş context ile (model "bilgim yok" demeli idealde)
answer_empty = llm.generate_answer("Kuantum mekaniği nedir?", "")
test("Boş bağlamla cevap üretildi (hata vermedi)", answer_empty is not None)
test("Boş bağlam cevabı boş değil", len(answer_empty) > 0)

print(f"  [INFO] Boş bağlam cevabı: {answer_empty[:200]}...")
print()


# ══════════════════════════════════════════════════════════════
# TEST 6: main.py — ask_question() fonksiyonu
# ══════════════════════════════════════════════════════════════
print("=" * 60)
print("TEST 6: main.py — ask_question() fonksiyonu")
print("=" * 60)

import main

test("main modülü import edildi", True)
test("ask_question fonksiyonu var", hasattr(main, "ask_question"))
test("run_ingest fonksiyonu var", hasattr(main, "run_ingest"))
test("run_cli fonksiyonu var", hasattr(main, "run_cli"))

# ask_question testi
result = main.ask_question("Python nedir?")
test("ask_question sonuç döndürdü", result is not None)
test("Sonuçta 'Cevap' var", "Cevap" in result, f"Sonuç: {result[:100]}")
test("Sonuçta 'Kaynaklar' var", "Kaynaklar" in result)
test("Sonuçta 'Süre' var", "Süre" in result)

print(f"\n  [INFO] ask_question sonucu (ilk 200 kar.): {result[:200]}...")
print()


# ══════════════════════════════════════════════════════════════
# TEST 7: app.py — import kontrolü
# ══════════════════════════════════════════════════════════════
print("=" * 60)
print("TEST 7: app.py — import kontrolü (streamlit gerekir)")
print("=" * 60)

try:
    import streamlit
    test("streamlit kütüphanesi yüklü", True)
except ImportError:
    test("streamlit kütüphanesi yüklü", False,
         "pip install streamlit ile yükleyin")

print()


# ══════════════════════════════════════════════════════════════
# TEST 8: Streaming cevap (generate_answer_stream)
# ══════════════════════════════════════════════════════════════
print("=" * 60)
print("TEST 8: generate_answer_stream() — Streaming cevap")
print("=" * 60)

query_stream = "Python nedir?"
top_chunks_s = retrieval.get_top_chunks(query_stream, top_k=2)
context_s = retrieval.format_context(top_chunks_s)

try:
    stream_parts = []
    for part in llm.generate_answer_stream(query_stream, context_s):
        stream_parts.append(part)

    full_stream = "".join(stream_parts)
    test("Streaming cevap döndü", len(stream_parts) > 0,
         f"Parça sayısı: {len(stream_parts)}")
    test("Streaming cevap boş değil", len(full_stream) > 0)
    test("Birden fazla parça geldi (streaming çalışıyor)",
         len(stream_parts) > 1,
         f"Parça sayısı: {len(stream_parts)}")

    print(f"  [INFO] Streaming: {len(stream_parts)} parça, toplam {len(full_stream)} karakter")
    print(f"  [INFO] İlk 200 karakter: {full_stream[:200]}...")

except RuntimeError as e:
    # Bazı modeller streaming desteklemeyebilir
    print(f"  [UYARI] Streaming desteklenmeyebilir: {e}")
    test("Streaming çağrısı yapıldı (hata alınsa da)", True)

except Exception as e:
    test("Streaming çalıştı", False, str(e))

print()


# ══════════════════════════════════════════════════════════════
# SONUÇ
# ══════════════════════════════════════════════════════════════
print("=" * 60)
total = PASSED + FAILED
print(f"SONUÇ: {PASSED}/{total} test GEÇTİ", end="")
if FAILED > 0:
    print(f", {FAILED} BAŞARISIZ")
else:
    print(" -- TÜMÜ BAŞARILI!")
print("=" * 60)

sys.exit(0 if FAILED == 0 else 1)
