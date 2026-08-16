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


def run_ingest(force=False):
    """
    Ingestion pipeline'ını çalıştırır.
    documents/ klasöründeki belgeleri okur, parçalar,
    embedding hesaplar ve Qdrant'a kaydeder.
    """
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
    print("\n" + "═" * 60)
    print("  🤖 Local RAG AI Assistant")
    print("  Microsoft Foundry Local ile çalışır (tamamen offline)")
    print("═" * 60)
    print(f"  Model  : {config.CHAT_MODEL}")
    print(f"  DB     : {config.QDRANT_URL} ({config.QDRANT_COLLECTION})")
    print(f"  Top-K  : {config.TOP_K}")
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
        description="Local RAG AI Assistant — Offline Q&A Chatbot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python main.py --ingest           Belgeleri yükle
  python main.py                    Sohbet modunu başlat
  python main.py -q "Python nedir?" Tek soru sor
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

    args = parser.parse_args()

    # Veritabanını initialize et
    database.init_db()

    # --ingest modu
    if args.ingest:
        success = run_ingest(force=args.force)
        if not success:
            sys.exit(1)

    # -q ile tek soru
    if args.query:
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
