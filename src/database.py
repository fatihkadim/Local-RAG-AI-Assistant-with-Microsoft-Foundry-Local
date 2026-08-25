"""
Veritabanı (veri kalıcılık) katmanı.
Qdrant kullanarak belge parçalarını (chunk) ve embedding vektörlerini
kaydetme, okuma ve arama işlemlerini yönetir.

Encrypted Document Vault Entegrasyonu:
    - VAULT_ENCRYPT_PAYLOADS aktifken chunk metinleri şifreli kaydedilir
    - Arama sonuçları otomatik olarak decrypt edilir
"""

from qdrant_client import QdrantClient
from qdrant_client.http import models
import uuid

from . import config
from .telemetry import trace_span

# Qdrant client'ı başlat
client = QdrantClient(url=config.QDRANT_URL, check_compatibility=False)


def _get_vault_manager():
    """Aktif VaultManager'i dondurur (yoksa None)."""
    if not config.VAULT_ENABLED or not config.VAULT_ENCRYPT_PAYLOADS:
        return None
    try:
        from .vault import get_vault_manager
        return get_vault_manager()
    except ImportError:
        return None


def init_db():
    """
    Qdrant veritabanını ve koleksiyonu başlatır.
    Eğer koleksiyon yoksa oluşturur.
    Not: Vektör boyutu embedding modelinize uygun olmalıdır (örneğin 1024).
    """
    try:
        # Vektör boyutunu Foundry Local SDK'nın qwen3-embedding-0.6b modeline göre 1024 alıyoruz.
        VECTOR_SIZE = 1024

        collections = [col.name for col in client.get_collections().collections]
        if config.QDRANT_COLLECTION not in collections:
            client.create_collection(
                collection_name=config.QDRANT_COLLECTION,
                vectors_config=models.VectorParams(
                    size=VECTOR_SIZE,
                    distance=models.Distance.COSINE
                )
            )
    except Exception as e:
        raise RuntimeError(f"Qdrant koleksiyonu oluşturulamadı: {e}") from e


def clear_db():
    """
    Qdrant koleksiyonunu siler (içindeki tüm verilerle birlikte).
    """
    try:
        collections = [col.name for col in client.get_collections().collections]
        if config.QDRANT_COLLECTION in collections:
            client.delete_collection(collection_name=config.QDRANT_COLLECTION)
    except Exception as e:
        raise RuntimeError(f"Qdrant koleksiyonu silinemedi: {e}") from e


def _encrypt_payload_text(text):
    """Vault aktifken metni sifreler, degilse aynen dondurur."""
    vm = _get_vault_manager()
    if vm:
        return vm.encrypt_text(text)
    return text


def _decrypt_payload_text(text):
    """Vault aktifken metni cozer, degilse aynen dondurur."""
    vm = _get_vault_manager()
    if vm:
        try:
            return vm.decrypt_text(text)
        except Exception:
            # Sifrelenmemis eski veri olabilir, aynen dondur
            return text
    return text


def insert_chunk(text, embedding, source_file, chunk_index):
    """
    Bir belge parçasını (chunk) ve embedding vektörünü Qdrant'a ekler.
    Vault aktifken metin payload'u şifrelenmiş olarak kaydedilir.
    """
    if not text:
        raise ValueError("Belge parçası metni (text) boş olamaz.")
    if not embedding:
        raise ValueError("Embedding vektörü boş olamaz.")

    # Benzersiz bir UUID oluştur
    point_id = str(uuid.uuid4())

    # Vault aktifken metni sifrele
    stored_text = _encrypt_payload_text(text)

    payload = {
        "text": stored_text,
        "source_file": source_file,
        "chunk_index": chunk_index,
        "encrypted": _get_vault_manager() is not None,
    }

    try:
        client.upsert(
            collection_name=config.QDRANT_COLLECTION,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload
                )
            ]
        )
    except Exception as e:
        raise RuntimeError(f"Qdrant'a chunk eklenemedi: {e}") from e


