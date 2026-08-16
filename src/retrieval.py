"""
Retrieval (belge arama) modulu.
Kullanici sorgusuna en benzer belge parcalarini bulur.
"""

from src import config
from src import database
from src import embeddings
from src.telemetry import trace_span
import time


def get_top_chunks(query, top_k=None, trace_ctx=None):
    """
    Kullanici sorgusuna en benzer belge parcalarini Qdrant üzerinden bulur.
    OpenTelemetry span'leri ve detaylı zaman kırılımları ile izlenir.

    Args:
        query (str): Kullanicinin sorusu.
        top_k (int, optional): Dondurulecek en benzer parca sayisi.
                               Varsayilan: config.TOP_K
        trace_ctx (QueryTraceContext, optional): Canli tracing baglami.

    Returns:
        list[dict]: En benzer parcalar, benzerlik skoruna gore azalan sirada.
    """
    if query is None or not query.strip():
        raise ValueError("Arama sorgusu bos olamaz.")

    if top_k is None:
        top_k = config.TOP_K

    retrieval_start = time.time()

    with trace_span("rag.retrieval", {"rag.top_k": top_k, "rag.query": query[:100]}):
        # 1. Sorguyu embedding'e donustur
        embed_start = time.time()
        with trace_span("rag.embedding.query", {"text_len": len(query)}):
            query_embedding = embeddings.get_embedding(query)
        embed_duration = (time.time() - embed_start) * 1000.0

        # 2. Veritabaninda dogrudan arama yap
        search_start = time.time()
        with trace_span("rag.qdrant.search", {"top_k": top_k, "embedding_dim": len(query_embedding)}):
            scored_chunks = database.search_chunks(query_embedding, top_k=top_k)
        search_duration = (time.time() - search_start) * 1000.0

    retrieval_total = (time.time() - retrieval_start) * 1000.0

    if trace_ctx:
        trace_ctx.retrieval_ms = retrieval_total
        trace_ctx.embedding_query_ms = embed_duration
        trace_ctx.qdrant_search_ms = search_duration
        trace_ctx.chunks_count = len(scored_chunks)

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
