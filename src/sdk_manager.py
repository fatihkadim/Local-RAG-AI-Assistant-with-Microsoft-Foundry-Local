"""
Foundry Local SDK singleton yöneticisi.

Bu modül, FoundryLocalManager'ın tek bir noktadan başlatılmasını sağlar.
embeddings.py ve llm.py modülleri bu modülü kullanarak SDK'ya erişir.
Tekrarlanan init kodunu ortadan kaldırır (DRY prensibi).

Kullanım:
    from src.sdk_manager import get_manager

    manager = get_manager()
    model = manager.catalog.get_model("phi-3.5-mini")
"""

from foundry_local_sdk import Configuration, FoundryLocalManager

# ── Modül Seviyesi Singleton ─────────────────────────────────
_manager = None


def get_manager():
    """
    FoundryLocalManager singleton instance'ını döndürür.

    İlk çağrıldığında:
    1. Configuration ile SDK'yı initialize eder
    2. Execution provider'ları (GPU/NPU) kaydeder
    3. Singleton instance'ı döndürür

    Sonraki çağrılarda mevcut instance'ı döndürür.

    Returns:
        FoundryLocalManager: SDK yönetici instance'ı.

    Raises:
        RuntimeError: SDK initialize edilemezse.
    """
    global _manager

    if _manager is not None:
        return _manager

    try:
        # SDK'yı initialize et
        try:
            sdk_config = Configuration(app_name="local-rag-assistant")
            FoundryLocalManager.initialize(sdk_config)
        except Exception:
            # Zaten initialize edilmiş olabilir — sorun yok
            pass

        _manager = FoundryLocalManager.instance

        # GPU/NPU hızlandırma için execution provider'ları kaydet
        try:
            _manager.download_and_register_eps()
            print("[GPU] Execution provider'lar kaydedildi (GPU/NPU hızlandırma aktif).")
        except Exception as ep_err:
            print(f"[GPU] EP kaydı başarısız, CPU ile devam ediliyor: {ep_err}")

        return _manager

    except Exception as e:
        raise RuntimeError(
            f"Foundry Local SDK başlatılamadı: {e}"
        ) from e
