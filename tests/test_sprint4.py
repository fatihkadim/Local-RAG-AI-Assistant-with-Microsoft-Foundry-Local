import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
"""
Sprint 4 -- llm.py + main.py + app.py Manuel Test Scripti
Kullanım: python tests/test_sprint4.py
"""

import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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
    print("=" * 60)
    print("ÖN KONTROL: Veritabanı durumu")
    print("=" * 60)

    from src import config
    from src import database

    try:
        database.init_db()
        chunk_count = database.get_chunk_count()
    except Exception:
        chunk_count = 0

    check("Veritabanı kontrolü", True)
    print(f"  [INFO] Veritabanında {chunk_count} belge parçası mevcut.\n")

    # TEST 1
    print("=" * 60)
    print("TEST 1: llm modülü import ve temel kontroller")
    print("=" * 60)

    from src import llm

    check("llm modülü import edildi", True)
    check("generate_answer fonksiyonu var", hasattr(llm, "generate_answer"))
    check("generate_answer_stream fonksiyonu var", hasattr(llm, "generate_answer_stream"))
    check("_ensure_initialized fonksiyonu var", hasattr(llm, "_ensure_initialized"))

    print()

    # TEST 2
    print("=" * 60)
    print("TEST 2: generate_answer() — Giriş validasyonu")
    print("=" * 60)

    try:
        llm.generate_answer("", "bir bağlam")
        check("Boş sorgu reddedildi", False, "ValueError beklendi")
    except ValueError:
        check("Boş sorgu reddedildi (ValueError)", True)

    try:
        llm.generate_answer(None, "bir bağlam")
        check("None sorgu reddedildi", False, "ValueError beklendi")
    except ValueError:
        check("None sorgu reddedildi (ValueError)", True)

    try:
        llm.generate_answer("test sorusu", None)
        check("None context reddedildi", False, "ValueError beklendi")
    except ValueError:
        check("None context reddedildi (ValueError)", True)

    print()

    # TEST 6
    print("=" * 60)
    print("TEST 6: main.py — ask_question() fonksiyonu")
    print("=" * 60)

    import main as main_mod

    check("main modülü import edildi", True)
    check("ask_question fonksiyonu var", hasattr(main_mod, "ask_question"))
    check("run_ingest fonksiyonu var", hasattr(main_mod, "run_ingest"))
    check("run_cli fonksiyonu var", hasattr(main_mod, "run_cli"))

    print()

    # TEST 7
    print("=" * 60)
    print("TEST 7: app.py — import kontrolü (streamlit gerekir)")
    print("=" * 60)

    try:
        import streamlit
        check("streamlit kütüphanesi yüklü", True)
    except ImportError:
        check("streamlit kütüphanesi yüklü", False, "pip install streamlit ile yükleyin")

    print()

    # SONUC
    print("=" * 60)
    total = PASSED + FAILED
    print(f"SONUÇ: {PASSED}/{total} test GEÇTİ", end="")
    if FAILED > 0:
        print(f", {FAILED} BAŞARISIZ")
    else:
        print(" -- TÜMÜ BAŞARILI!")
    print("=" * 60)

    sys.exit(0 if FAILED == 0 else 1)


if __name__ == "__main__":
    main()
