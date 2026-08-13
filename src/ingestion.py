"""
Belge yukleme ve parcalama (ingestion) modulu.
documents/ klasorundeki belgeleri okur, parcalara boler,
embedding'lerini hesaplar ve SQLite'a kaydeder.

Kullanim:
    from src.ingestion import ingest_all

    stats = ingest_all()
    print(f"{stats['total_chunks']} parca yuklendi.")
"""

import os
import glob

from src import config
from src import database
from src import embeddings


# ── Belge Yukleme ─────────────────────────────────────────────

def load_documents(directory=None):
    """
    Belirtilen klasordeki .txt ve .md dosyalarini okur.

    Args:
        directory (str, optional): Belgelerin bulundugu klasor yolu.
                                   Varsayilan: config.DOCUMENTS_DIR

    Returns:
        list[dict]: Her eleman su anahtarlari icerir:
            - "filename" (str): Dosya adi (orn: "python_temelleri.txt")
            - "content" (str): Dosyanin tam metni

    Raises:
        FileNotFoundError: Belirtilen klasor bulunamazsa.
        ValueError: Klasorde hic desteklenen belge yoksa.
    """
    if directory is None:
        directory = config.DOCUMENTS_DIR

    if not os.path.isdir(directory):
        raise FileNotFoundError(
            f"Belge klasoru bulunamadi: {directory}"
        )

    # Desteklenen dosya uzantilari
    supported_extensions = [".txt", ".md", ".pdf"]
    documents = []

    for ext in supported_extensions:
        pattern = os.path.join(directory, f"*{ext}")
        for filepath in sorted(glob.glob(pattern)):
            filename = os.path.basename(filepath)

            # .gitkeep gibi ozel dosyalari atla
            if filename.startswith("."):
                continue

            try:
                if ext == ".pdf":
                    try:
                        import pymupdf
                        doc = pymupdf.open(filepath)
                        page_texts = [
                            page.get_text() for page in doc
                        ]
                        content = "\n\n".join(page_texts).strip()
                        if not content:
                            print(f"  [UYARI] {filename} metin icermiyor (taratilmis PDF olabilir), atlaniyor.")
                            continue
                    except Exception as pdf_err:
                        print(f"  [UYARI] {filename} PDF okuma hatasi ({pdf_err}), atlaniyor.")
                        continue
                else:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read().strip()

                # Bos dosyalari atla
                if not content:
                    print(f"  [UYARI] {filename} bos, atlaniyor.")
                    continue

                documents.append({
                    "filename": filename,
                    "content": content,
                })
                print(f"  [OK] {filename} okundu ({len(content)} karakter)")

            except UnicodeDecodeError:
                print(f"  [UYARI] {filename} okunamadi (encoding hatasi), atlaniyor.")
                continue

    if not documents:
        raise ValueError(
            f"'{directory}' klasorunde desteklenen belge bulunamadi. "
            f"Desteklenen uzantilar: {supported_extensions}"
        )

    return documents


# ── Chunk Kalite Filtresi ─────────────────────────────────────

def _is_quality_chunk(text):
    """
    Bir metin parcasinin yeterli kalitede olup olmadigini kontrol eder.
    Bozuk PDF metinleri, matematik formulleri, XML tag'leri gibi
    anlamsiz icerikleri filtreler.

    Returns:
        bool: True ise parca kaliteli, False ise atlanmali.
    """
    if not text or len(text.strip()) < 20:
        return False

    # Alfanumerik karakter oranini hesapla
    alnum_count = sum(1 for c in text if c.isalnum() or c.isspace())
    total_count = len(text)
    if total_count == 0:
        return False

    alnum_ratio = alnum_count / total_count

    # Cok fazla ozel karakter varsa (formul, bozuk metin)
    if alnum_ratio < 0.5:
        return False

    # XML/markup tag'leri iceriyorsa
    markup_indicators = ["[open]", "[close]", "[sep]", "<sep>", "end_of_msg", "role=\""]
    markup_count = sum(1 for ind in markup_indicators if ind in text.lower())
    if markup_count >= 2:
        return False

    # En az 3 kelime icermeli (anlamli metin)
    words = text.split()
    if len(words) < 3:
        return False

    return True


# ── Metin Parcalama (Chunking) ────────────────────────────────