def insert_chunks_batch(chunks_data):
    """
    Birden fazla belge parçasını tek bir toplu (bulk) işlemle Qdrant'a ekler.
    Tek tek HTTP istekleri atmak yerine tek bir ağ çağrısında kaydeder (10x-50x daha hızlı).
    Vault aktifken metin payload'ları şifrelenmiş olarak kaydedilir.
    
    Args:
        chunks_data (list[dict]): Her eleman şu anahtarları içermelidir:
            - "text" (str)
            - "embedding" (list[float])
            - "source_file" (str)
            - "chunk_index" (int)
    """
    if not chunks_data:
        return

    is_encrypted = _get_vault_manager() is not None

    points = []
    for item in chunks_data:
        point_id = str(uuid.uuid4())

        # Vault aktifken metni sifrele
        stored_text = _encrypt_payload_text(item["text"])

        payload = {
            "text": stored_text,
            "source_file": item["source_file"],
            "chunk_index": item["chunk_index"],
            "encrypted": is_encrypted,
        }
        points.append(
            models.PointStruct(
                id=point_id,
                vector=item["embedding"],
                payload=payload
            )
        )

    with trace_span("rag.qdrant.upsert_batch", {"chunks_count": len(chunks_data)}):
        try:
            # 100'erli paketler halinde upsert et (büyük listelerde güvenli bellek yönetimi)
            BATCH_SIZE = 100
            for i in range(0, len(points), BATCH_SIZE):
                batch = points[i:i + BATCH_SIZE]
                client.upsert(
                    collection_name=config.QDRANT_COLLECTION,
                    points=batch
                )
        except Exception as e:
            raise RuntimeError(f"Qdrant'a toplu chunk eklenemedi: {e}") from e


def delete_file_chunks(source_file):
    """
    Belirli bir dosyaya ait tüm parça ve embedding'leri Qdrant'tan siler.
    (Dosya güncellendiğinde veya silindiğinde kullanılır)
    """
    try:
        client.delete(
            collection_name=config.QDRANT_COLLECTION,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="source_file",
                            match=models.MatchValue(value=source_file)
                        )
                    ]
                )
            )
        )
    except Exception as e:
        raise RuntimeError(f"'{source_file}' kaynaklı parçalar silinemedi: {e}") from e


def get_chunk_count():
    try:
        response = client.count(collection_name=config.QDRANT_COLLECTION, exact=True)
        return response.count
    except Exception:
        return 0


def get_sources():
    """Qdrant'taki tüm yüklü belgelerin benzersiz dosya adlarını döndürür."""
    try:
        records, _ = client.scroll(
            collection_name=config.QDRANT_COLLECTION,
            limit=1000,
            with_payload=["source_file"],
            with_vectors=False
        )
        sources = set()
        for rec in records:
            if rec.payload and "source_file" in rec.payload:
                sources.add(rec.payload["source_file"])
        return list(sources)
    except Exception:
        return []

def search_chunks(query_vector, top_k=3):
    """
    Verilen sorgu vektörüne en yakın top_k belge parçasını arar.
    Vault aktifken sonuçlardaki metin payload'ları otomatik decrypt edilir.
    
    Returns:
        list[dict]: Benzer belge parçaları (metin çözülmüş halde).
    """
    try:
        search_result = client.query_points(
            collection_name=config.QDRANT_COLLECTION,
            query=query_vector,
            limit=top_k
        )

        results = []
        for scored_point in search_result.points:
            payload = scored_point.payload
            raw_text = payload.get("text", "")

            # Vault aktifken ve payload sifreliyse decrypt et
            if payload.get("encrypted", False):
                text = _decrypt_payload_text(raw_text)
            else:
                text = raw_text

            results.append({
                "id": scored_point.id,
                "text": text,
                "source_file": payload.get("source_file", ""),
                "chunk_index": payload.get("chunk_index", 0),
                "score": scored_point.score
            })
        return results

    except Exception as e:
        raise RuntimeError(f"Qdrant'ta arama yapılamadı: {e}") from e
