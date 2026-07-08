"""
Local RAG AI Assistant — Ana Giriş Noktası (CLI modu)
Microsoft Foundry Local ile tamamen offline çalışan Q&A chatbot.

Kullanım:
    python main.py --ingest     → Belgeleri yükle ve veritabanını oluştur
    python main.py              → Soru-Cevap modunu başlat (CLI)
"""

# TODO: Ana uygulama mantığı burada implemente edilecek
#
# 1. argparse ile komut satırı argümanlarını al
#    --ingest  → ingestion.ingest_all() çalıştır
#    (argümansız) → CLI sohbet döngüsünü başlat
#
# 2. CLI sohbet döngüsü:
#    while True:
#        query = input("Sorunuz: ")
#        if query in ("çık", "exit", "q"):
#            break
#        chunks = retrieval.get_top_chunks(query)
#        context = "\n".join(chunks)
#        answer = llm.generate_answer(query, context)
#        print(answer)


if __name__ == "__main__":
    pass  # TODO: main() fonksiyonunu çağır
