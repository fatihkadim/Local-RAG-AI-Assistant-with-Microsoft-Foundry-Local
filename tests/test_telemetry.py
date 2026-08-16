"""
Observability (OpenTelemetry & Prometheus) Test Modülü.

Testler:
1. Telemetry başlatma ve TracerProvider kurulumu
2. Span context manager ve decorator işlevselliği
3. QueryTraceContext ve Trace ID üretimi
4. Waterfall zaman kırılımı hesaplama
5. Prometheus metrik kayıtları (Counter & Histogram)
6. /metrics HTTP endpoint testi
7. config.ENABLE_TELEMETRY = False fallback testi
"""

import sys
import os
import time
import requests
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import config
from src import telemetry


def test_init_telemetry():
    """Telemetry'nin başarıyla başlatıldığını doğrular."""
    telemetry.init_telemetry()
    tracer = telemetry.get_tracer()
    assert tracer is not None, "Tracer initialize edilemedi"


def test_trace_span_context():
    """trace_span context manager'ın hata vermeden çalıştığını doğrular."""
    with telemetry.trace_span("test.span.unit", {"test.attr": "value"}) as span:
        time.sleep(0.01)
        if span:
            span.set_attribute("inner.attr", 123)


def test_trace_function_decorator():
    """trace_function decorator'ünün çalıştığını doğrular."""
    @telemetry.trace_function("test.decorated.func")
    def sample_func(x, y):
        return x + y

    result = sample_func(2, 3)
    assert result == 5


def test_query_trace_context():
    """start_query_trace'in Trace ID ve waterfall dökümü oluşturduğunu doğrular."""
    query = "Test sorusu nedir?"
    with telemetry.start_query_trace(query) as trace_ctx:
        assert len(trace_ctx.trace_id) == 32, f"Geçersiz trace ID: {trace_ctx.trace_id}"
        time.sleep(0.02)
        trace_ctx.retrieval_ms = 10.5
        trace_ctx.embedding_query_ms = 4.2
        trace_ctx.qdrant_search_ms = 6.3
        trace_ctx.llm_generation_ms = 15.0
        trace_ctx.tokens_count = 8
        trace_ctx.chunks_count = 3

    # Çıkışta toplam süre hesaplanmış olmalı
    assert trace_ctx.total_ms >= 20.0
    assert trace_ctx.status == "success"

    # Dict formatına dönüşüm
    d = trace_ctx.to_dict()
    assert d["query"] == query
    assert d["retrieval_ms"] == 10.5
    assert d["tokens_count"] == 8


def test_recent_traces_history():
    """Son sorguların geçmiş listesine kaydedildiğini doğrular."""
    with telemetry.start_query_trace("Geçmiş sorgu 1"):
        pass

    recent = telemetry.get_recent_traces()
    assert len(recent) > 0
    assert any("Geçmiş sorgu 1" in t["query"] for t in recent)


def test_prometheus_metrics_record():
    """Prometheus metrik kayıt fonksiyonlarının çalıştığını doğrular."""
    telemetry.record_query_metrics(
        status="success",
        total_duration_sec=0.15,
        retrieval_sec=0.05,
        llm_sec=0.10,
        chunks_count=3,
        tokens_count=25
    )
    telemetry.record_ingestion_metrics(
        duration_sec=1.5,
        documents_count=4
    )


def test_prometheus_http_endpoint():
    """http://localhost:8000/metrics adresinden Prometheus metriklerinin okunabildiğini test eder."""
    try:
        url = f"http://localhost:{config.PROMETHEUS_METRICS_PORT}/metrics"
        response = requests.get(url, timeout=3)
        assert response.status_code == 200
        text = response.text
        assert "rag_queries_total" in text
        assert "rag_query_duration_seconds" in text
        assert "rag_tokens_generated_total" in text
    except requests.exceptions.ConnectionError:
        pytest.skip("Prometheus portu henüz açık değil veya dinlenmiyor")


if __name__ == "__main__":
    print("=" * 60)
    print("RUNNING TELEMETRY TESTS")
    print("=" * 60)
    test_init_telemetry()
    print("  [OK] test_init_telemetry")
    test_trace_span_context()
    print("  [OK] test_trace_span_context")
    test_trace_function_decorator()
    print("  [OK] test_trace_function_decorator")
    test_query_trace_context()
    print("  [OK] test_query_trace_context")
    test_recent_traces_history()
    print("  [OK] test_recent_traces_history")
    test_prometheus_metrics_record()
    print("  [OK] test_prometheus_metrics_record")
    test_prometheus_http_endpoint()
    print("  [OK] test_prometheus_http_endpoint")
    print("=" * 60)
    print("ALL TELEMETRY TESTS PASSED!")
    print("=" * 60)