def chunk_text(text, source_file, chunk_size=None, chunk_overlap=None):
    """
    Bir metni belirli boyutta, ortusme ile parcalara boler.

    Parcalama stratejisi:
    - Her parca yaklasik chunk_size karakter uzunlugundadir.
    - Parcalar arasi chunk_overlap karakter ortusme vardir.
    - Ortusme, baglam kaybini onler (cumle ortasindan bolunmeleri tolere eder).

    Args:
        text (str): Parcalanacak metin.
        source_file (str): Kaynak dosya adi (parcalarla birlikte kaydedilir).
        chunk_size (int, optional): Parca uzunlugu. Varsayilan: config.CHUNK_SIZE
        chunk_overlap (int, optional): Ortusme miktari. Varsayilan: config.CHUNK_OVERLAP

    Returns:
        list[dict]: Her eleman su anahtarlari icerir:
            - "text" (str): Parca metni
            - "source_file" (str): Kaynak dosya adi
            - "chunk_index" (int): Dosya icindeki parca sirasi (0'dan baslar)

    Raises:
        ValueError: text bos veya None ise.
    """
    if not text or not text.strip():
        raise ValueError("Parcalanacak metin bos olamaz.")

    if chunk_size is None:
        chunk_size = config.CHUNK_SIZE
    if chunk_overlap is None:
        chunk_overlap = config.CHUNK_OVERLAP

    chunks = []
    start = 0
    chunk_index = 0

    while start < len(text):
        end = start + chunk_size

        # Metni cumlelerden bolmeye calis (daha dogal kesim)
        if end < len(text):
            # Parca bitisinden geriye dogru cumle sonu isareti ara
            search_region = text[max(start, end - 100):end]
            # Son cumle sonu isaretini bul
            last_period = -1
            for sep in [". ", ".\n", "? ", "?\n", "! ", "!\n", "\n\n"]:
                pos = search_region.rfind(sep)
                if pos > last_period:
                    last_period = pos

            if last_period > 0:
                # Cumle sonundan bol (ayiracin kendisi dahil)
                end = max(start, end - 100) + last_period + 1

        chunk_text_piece = text[start:end].strip()

        if chunk_text_piece and _is_quality_chunk(chunk_text_piece):
            chunks.append({
                "text": chunk_text_piece,
                "source_file": source_file,
                "chunk_index": chunk_index,
            })
            chunk_index += 1

        # Sonraki parcaya gec (ortusme ile)
        start = end - chunk_overlap if end < len(text) else end

    return chunks


# ── Ana Ingestion Pipeline ────────────────────────────────────

def ingest_all(directory=None, clear_existing=True):
    """
    Tam ingestion pipeline'ini calistirir:
    1. documents/ klasorundeki belgeleri okur
    2. Her belgeyi parcalara boler
    3. Her parca icin embedding uretir (Foundry Local SDK ile)
    4. Parcalari ve embedding'leri SQLite'a kaydeder

    Args:
        directory (str, optional): Belge klasoru. Varsayilan: config.DOCUMENTS_DIR
        clear_existing (bool): True ise mevcut verileri siler.
                               Varsayilan: True

    Returns:
        dict: Islem istatistikleri:
            - "documents_loaded" (int): Okunan belge sayisi
            - "total_chunks" (int): Toplam parca sayisi
            - "files" (list[str]): Islenen dosya adlari

    Raises:
        FileNotFoundError: Belge klasoru bulunamazsa.
        ValueError: Hic belge bulunamazsa.
        RuntimeError: Embedding veya veritabani islemi basarisiz olursa.
    """
    print("\n" + "=" * 60)
    print("INGESTION PIPELINE BASLATILIYOR")
    print("=" * 60)

    # 1. Veritabanini hazirla
    print("\n[1/4] Veritabani hazirlaniyor...")
    if clear_existing:
        database.clear_db()
        print("  [OK] Mevcut veriler temizlendi.")
    database.init_db()

    # 2. Belgeleri oku
    print(f"\n[2/4] Belgeler okunuyor ({directory or config.DOCUMENTS_DIR})...")
    documents = load_documents(directory)
    print(f"  [OK] {len(documents)} belge okundu.")

    # 3. Belgeleri parcala
    print("\n[3/4] Belgeler parcalaniyor...")
    all_chunks = []
    for doc in documents:
        doc_chunks = chunk_text(doc["content"], doc["filename"])
        all_chunks.extend(doc_chunks)
        print(f"  [OK] {doc['filename']} -> {len(doc_chunks)} parca")

    print(f"  [TOPLAM] {len(all_chunks)} parca olusturuldu.")

    # 4. Embedding uret ve veritabanina kaydet
    print("\n[4/4] Embedding'ler uretiliyor ve kaydediliyor...")
    chunk_texts = [chunk["text"] for chunk in all_chunks]
    total_chunks = len(all_chunks)

    # Parcalar halinde embedding uretip kaydet (ilerleme takibi icin)
    STEP_SIZE = 16
    all_embeddings = []
    for start_idx in range(0, total_chunks, STEP_SIZE):
        step_texts = chunk_texts[start_idx:start_idx + STEP_SIZE]
        step_embeddings = embeddings.get_embeddings_batch(step_texts)
        all_embeddings.extend(step_embeddings)
        current_done = len(all_embeddings)
        print(f"  [{current_done}/{total_chunks}] parca embed edildi...")

    # Her parcayi veritabanina kaydet
    for chunk, embedding in zip(all_chunks, all_embeddings):
        database.insert_chunk(
            text=chunk["text"],
            embedding=embedding,
            source_file=chunk["source_file"],
            chunk_index=chunk["chunk_index"],
        )

    files = [doc["filename"] for doc in documents]
    stats = {
        "documents_loaded": len(documents),
        "total_chunks": len(all_chunks),
        "files": files,
    }

    print(f"\n  [OK] {stats['total_chunks']} parca veritabanina kaydedildi.")

    print("\n" + "=" * 60)
    print("INGESTION TAMAMLANDI")
    print(f"  Belge: {stats['documents_loaded']}")
    print(f"  Parca: {stats['total_chunks']}")
    print(f"  Dosyalar: {', '.join(stats['files'])}")
    print("=" * 60 + "\n")

    return stats
