"""
OpenTelemetry ve Prometheus Tabanlı Dağıtık İzleme (Distributed Tracing) & Metrik Modülü.

Bu modül:
1. OpenTelemetry Tracer ile her işlem için hiyerarşik span ve Trace ID üretir.
2. Prometheus Client ile canlı metrikleri toplayıp HTTP (:8000/metrics) üzerinden sunar.
3. Streamlit ve CLI için anlık gecikme kırılımları (waterfall breakdown) sağlar.
4. config.ENABLE_TELEMETRY = False olduğunda sıfır maliyetli (no-op) fallback çalışır.
"""

import time
import functools
from contextlib import contextmanager

from src import config

# ── Modül Seviyesi Değişkenler ────────────────────────────────
_initialized = False
_tracer = None
_prometheus_server_started = False

# Canlı metrik sayaçları (Prometheus)
_metric_queries_total = None
_metric_query_duration = None
_metric_retrieval_duration = None
_metric_llm_duration = None
_metric_tokens_total = None
_metric_chunks_retrieved = None
_metric_ingestion_duration = None
_metric_documents_total = None

# Son işlemlerin trace & waterfall geçmişi (bellekte tutulur, UI için)
_recent_traces = []


def init_telemetry():
    """
    OpenTelemetry ve Prometheus metrik sunucusunu başlatır.
    Sadece bir kez çalıştırılır.
    """
    global _initialized, _tracer, _prometheus_server_started
    global _metric_queries_total, _metric_query_duration, _metric_retrieval_duration
    global _metric_llm_duration, _metric_tokens_total, _metric_chunks_retrieved
    global _metric_ingestion_duration, _metric_documents_total

    if _initialized or not config.ENABLE_TELEMETRY:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.resources import Resource

        # 1. OpenTelemetry TracerProvider Kurulumu
        resource = Resource.create({"service.name": config.OTEL_SERVICE_NAME})
        provider = TracerProvider(resource=resource)

        # Jaeger OTLP gRPC Exporter (:4317)
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            otlp_exporter = OTLPSpanExporter(endpoint="localhost:4317", insecure=True)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        except Exception:
            pass

        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(config.OTEL_SERVICE_NAME)

        # 2. Prometheus Metrikleri Kurulumu
        from prometheus_client import Counter, Histogram, start_http_server, REGISTRY

        # Metriklerin birden fazla kez register edilmesini önlemek için kontrol
        try:
            _metric_queries_total = Counter(
                "rag_queries_total",
                "Toplam kullanıcı sorgu sayısı",
                ["status"]
            )
            _metric_query_duration = Histogram(
                "rag_query_duration_seconds",
                "Uçtan uca RAG sorgu-cevap süresi (saniye)",
                buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0]
            )
            _metric_retrieval_duration = Histogram(
                "rag_retrieval_duration_seconds",
                "Retrieval (arama) süresi (saniye)",
                buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
            )
            _metric_llm_duration = Histogram(
                "rag_llm_duration_seconds",
                "LLM cevap üretim süresi (saniye)",
                buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 45.0, 60.0]
            )
            _metric_tokens_total = Counter(
                "rag_tokens_generated_total",
                "Üretilen yaklaşık toplam token/kelime sayısı"
            )
            _metric_chunks_retrieved = Histogram(
                "rag_chunks_retrieved_count",
                "Sorgu başına getirilen parça sayısı",
                buckets=[1, 2, 3, 5, 10]
            )
            _metric_ingestion_duration = Histogram(
                "rag_ingestion_duration_seconds",
                "Ingestion toplam süresi (saniye)",
                buckets=[0.1, 1.0, 5.0, 15.0, 30.0, 60.0, 120.0, 300.0]
            )
            _metric_documents_total = Counter(
                "rag_documents_ingested_total",
                "Yüklenen toplam belge sayısı"
            )
        except ValueError:
            # Zaten register edilmişse mevcut registry'den al
            pass

        # 3. Prometheus HTTP Endpoint Başlatma (:8000/metrics)
        if not _prometheus_server_started:
            try:
                start_http_server(config.PROMETHEUS_METRICS_PORT)
                _prometheus_server_started = True
                print(f"[TELEMETRY] Prometheus metrik sunucusu aktif: http://localhost:{config.PROMETHEUS_METRICS_PORT}/metrics")
            except Exception as srv_err:
                print(f"[TELEMETRY] Prometheus portu başlatılamadı ({srv_err}), devam ediliyor.")

        _initialized = True
        print(f"[TELEMETRY] OpenTelemetry & Prometheus hazır (Servis: {config.OTEL_SERVICE_NAME})")

    except Exception as e:
        print(f"[TELEMETRY] Başlatma uyarısı: {e}. No-op moduna geçildi.")
        _initialized = False


def get_tracer():
    """Mevcut OpenTelemetry tracer'ı döndürür."""
    global _tracer
    if not _initialized and config.ENABLE_TELEMETRY:
        init_telemetry()
    return _tracer


# ── Context Managers & Decorators ─────────────────────────────

@contextmanager
def trace_span(span_name, attributes=None):
    """
    Belirli bir işlem bloğunu OpenTelemetry span'ı içine alır.

    Kullanım:
        with trace_span("rag.embedding.query", {"query_len": len(q)}):
            ...
    """
    tracer = get_tracer()
    if tracer is None or not config.ENABLE_TELEMETRY:
        yield None
        return

    with tracer.start_as_current_span(span_name) as span:
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, v)
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(trace.StatusCode.ERROR, str(exc))
            raise


