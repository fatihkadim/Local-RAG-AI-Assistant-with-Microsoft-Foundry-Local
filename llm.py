"""
LLM entegrasyon modülü.
Foundry Local SDK üzerinden yerel LLM ile cevap üretir.

Bu modül, RAG pipeline'ının son aşamasıdır:
Retrieval modülünden gelen bağlam (context) ve kullanıcı sorusu
birleştirilerek yerel LLM'e gönderilir, model cevap üretir.

Kullanım:
    from llm import generate_answer

    cevap = generate_answer("Python nedir?", baglam_metni)
    print(cevap)
"""

from foundry_local_sdk import Configuration, FoundryLocalManager

import config

# ── Modül Seviyesi Değişkenler (Lazy Initialization) ─────────
_manager = None
_chat_client = None


def _ensure_initialized():
    """
    Foundry Local SDK'yı ve chat modelini başlatır (lazy init).

    İlk çağrıldığında:
    1. FoundryLocalManager'ı initialize eder (eğer henüz yapılmadıysa)
    2. Chat modelini (config.CHAT_MODEL) indirir ve yükler
    3. ChatClient'ı oluşturur

    Sonraki çağrılarda mevcut instance'ları kullanır (tekrar yüklemez).

    Raises:
        RuntimeError: SDK initialize edilemezse veya model yüklenemezse.
    """
    global _manager, _chat_client

    if _chat_client is not None:
        return

    try:
        # SDK'yı initialize et (sadece ilk seferde)
        # Not: FoundryLocalManager singleton'dır. embeddings.py zaten
        # initialize etmiş olabilir, bu durumda mevcut instance kullanılır.
        if _manager is None:
            try:
                sdk_config = Configuration(app_name="local-rag-assistant")
                FoundryLocalManager.initialize(sdk_config)
            except Exception:
                # Zaten initialize edilmiş (embeddings.py tarafından) — sorun yok
                pass

            _manager = FoundryLocalManager.instance

            # GPU/NPU hızlandırma için execution provider'ları kaydet
            try:
                _manager.download_and_register_eps()
                print("[GPU] Execution provider'lar kaydedildi (GPU/NPU hızlandırma aktif).")
            except Exception as ep_err:
                print(f"[GPU] EP kaydı başarısız, CPU ile devam ediliyor: {ep_err}")

        # Chat modelini indir (yoksa) ve yükle
        try:
            model = _manager.catalog.get_model(config.CHAT_MODEL)
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
                    model = _manager.catalog.get_model(fb_name)
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

    # Modelin şablon taklidi yaparak kendisini tekrarlamasını önlemek için ilk kesim noktası
    for stop_pattern in ["Sorunu cevaplayın:", "\nParça:", "\nSoru:", "Soruyu cevaplayın:"]:
        if stop_pattern in text:
            text = text.split(stop_pattern)[0]

    return text.strip()


def generate_answer(query, context):
    """
    Kullanıcı sorusunu, verilen bağlam bilgisiyle birleştirerek
    yerel LLM'den cevap üretir.

    RAG pipeline'ının son adımıdır:
    1. System prompt (config.SYSTEM_PROMPT) ile modele rolünü tanımlar
    2. Bağlam bilgisini (retrieval'dan gelen parçalar) ekler
    3. Kullanıcı sorusunu gönderir
    4. Modelin cevabını döndürür

    Args:
        query (str): Kullanıcının sorusu.
        context (str): Retrieval modülünden gelen formatlanmış bağlam metni.
                       retrieval.format_context() çıktısı beklenir.

    Returns:
        str: LLM'in ürettiği cevap metni.

    Raises:
        ValueError: query veya context None/boş ise.
        RuntimeError: Model yüklenemezse veya cevap üretilemezse.

    Örnek:
        >>> from retrieval import get_top_chunks, format_context
        >>> chunks = get_top_chunks("Python nedir?")
        >>> context = format_context(chunks)
        >>> cevap = generate_answer("Python nedir?", context)
        >>> print(cevap)
    """
    if query is None or not query.strip():
        raise ValueError("Soru (query) boş olamaz.")
    if context is None:
        raise ValueError("Bağlam (context) None olamaz.")

    _ensure_initialized()

    # Kullanıcı mesajını bağlam ile birleştir
    user_message = (
        f"Aşağıdaki bağlam bilgilerini kullanarak soruyu cevapla.\n\n"
        f"--- BAĞLAM ---\n"
        f"{context}\n"
        f"--- BAĞLAM SONU ---\n\n"
        f"Soru: {query}"
    )

    try:
        # Chat completion API'sını çağır
        messages = [
            {"role": "system", "content": config.SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        response = _chat_client.complete_chat(messages)

        # Cevabı al ve temizle
        raw_answer = response.choices[0].message.content.strip()
        answer = _clean_response(raw_answer)
        return answer

    except Exception as e:
        raise RuntimeError(
            f"Cevap üretilemedi: {e}"
        ) from e


def generate_answer_stream(query, context):
    """
    generate_answer() ile aynı mantık, ancak cevabı parça parça
    (streaming) döndürür. CLI ve web arayüzünde gerçek zamanlı
    cevap gösterimi için kullanılır.

    Args:
        query (str): Kullanıcının sorusu.
        context (str): Formatlanmış bağlam metni.

    Yields:
        str: Cevabın her bir parçası (token/kelime grubu).

    Raises:
        ValueError: query veya context None/boş ise.
        RuntimeError: Model yüklenemezse veya cevap üretilemezse.
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

    try:
        messages = [
            {"role": "system", "content": config.SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        # Streaming response
        for chunk in _chat_client.complete_streaming_chat(messages):
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    except Exception as e:
        raise RuntimeError(
            f"Streaming cevap üretilemedi: {e}"
        ) from e
