"""
LLM entegrasyon modülü.
Foundry Local SDK üzerinden yerel LLM ile cevap üretir.

Bu modül, RAG pipeline'ının son aşamasıdır:
Retrieval modülünden gelen bağlam (context) ve kullanıcı sorusu
birleştirilerek yerel LLM'e gönderilir, model cevap üretir.

Kullanım:
    from src.llm import generate_answer

    cevap = generate_answer("Python nedir?", baglam_metni)
    print(cevap)
"""

from src import config
from src.sdk_manager import get_manager

# ── Modül Seviyesi Değişkenler (Lazy Initialization) ─────────
_chat_client = None


def _ensure_initialized():
    """
    Chat modelini başlatır (lazy init).

    İlk çağrıldığında:
    1. SDK manager'dan FoundryLocalManager instance'ını alır
    2. Chat modelini (config.CHAT_MODEL) indirir ve yükler
    3. ChatClient'ı oluşturur

    Sonraki çağrılarda mevcut instance'ları kullanır (tekrar yüklemez).

    Raises:
        RuntimeError: SDK initialize edilemezse veya model yüklenemezse.
    """
    global _chat_client

    if _chat_client is not None:
        return

    try:
        manager = get_manager()

        # Chat modelini indir (yoksa) ve yükle
        try:
            model = manager.catalog.get_model(config.CHAT_MODEL)
            model.download()
            model.load()
        except Exception as load_err:
            print(f"[UYARI] '{config.CHAT_MODEL}' modeli yüklenemedi ({load_err}). CPU varyantı/yedek model deneniyor...")
            fallback_models = [
                "phi-3-mini",
                "qwen2.5-1.5b-instruct",
                "qwen2.5-0.5b-instruct",
                "qwen3-0.6b",
            ]
            loaded = False
            for fb_name in fallback_models:
                try:
                    model = manager.catalog.get_model(fb_name)
                    model.download()
                    model.load()
                    loaded = True
                    print(f"[LLM] Yedek model başarıyla yüklendi: {fb_name}")
                    break
                except Exception:
                    continue
            if not loaded:
                raise load_err

        # Chat client'ı oluştur
        _chat_client = model.get_chat_client()
        # KV-cache bellek tasmasini onlemek icin max cikti uzunlugunu sinirla.
        # Daha fazlasi icin config.py'ye MAX_TOKENS sabiti eklenebilir.
        _chat_client.settings.max_tokens = 512
        print(f"[LLM] Chat modeli hazır.")

    except Exception as e:
        raise RuntimeError(
            f"Chat modeli başlatılamadı "
            f"(model: {config.CHAT_MODEL}): {e}"
        ) from e


def _clean_response(text: str) -> str:
    """Modellerin üretebileceği şablon tekrarlarını ve ekstra etiketleri temizler."""
    if not text:
        return ""

    # Modelin şablon taklidi yaparak kendisini tekrarlamasını önlemek için kesim noktaları
    stop_patterns = [
        "Sorunu cevaplayın:",
        "Soruyu cevaplayın:",
        "\nParça:",
        "\nSoru:",
        "\nCevap:",
        "\nSon cevabı:",
        "\nKaynak:",
        "\nParca:",
        "\n[Kaynak:",
        "\n--- BAĞLAM",
        "\n--- BAGLAM",
    ]
    for stop_pattern in stop_patterns:
        if stop_pattern in text:
            text = text.split(stop_pattern)[0]

    # Eğer temizlemeden sonra çok kısa veya boş kaldıysa,
    # orijinal metnin ilk anlamlı cümlesini almayı dene
    cleaned = text.strip()
    if len(cleaned) < 5:
        return cleaned if cleaned else ""

    return cleaned


from src.telemetry import trace_span
import time


def generate_answer(query, context, trace_ctx=None):
    """
    Kullanıcı sorusunu, verilen bağlam bilgisiyle birleştirerek
    yerel LLM'den cevap üretir.
    OpenTelemetry span'i ve gecikme takibi ile izlenir.

    Args:
        query (str): Kullanıcının sorusu.
        context (str): Retrieval modülünden gelen formatlanmış bağlam metni.
        trace_ctx (QueryTraceContext, optional): Canlı tracing bağlamı.

    Returns:
        str: LLM'in ürettiği cevap metni.
    """
    if query is None or not query.strip():
        raise ValueError("Soru (query) boş olamaz.")
    if context is None:
        raise ValueError("Bağlam (context) None olamaz.")

    _ensure_initialized()

    user_message = (
        f"Aşağıdaki bağlam bilgilerini kullanarak soruyu cevapla.\n\n"
        f"--- BAĞLAM ---\n"
        f"{context}\n"
        f"--- BAĞLAM SONU ---\n\n"
        f"Soru: {query}"
    )

    llm_start = time.time()

    with trace_span("rag.llm.generate", {"llm.model": config.CHAT_MODEL, "context_chars": len(context)}):
        try:
            messages = [
                {"role": "system", "content": config.SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ]

            response = _chat_client.complete_chat(messages)
            raw_answer = response.choices[0].message.content.strip()
            answer = _clean_response(raw_answer)

            llm_duration = (time.time() - llm_start) * 1000.0

            if trace_ctx:
                trace_ctx.llm_generation_ms = llm_duration
                trace_ctx.tokens_count = len(answer.split())

            return answer

        except Exception as e:
            raise RuntimeError(f"Cevap üretilemedi: {e}") from e


def generate_answer_stream(query, context, trace_ctx=None):
    """
    generate_answer() ile aynı mantık, ancak cevabı parça parça
    (streaming) döndürür.
    """
    if query is None or not query.strip():
        raise ValueError("Soru (query) boş olamaz.")
    if context is None:
        raise ValueError("Bağlam (context) None olamaz.")

    _ensure_initialized()

    user_message = (
        f"Aşağıdaki bağlam bilgilerini kullanarak soruyu cevapla.\n\n"
        f"--- BAĞLAM ---\n"
        f"{context}\n"
        f"--- BAĞLAM SONU ---\n\n"
        f"Soru: {query}"
    )

    llm_start = time.time()
    token_count = 0

    with trace_span("rag.llm.generate_stream", {"llm.model": config.CHAT_MODEL, "context_chars": len(context)}):
        try:
            messages = [
                {"role": "system", "content": config.SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ]

            for chunk in _chat_client.complete_streaming_chat(messages):
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    token_count += len(token.split()) or 1
                    yield token

            llm_duration = (time.time() - llm_start) * 1000.0
            if trace_ctx:
                trace_ctx.llm_generation_ms = llm_duration
                trace_ctx.tokens_count = token_count

        except Exception as e:
            raise RuntimeError(f"Streaming cevap üretilemedi: {e}") from e
