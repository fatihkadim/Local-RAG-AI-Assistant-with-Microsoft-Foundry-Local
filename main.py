"""
Local RAG AI Assistant — Ana Giriş Noktası (CLI modu)
Microsoft Foundry Local ile tamamen offline çalışan Q&A chatbot.

Desteklenen dosya formatları:
    .txt, .md, .pdf, .docx, .pptx, .html, .htm, .csv, .tsv,
    .xlsx, .xls, .epub, .json, .jsonl, .rst

Kullanım:
    python main.py --ingest     → Belgeleri yükle ve veritabanını oluştur
    python main.py              → Soru-Cevap modunu başlat (CLI)
    python main.py --ingest -q "Python nedir?"  → Yükle + tek soru sor

Vault Komutları:
    python main.py --vault-init     → Yeni vault oluştur (ilk kez şifre belirle)
    python main.py --vault-migrate  → Mevcut belgeleri vault'a şifreli taşı
    python main.py --vault-status   → Vault durumunu göster
    python main.py --ingest         → Vault aktifken şifreli ingestion
"""

import argparse
import sys
import time

# Windows terminalinin varsayilan cp1254 encoding'i emoji/Unicode karakterleri
# desteklemeyebilir. Stdout'u UTF-8'e zorlayarak tum print cagrilarinin
# sorunsuz calismasini sagliyoruz.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from src import config
from src import database
from src import ingestion
from src import retrieval
from src import llm


def _ensure_vault():
    """
    Vault aktifse interaktif olarak vault'u baslatir.
    Zaten aciksa tekrar sormaz.
    """
    if not config.VAULT_ENABLED:
        return

    from src.vault import get_vault_manager, init_vault_interactive
    if get_vault_manager() is None:
        init_vault_interactive()


def run_vault_init():
    """Yeni vault olusturur veya mevcut vault'u dogrular."""
    from src.vault import init_vault_interactive
    print("\n" + "=" * 60)
    print("  🔐 ENCRYPTED DOCUMENT VAULT — İLK KURULUM")
    print("=" * 60 + "\n")
    try:
        vm = init_vault_interactive()
        status = vm.get_vault_status()
        print(f"\n✅ Vault hazır!")
        print(f"   Klasör: {status['vault_dir']}")
        print(f"   Şifreli dosya: {status['vault_files_count']}")
        print(f"   Versiyon: {status['version']}\n")
    except Exception as e:
        print(f"\n❌ Vault oluşturulamadı: {e}\n")
        sys.exit(1)


def run_vault_migrate():
    """Mevcut sifrenmemis belgeleri vault'a goc ettirir."""
    from src.vault import init_vault_interactive

    print("\n" + "=" * 60)
    print("  🔐 VAULT GÖÇ — Belgeleri Şifreli Olarak Taşı")
    print("=" * 60 + "\n")

    try:
        vm = init_vault_interactive()
        print(f"\n📂 '{config.DOCUMENTS_DIR}/' klasöründeki belgeler vault'a taşınıyor...\n")
        stats = vm.migrate_documents()

        print("\n" + "=" * 60)
        print("GÖÇ TAMAMLANDI")
        print(f"  Taşınan belge  : {stats['migrated_count']}")
        print(f"  Başarısız       : {stats['failed_count']}")
        print("=" * 60 + "\n")

        if stats['migrated_count'] > 0:
            print("💡 Artık şifreli belgeleri kullanmak için normal ingestion çalıştırın:")
            print("   python main.py --ingest\n")

    except Exception as e:
        print(f"\n❌ Göç başarısız: {e}\n")
        sys.exit(1)


def run_vault_status():
    """Vault durumunu gosterir."""
    import os

    print("\n" + "=" * 60)
    print("  🔐 VAULT DURUM BİLGİSİ")
    print("=" * 60 + "\n")

    vault_meta_path = os.path.join(config.VAULT_DIR, config.VAULT_META_FILE)

    if not os.path.exists(vault_meta_path):
        print("  ⚪ Vault henüz oluşturulmamış.")
        print("  Oluşturmak için: python main.py --vault-init\n")
        return

    try:
        from src.vault import init_vault_interactive
        vm = init_vault_interactive()
        status = vm.get_vault_status()

        print(f"  🟢 Vault Aktif")
        print(f"  Klasör         : {status['vault_dir']}")
        print(f"  Versiyon       : {status['version']}")
        print(f"  Şifreli dosya  : {status['vault_files_count']}")
        if status['vault_files']:
            print(f"  Dosyalar:")
            for vf in status['vault_files'][:10]:
                print(f"    • {vf}")
            if len(status['vault_files']) > 10:
                print(f"    ... ve {len(status['vault_files']) - 10} dosya daha")
        print()

    except Exception as e:
        print(f"  ❌ Vault durumu okunamadı: {e}\n")


