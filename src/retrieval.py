"""
Retrieval (belge arama) modulu.
Kullanici sorgusuna en benzer belge parcalarini bulur.
"""

from src import config
from src import database
from src import embeddings


def get_top_chunks(query, top_k=None):
    """
    Kullanici sorgusuna en benzer belge parcalarini Qdrant üzerinden bulur.

    Args:
        query (str): Kullanicinin sorusu.
        top_k (int, optional): Dondurulecek en benzer parca sayisi.
                               Varsayilan: config.TOP_K

    Returns:
        list[dict]: En benzer parcalar, benzerlik skoruna gore azalan
                    sirada. Her eleman su anahtarlari icerir:
            - "id" (str): Veritabani satir ID'si (UUID)
            - "text" (str): Parca metni
            - "source_file" (str): Kaynak dosya adi
            - "chunk_index" (int): Dosya icindeki parca sirasi
            - "score" (float): Cosine similarity skoru

        Veritabani bossa veya eslesme yoksa bos liste doner.
    """
    if query is None or not query.strip():
        raise ValueError("Arama sorgusu bos olamaz.")

    if top_k is None:
        top_k = config.TOP_K

    # 1. Sorguyu embedding'e donustur
    query_embedding = embeddings.get_embedding(query)

    # 2. Veritabaninda dogrudan arama yap
    scored_chunks = database.search_chunks(query_embedding, top_k=top_k)

    return scored_chunks


def format_context(chunks):
    """
    Bulunan parcalari LLM'e gondermek uzere formatlı bir bagLam
    metnine donusturur.
    """
    if not chunks:
        return ""

    parts = []
    for chunk in chunks:
        header = f"[Kaynak: {chunk['source_file']}, Parca: {chunk['chunk_index'] + 1}]"
        parts.append(f"{header}\n{chunk['text']}")

    return "\n\n".join(parts)