def trace_function(span_name=None):
    """
    Bir fonksiyonu otomatik olarak trace span'ı içine alan dekoratör.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            name = span_name or f"rag.{func.__name__}"
            with trace_span(name):
                return func(*args, **kwargs)
        return wrapper
    return decorator


# ── Query Trace Tracker & Waterfall Analytics ─────────────────

class QueryTraceContext:
    """
    Tek bir kullanıcı sorusu için uçtan uca zaman kırılımlarını (waterfall)
    ve Trace ID'yi saklayan yardımcı sınıf.
    """
    def __init__(self, query: str):
        self.query = query
        self.trace_id = "00000000000000000000000000000000"
        self.start_time = time.time()
        self.end_time = None
        self.total_ms = 0.0
        self.retrieval_ms = 0.0
        self.embedding_query_ms = 0.0
        self.qdrant_search_ms = 0.0
        self.llm_generation_ms = 0.0
        self.chunks_count = 0
        self.tokens_count = 0
        self.status = "success"
        self.error_msg = ""
        self._span = None
        self._span_cm = None

    def __enter__(self):
        tracer = get_tracer()
        if tracer and config.ENABLE_TELEMETRY:
            from opentelemetry import trace
            self._span_cm = tracer.start_as_current_span("rag.query")
            self._span = self._span_cm.__enter__()
            self._span.set_attribute("rag.query.text", self.query[:200])
            ctx = self._span.get_span_context()
            if ctx.is_valid:
                self.trace_id = f"{ctx.trace_id:032x}"
        else:
            # Fallback sahte trace ID
            import uuid
            self.trace_id = uuid.uuid4().hex

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        self.total_ms = (self.end_time - self.start_time) * 1000.0

        if exc_val is not None:
            self.status = "error"
            self.error_msg = str(exc_val)
            if self._span:
                from opentelemetry import trace
                self._span.record_exception(exc_val)
                self._span.set_status(trace.StatusCode.ERROR, str(exc_val))

        # Prometheus metriklerini kaydet
        if config.ENABLE_TELEMETRY:
            record_query_metrics(
                status=self.status,
                total_duration_sec=self.total_ms / 1000.0,
                retrieval_sec=self.retrieval_ms / 1000.0,
                llm_sec=self.llm_generation_ms / 1000.0,
                chunks_count=self.chunks_count,
                tokens_count=self.tokens_count
            )

        # Son traceler listesine ekle (maks 20 adet)
        _recent_traces.append(self.to_dict())
        if len(_recent_traces) > 20:
            _recent_traces.pop(0)

        if self._span_cm:
            self._span_cm.__exit__(exc_type, exc_val, exc_tb)

    def to_dict(self):
        return {
            "trace_id": self.trace_id,
            "query": self.query,
            "status": self.status,
            "total_ms": round(self.total_ms, 2),
            "retrieval_ms": round(self.retrieval_ms, 2),
            "embedding_query_ms": round(self.embedding_query_ms, 2),
            "qdrant_search_ms": round(self.qdrant_search_ms, 2),
            "llm_generation_ms": round(self.llm_generation_ms, 2),
            "chunks_count": self.chunks_count,
            "tokens_count": self.tokens_count,
            "timestamp": time.time(),
        }


def start_query_trace(query: str) -> QueryTraceContext:
    """Tek bir RAG sorgusu için tracing bağlamı oluşturur."""
    return QueryTraceContext(query)


# ── Metrik Kayıt Fonksiyonları ────────────────────────────────

def record_query_metrics(status="success", total_duration_sec=0.0, retrieval_sec=0.0,
                         llm_sec=0.0, chunks_count=0, tokens_count=0):
    """Sorgu tamamlandığında Prometheus metriklerini günceller."""
    if not config.ENABLE_TELEMETRY:
        return

    try:
        if _metric_queries_total:
            _metric_queries_total.labels(status=status).inc()
        if _metric_query_duration and total_duration_sec > 0:
            _metric_query_duration.observe(total_duration_sec)
        if _metric_retrieval_duration and retrieval_sec > 0:
            _metric_retrieval_duration.observe(retrieval_sec)
        if _metric_llm_duration and llm_sec > 0:
            _metric_llm_duration.observe(llm_sec)
        if _metric_chunks_retrieved and chunks_count > 0:
            _metric_chunks_retrieved.observe(chunks_count)
        if _metric_tokens_total and tokens_count > 0:
            _metric_tokens_total.inc(tokens_count)
    except Exception:
        pass


def record_ingestion_metrics(duration_sec: float, documents_count: int):
    """Ingestion tamamlandığında Prometheus metriklerini günceller."""
    if not config.ENABLE_TELEMETRY:
        return

    try:
        if _metric_ingestion_duration and duration_sec > 0:
            _metric_ingestion_duration.observe(duration_sec)
        if _metric_documents_total and documents_count > 0:
            _metric_documents_total.inc(documents_count)
    except Exception:
        pass


def get_recent_traces():
    """Son çalıştırılan sorguların zaman ve trace dökümlerini döndürür."""
    return list(reversed(_recent_traces))