def run_ingest(force=False):
    """
    Ingestion pipeline'ını çalıştırır.
    documents/ klasöründeki belgeleri okur, parçalar,
    embedding hesaplar ve Qdrant'a kaydeder.
    Vault aktifken şifreli belgeler de işlenir.
    """
    # Vault aktifse önce vault'u aç
    _ensure_vault()

    try:
        stats = ingestion.ingest_all(clear_existing=force)
        print(f"\n✅ Ingestion tamamlandı: Toplam {stats['total_chunks']} parça veritabanında.")
        return True
    except FileNotFoundError as e:
        print(f"\n❌ Hata: {e}")
        print(f"   '{config.DOCUMENTS_DIR}/' klasörüne .txt veya .md dosyaları ekleyin.")
        return False
    except ValueError as e:
        print(f"\n❌ Hata: {e}")
        return False
    except RuntimeError as e:
        print(f"\n❌ SDK Hatası: {e}")
        print("   Foundry Local SDK'nın doğru yüklendiğinden emin olun.")
        return False


from src.telemetry import start_query_trace, init_telemetry


def ask_question(query):
    """
    Tek bir soruyu RAG pipeline ile cevaplar.
    OpenTelemetry Trace ID ve zaman çizelgesi (waterfall) bilgisi üretir.

    Args:
        query (str): Kullanıcının sorusu.

    Returns:
        str: Cevap metni veya hata mesajı.
    """
    # Veritabanı kontrolü
    try:
        chunk_count = database.get_chunk_count()
        if not chunk_count:
            return (
                "⚠️ Veritabanı boş! Önce belgeleri yükleyin:\n"
                "   python main.py --ingest"
            )
    except Exception:
        return (
            "⚠️ Veritabanı bulunamadı! Önce belgeleri yükleyin:\n"
            "   python main.py --ingest"
        )

    with start_query_trace(query) as trace_ctx:
        # 1. En ilgili parçaları bul
        top_chunks = retrieval.get_top_chunks(query, trace_ctx=trace_ctx)

        if not top_chunks:
            return "Bu konuda veritabanında bilgi bulunamadı."

        # 2. Bağlam oluştur
        context = retrieval.format_context(top_chunks)

        # 3. LLM'den cevap üret
        print("\n⏳ Cevap üretiliyor...\n")
        answer = llm.generate_answer(query, context, trace_ctx=trace_ctx)

    # Sonuçları göster
    result = []
    result.append("─" * 50)
    result.append(f"📝 Cevap:\n{answer}")
    result.append("─" * 50)
    result.append(f"\n📚 Kaynaklar:")
    for chunk in top_chunks:
        result.append(
            f"   • {chunk['source_file']} "
            f"(parça {chunk['chunk_index'] + 1}, "
            f"skor: {chunk['score']:.4f})"
        )
    
    # Observability & Trace bilgisi
    result.append(f"\n📊 Observability:")
    result.append(f"   • Trace ID : {trace_ctx.trace_id}")
    result.append(f"   • Toplam   : {trace_ctx.total_ms:.1f}ms")
    result.append(f"   • Arama    : {trace_ctx.retrieval_ms:.1f}ms (Embed: {trace_ctx.embedding_query_ms:.1f}ms | Qdrant: {trace_ctx.qdrant_search_ms:.1f}ms)")
    result.append(f"   • LLM      : {trace_ctx.llm_generation_ms:.1f}ms ({trace_ctx.tokens_count} kelime/token)")

    return "\n".join(result)


