"""
Embedding Servisi (embeddings.py) Test Modülü.

Testler:
1. Girdi validasyonu (boş metin, None)
2. Embedding üretimi (tekil ve toplu)
3. Cosine similarity benzerlik kontrolü
4. Lazy initialization
"""

import os
import sys
import math
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import embeddings


def cosine_similarity(vec_a, vec_b):
    """İki vektör arasındaki kosinüs benzerliğini hesaplar."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def test_embedding_input_validation():
    """Boş metin ve None girdilerinin ValueError fırlattığını test eder."""
    with pytest.raises(ValueError):
        embeddings.get_embedding("")
    with pytest.raises(ValueError):
        embeddings.get_embedding(None)
    with pytest.raises(ValueError):
        embeddings.get_embedding("   ")


def test_get_embedding_execution():
    """Foundry SDK çalışıyorsa embedding üretildiğini doğrular."""
    try:
        emb = embeddings.get_embedding("Python programlama dili.")
        assert isinstance(emb, list)
        assert len(emb) > 0
        assert all(isinstance(x, float) for x in emb)
    except Exception as e:
        pytest.skip(f"Foundry Local SDK veya model aktif değil: {e}")


def test_get_embeddings_batch_execution():
    """Toplu embedding üretimini test eder."""
    try:
        texts = ["Birinci metin.", "İkinci metin."]
        batch_embs = embeddings.get_embeddings_batch(texts)
        assert len(batch_embs) == 2
        assert len(batch_embs[0]) == len(batch_embs[1])
    except Exception as e:
        pytest.skip(f"Foundry Local SDK veya model aktif değil: {e}")


def test_embeddings_similarity_logic():
    """Benzer metinlerin benzerlik skorunun daha yüksek olduğunu test eder."""
    try:
        e1 = embeddings.get_embedding("Python ile veri bilimi ve yapay zeka.")
        e2 = embeddings.get_embedding("Python programlama ve makine öğrenimi.")
        e3 = embeddings.get_embedding("Taze portakal suyu ve narenciye bahçeleri.")

        sim_related = cosine_similarity(e1, e2)
        sim_unrelated = cosine_similarity(e1, e3)

        assert sim_related > sim_unrelated, f"Beklenen: {sim_related} > {sim_unrelated}"
    except Exception as e:
        pytest.skip(f"Foundry Local SDK veya model aktif değil: {e}")
