"""
Retrieval (belge arama) modulu.
Kullanici sorgusuna en benzer belge parcalarini bulur.
Cosine similarity kullanarak vektor benzerligi hesaplar.

Kullanim:
    from retrieval import get_top_chunks

    sonuclar = get_top_chunks("Python nedir?")
    for sonuc in sonuclar:
        print(sonuc["text"], sonuc["score"])
"""

import math

import config
import database
import embeddings


def cosine_similarity(vec_a, vec_b):
    """
    Iki vektor arasindaki cosine similarity degerini hesaplar.

    Cosine similarity, iki vektorun yonlerinin ne kadar benzer
    oldugunu olcer. Deger -1 ile 1 arasindadir:
    - 1.0  → Tamamen ayni yon (en benzer)
    - 0.0  → Ortogonal (ilgisiz)
    - -1.0 → Tam zit yon

    Args:
        vec_a (list[float]): Birinci vektor.
        vec_b (list[float]): Ikinci vektor.

    Returns:
        float: Cosine similarity degeri [-1, 1] araliginda.

    Raises:
        ValueError: Vektorler None, bos veya farkli boyuttaysa.
    """
    if vec_a is None or vec_b is None:
        raise ValueError("Vektorler None olamaz.")
    if len(vec_a) == 0 or len(vec_b) == 0:
        raise ValueError("Vektorler bos olamaz.")
    if len(vec_a) != len(vec_b):
        raise ValueError(
            f"Vektor boyutlari eslesmiyor: {len(vec_a)} vs {len(vec_b)}"
        )

    # Dot product
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))

    # Norm (buyukluk) hesapla
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    # Sifir vektoru kontrolu
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot_product / (norm_a * norm_b)


def get_top_chunks(query, top_k=None):
    """
    Kullanici sorgusuna en benzer belge parcalarini bulur ve dondurur.

    Islem adimlari:
    1. Sorguyu embedding'e donusturur (Foundry Local SDK)
    2. Veritabanindan tum parcalari ve embedding'lerini okur
    3. Sorgu embedding'i ile her parca embedding'i arasinda
       cosine similarity hesaplar
    4. En yuksek benzerlik skoruna sahip top_k parcayi dondurur

    Args:
        query (str): Kullanicinin sorusu.
        top_k (int, optional): Dondurulecek en benzer parca sayisi.
                               Varsayilan: config.TOP_K

    Returns:
        list[dict]: En benzer parcalar, benzerlik skoruna gore azalan
                    sirada. Her eleman su anahtarlari icerir:
            - "id" (int): Veritabani satir ID'si
            - "text" (str): Parca metni
            - "source_file" (str): Kaynak dosya adi
            - "chunk_index" (int): Dosya icindeki parca sirasi
            - "score" (float): Cosine similarity skoru

        Veritabani bossa bos liste doner.

    Raises:
        ValueError: query None veya bos ise.
        RuntimeError: Embedding hesaplanamaz veya DB okunamazsa.
    """
    if query is None or not query.strip():
        raise ValueError("Arama sorgusu bos olamaz.")

    if top_k is None:
        top_k = config.TOP_K

    # 1. Sorguyu embedding'e donustur
    query_embedding = embeddings.get_embedding(query)

    # 2. Veritabanindan tum parcalari oku
    all_chunks = database.get_all_chunks()

    if not all_chunks:
        return []

    # 3. Her parca icin benzerlik skoru hesapla
    scored_chunks = []
    for chunk in all_chunks:
        score = cosine_similarity(query_embedding, chunk["embedding"])
        scored_chunks.append({
            "id": chunk["id"],
            "text": chunk["text"],
            "source_file": chunk["source_file"],
            "chunk_index": chunk["chunk_index"],
            "score": score,
        })

    # 4. Skora gore azalan sirada sirala ve top_k tane dondur
    scored_chunks.sort(key=lambda x: x["score"], reverse=True)

    return scored_chunks[:top_k]


def format_context(chunks):
    """
    Bulunan parcalari LLM'e gondermek uzere formatlı bir bagLam
    metnine donusturur.

    Args:
        chunks (list[dict]): get_top_chunks()'tan donen parcalar.

    Returns:
        str: Formatlanmis baglam metni. Her parca kaynak dosya adi
             ve sira numarasi ile etiketlenmistir.

    Ornek cikti:
        [Kaynak: python.txt, Parca: 1]
        Python bir programlama dilidir...

        [Kaynak: python.txt, Parca: 2]
        Python Guido van Rossum tarafindan...
    """
    if not chunks:
        return ""

    parts = []
    for chunk in chunks:
        header = f"[Kaynak: {chunk['source_file']}, Parca: {chunk['chunk_index'] + 1}]"
        parts.append(f"{header}\n{chunk['text']}")

    return "\n\n".join(parts)