def run_cli():
    """
    İnteraktif CLI sohbet döngüsünü başlatır.
    Kullanıcıdan soru alır, RAG pipeline ile cevaplar,
    'çık', 'exit' veya 'q' girilene kadar devam eder.
    """
    # Vault aktifse önce vault'u aç
    _ensure_vault()

    print("\n" + "═" * 60)
    print("  🤖 Local RAG AI Assistant")
    print("  Microsoft Foundry Local ile çalışır (tamamen offline)")
    print("═" * 60)
    print(f"  Model  : {config.CHAT_MODEL}")
    print(f"  DB     : {config.QDRANT_URL} ({config.QDRANT_COLLECTION})")
    print(f"  Top-K  : {config.TOP_K}")
    if config.VAULT_ENABLED:
        print(f"  Vault  : 🔒 Aktif (E2E Encrypted)")
    print("─" * 60)
    print("  Çıkmak için: 'çık', 'exit' veya 'q' yazın")
    print("═" * 60 + "\n")

    # Veritabanı kontrolü
    try:
        chunk_count = database.get_chunk_count()
        if not chunk_count:
            print("⚠️ Veritabanı boş! Önce belgeleri yükleyin:")
            print("   python main.py --ingest\n")
            return
        print(f"📊 Veritabanında {chunk_count} belge parçası mevcut.\n")
    except Exception:
        print("⚠️ Veritabanı bulunamadı! Önce belgeleri yükleyin:")
        print("   python main.py --ingest\n")
        return

    # Sohbet döngüsü
    while True:
        try:
            query = input("📌 Sorunuz: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n👋 Görüşmek üzere!")
            break

        # Çıkış komutları
        if query.lower() in ("çık", "exit", "q", "quit", "kapat"):
            print("\n👋 Görüşmek üzere!")
            break

        # Boş girdi
        if not query:
            print("  ⚠️ Lütfen bir soru yazın.\n")
            continue

        # Soruyu cevapla
        try:
            answer = ask_question(query)
            print(answer)
            print()  # Boş satır
        except Exception as e:
            print(f"\n❌ Hata: {e}\n")


def main():
    """Ana fonksiyon — komut satırı argümanlarını işler."""
    parser = argparse.ArgumentParser(
        description="Local RAG AI Assistant — Offline Q&A Chatbot (E2E Encrypted Vault)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python main.py --ingest           Belgeleri yükle (vault aktifse şifre sorar)
  python main.py                    Sohbet modunu başlat
  python main.py -q "Python nedir?" Tek soru sor

Vault Komutları:
  python main.py --vault-init       Yeni vault oluştur
  python main.py --vault-migrate    Mevcut belgeleri vault'a şifreli taşı
  python main.py --vault-status     Vault durumunu göster
        """
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Belgeleri yükle (akıllı artımlı mod - sadece yeni/değişen belgeler işlenir)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="--ingest ile birlikte kullanılırsa tüm veritabanını ve önbelleği sıfırlayıp baştan yükler"
    )
    parser.add_argument(
        "-q", "--query",
        type=str,
        help="Tek bir soru sor (sohbet moduna girmeden)"
    )
    parser.add_argument(
        "--vault-init",
        action="store_true",
        help="Yeni encrypted vault oluştur (ilk kez şifre belirle)"
    )
    parser.add_argument(
        "--vault-migrate",
        action="store_true",
        help="Mevcut şifresiz belgeleri vault'a şifreli olarak taşı"
    )
    parser.add_argument(
        "--vault-status",
        action="store_true",
        help="Vault durumunu göster (şifreli dosya sayısı vb.)"
    )

    args = parser.parse_args()

    # Vault komutları (öncelikli)
    if args.vault_init:
        run_vault_init()
        return

    if args.vault_migrate:
        run_vault_migrate()
        return

    if args.vault_status:
        run_vault_status()
        return

    # Veritabanını initialize et
    database.init_db()

    # --ingest modu
    if args.ingest:
        success = run_ingest(force=args.force)
        if not success:
            sys.exit(1)

    # -q ile tek soru
    if args.query:
        _ensure_vault()
        try:
            answer = ask_question(args.query)
            print(answer)
        except Exception as e:
            print(f"❌ Hata: {e}")
            sys.exit(1)
    elif not args.ingest:
        # Argüman yoksa → interaktif CLI
        run_cli()


if __name__ == "__main__":
    main()
