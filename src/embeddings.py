"""
Embedding hizmetleri modulu.
Foundry Local SDK kullanarak metin embedding'leri olusturur.

Bu modul, herhangi bir metin girdisi icin embedding vektorleri uretir.
Hem tek metin hem de toplu (batch) embedding uretimini destekler.
Ingestion pipeline (Sprint 3) ve retrieval sistemi (Sprint 4)
bu servise bagimlidir.

Kullanim:
    from src.embeddings import get_embedding, get_embeddings_batch

    vektor = get_embedding("Merhaba dunya")
    vektorler = get_embeddings_batch(["metin1", "metin2", "metin3"])
"""

from src import config
from src.sdk_manager import get_manager

# ── Modul Seviyesi Degiskenler (Lazy Initialization) ─────────
# Embedding client ilk kullanimda olusturulur.
_embedding_client = None


def _ensure_initialized():
    """
    Embedding modelini baslatir (lazy init).

    Ilk cagirildinginda:
    1. SDK manager'dan FoundryLocalManager instance'ini alir
    2. Embedding modelini (config.EMBEDDING_MODEL) yukler
    3. EmbeddingClient'i olusturur

    Sonraki cagrilarda mevcut instance'lari kullanir (tekrar yuklemez).

    Raises:
        RuntimeError: SDK initialize edilemezse veya model yuklenemezse.
    """
    global _embedding_client

    if _embedding_client is not None:
        return

    try:
        manager = get_manager()

        # Embedding modelini indir (yoksa) ve yukle
        model = manager.catalog.get_model(config.EMBEDDING_MODEL)
        model.download()
        model.load()

        # Embedding client'i olustur
        _embedding_client = model.get_embedding_client()

    except Exception as e:
        raise RuntimeError(
            f"Embedding servisi baslatılamadi "
            f"(model: {config.EMBEDDING_MODEL}): {e}"
        ) from e


def get_embedding(text):
    """
    Tek bir metin parcasi icin embedding vektoru uretir.

    Args:
        text (str): Embedding'i hesaplanacak metin.
                    Bos string veya None olmamalidir.

    Returns:
        list[float]: Embedding vektoru. Boyutu kullanilan modele
                     baglidir (ornegin qwen3-embedding-0.6b icin 1024).

    Raises:
        ValueError: text None veya bos string ise.
        RuntimeError: SDK veya model yuklenemezse.

    Ornek:
        >>> vektor = get_embedding("Python bir programlama dilidir.")
        >>> print(len(vektor))   # 1024
        >>> print(type(vektor))  # <class 'list'>
    """
    if text is None:
        raise ValueError("Embedding hesaplanamaz: text None olamaz.")
    if not text.strip():
        raise ValueError("Embedding hesaplanamaz: text bos olamaz.")

    _ensure_initialized()

    try:
        response = _embedding_client.generate_embedding(text)
        embedding = response.data[0].embedding
        return list(embedding)
    except Exception as e:
        raise RuntimeError(
            f"Embedding hesaplanamadi: {e}"
        ) from e


def get_embeddings_batch(texts):
    """
    Birden fazla metin icin tek seferde embedding vektorleri uretir.

    Giris sirasini korur: texts[0]'in embedding'i sonuc[0]'dir.
    Buyuk batch'ler otomatik olarak parcalara ayrilir (her parca
    en fazla BATCH_SIZE metin icerir) bellek tasmasini onlemek icin.

    Args:
        texts (list[str]): Embedding'leri hesaplanacak metinler listesi.
                           Bos liste olmamali, elemanlar bos string olmamali.

    Returns:
        list[list[float]]: Her metin icin bir embedding vektoru.
                           len(sonuc) == len(texts) garanti edilir.

    Raises:
        ValueError: texts None, bos liste ise veya icerisinde bos metin varsa.
        RuntimeError: SDK veya model yuklenemezse.

    Ornek:
        >>> metinler = ["Python hizlidir.", "Java derlenebilir."]
        >>> vektorler = get_embeddings_batch(metinler)
        >>> print(len(vektorler))     # 2
        >>> print(len(vektorler[0]))  # 1024
    """
    if texts is None:
        raise ValueError("Batch embedding hesaplanamaz: texts None olamaz.")
    if not texts:
        raise ValueError("Batch embedding hesaplanamaz: texts bos liste olamaz.")

    # Her metnin gecerli oldugundan emin ol
    for i, text in enumerate(texts):
        if text is None or not text.strip():
            raise ValueError(
                f"Batch embedding hesaplanamaz: texts[{i}] bos veya None."
            )

    _ensure_initialized()

    BATCH_SIZE = 32  # GPU/NPU paralelizasyonu icin optimize edilmis batch boyutu
    all_embeddings = []

    try:
        # Buyuk listeleri parcalar halinde isle
        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start:start + BATCH_SIZE]
            try:
                response = _embedding_client.generate_embeddings(batch)
                batch_embeddings = [list(item.embedding) for item in response.data]
            except Exception:
                # Toplu embedding ONNX bellek hatasi verirse daha kucuk (8'lik) batch dene
                batch_embeddings = []
                SUB_BATCH = 8
                for sub_start in range(0, len(batch), SUB_BATCH):
                    sub_batch = batch[sub_start:sub_start + SUB_BATCH]
                    try:
                        resp = _embedding_client.generate_embeddings(sub_batch)
                        batch_embeddings.extend([list(item.embedding) for item in resp.data])
                    except Exception:
                        for text_item in sub_batch:
                            response_single = _embedding_client.generate_embedding(text_item)
                            batch_embeddings.append(list(response_single.data[0].embedding))

            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    except Exception as e:
        raise RuntimeError(
            f"Batch embedding hesaplanamadi: {e}"
        ) from e
