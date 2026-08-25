"""
Local RAG AI Assistant — Streamlit Web Arayüzü
OpenTelemetry Tracing ve Prometheus Metrikleri Entegre Edilmiş Sohbet Arayüzü.
End-to-End Encrypted Document Vault desteği.

Kullanım:
    streamlit run app.py
"""

import streamlit as st
import time

from src import config
from src import database
from src import retrieval
from src import llm
from src.telemetry import start_query_trace, init_telemetry, get_recent_traces

# Telemetry servisini başlat
init_telemetry()

# ── Sayfa Ayarları ────────────────────────────────────────────
st.set_page_config(
    page_title="RAG AI Assistant",
    page_icon="🤖",
    layout="wide",
)

# ── Özel CSS ──────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 0.5rem 0;
    }
    .waterfall-bar {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 6px;
        padding: 8px 12px;
        margin: 6px 0;
        font-family: monospace;
        font-size: 0.82rem;
        color: #e2e8f0;
    }
    .badge-trace {
        background-color: #3b82f6;
        color: white;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-family: monospace;
    }
    .badge-embed {
        background-color: #10b981;
        color: white;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.75rem;
    }
    .badge-qdrant {
        background-color: #f59e0b;
        color: white;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.75rem;
    }
    .badge-llm {
        background-color: #8b5cf6;
        color: white;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.75rem;
    }
    .vault-locked {
        background: linear-gradient(135deg, #991b1b 0%, #7f1d1d 100%);
        border: 1px solid #dc2626;
        border-radius: 8px;
        padding: 12px;
        text-align: center;
        color: #fecaca;
    }
    .vault-unlocked {
        background: linear-gradient(135deg, #065f46 0%, #064e3b 100%);
        border: 1px solid #10b981;
        border-radius: 8px;
        padding: 12px;
        text-align: center;
        color: #a7f3d0;
    }
</style>
""", unsafe_allow_html=True)


# ── Başlık ────────────────────────────────────────────────────
st.markdown("<div class='main-header'>", unsafe_allow_html=True)
st.title("🤖 Local RAG AI Assistant")
st.caption("Microsoft Foundry Local • Rust Parser • OpenTelemetry & Prometheus Observability • 🔐 E2E Encrypted Vault")
st.markdown("</div>", unsafe_allow_html=True)


# ── Sidebar Bilgileri & Canlı Observability ───────────────────
with st.sidebar:
    st.header("⚙️ Sistem Ayarları")
    st.markdown(f"**Chat Modeli:** `{config.CHAT_MODEL}`")
    st.markdown(f"**Embedding:** `{config.EMBEDDING_MODEL}`")
    st.markdown(f"**Vektör DB:** `{config.QDRANT_URL}`")
    st.markdown(f"**Top-K:** `{config.TOP_K}`")

    st.divider()

    # ── 🔐 Vault Bölümü ──────────────────────────────────────
    if config.VAULT_ENABLED:
        st.subheader("🔐 Encrypted Vault")

        # Vault durumu session state'de takip ediliyor
        if "vault_unlocked" not in st.session_state:
            st.session_state.vault_unlocked = False
        if "vault_manager" not in st.session_state:
            st.session_state.vault_manager = None

        if not st.session_state.vault_unlocked:
            st.markdown(
                "<div class='vault-locked'>🔒 Vault Kilitli</div>",
                unsafe_allow_html=True
            )
            st.markdown("")

            vault_password = st.text_input(
                "Vault Şifresi",
                type="password",
                placeholder="Master şifrenizi girin...",
                key="vault_password_input"
            )

            col1, col2 = st.columns(2)
            with col1:
                unlock_btn = st.button("🔓 Aç", use_container_width=True)
            with col2:
                init_btn = st.button("🆕 Oluştur", use_container_width=True)

            if unlock_btn and vault_password:
                try:
                    from src.vault import init_vault_with_password
                    vm = init_vault_with_password(vault_password)
                    st.session_state.vault_unlocked = True
                    st.session_state.vault_manager = vm
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ {e}")

            if init_btn and vault_password:
                if len(vault_password) < 8:
                    st.error("Şifre en az 8 karakter olmalıdır.")
                else:
                    try:
                        from src.vault import init_vault_with_password
                        vm = init_vault_with_password(vault_password)
                        st.session_state.vault_unlocked = True
                        st.session_state.vault_manager = vm
                        st.success("✅ Vault oluşturuldu!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ {e}")

        else:
            st.markdown(
                "<div class='vault-unlocked'>🔓 Vault Açık</div>",
                unsafe_allow_html=True
            )
            st.markdown("")

            # Vault durumunu goster
            vm = st.session_state.vault_manager
            if vm:
                status = vm.get_vault_status()
                st.markdown(f"📁 **{status['vault_files_count']}** şifreli dosya")
                st.markdown(f"🔑 Versiyon: `{status['version']}`")

                with st.expander("📦 Vault Dosyaları"):
                    if status['vault_files']:
                        for vf in status['vault_files']:
                            st.markdown(f"- `{vf}`")
                    else:
                        st.info("Henüz şifreli dosya yok.")

            if st.button("🔒 Kilitle", use_container_width=True):
                from src.vault import set_vault_manager
                set_vault_manager(None)
                st.session_state.vault_unlocked = False
                st.session_state.vault_manager = None
                st.rerun()

        st.divider()

    # Veritabanı durumu
    try:
        chunk_count = database.get_chunk_count()
        sources = database.get_sources()
        st.success(f"📊 **{chunk_count}** parça • **{len(sources)}** kaynak yüklü")
        with st.expander("📁 Yüklü Belgeler"):
            for src in sorted(sources):
                st.markdown(f"- `{src}`")
    except Exception:
        st.warning("⚠️ Qdrant bağlantısı kurulamadı!")
        st.markdown("Terminalden çalıştırın:\n```bash\ndocker compose up -d\n```")

    st.divider()

    # 📊 Observability & Prometheus Paneli
    st.subheader("📊 Observability Stack")
    if config.ENABLE_TELEMETRY:
        st.markdown(f"🟢 **Tracer:** `{config.OTEL_SERVICE_NAME}`")
        st.markdown(f"📈 **Prometheus:** [localhost:{config.PROMETHEUS_METRICS_PORT}/metrics](http://localhost:{config.PROMETHEUS_METRICS_PORT}/metrics)")
        
        recent = get_recent_traces()
        if recent:
            with st.expander(f"⏱️ Son İşlemler ({len(recent)})", expanded=False):
                for t in recent[:5]:
                    st.markdown(
                        f"**{t['query'][:25]}...**\n"
                        f"- Toplam: `{t['total_ms']:.1f} ms`\n"
                        f"- Arama: `{t['retrieval_ms']:.1f} ms` | LLM: `{t['llm_generation_ms']:.1f} ms`\n"
                        f"- Trace: `{t['trace_id'][:12]}...`"
                    )
                    st.divider()
    else:
        st.info("⚪ Telemetry kapalı (`config.ENABLE_TELEMETRY = False`)")


# ── Vault Kilit Kontrolü ──────────────────────────────────────
# Vault aktifken ve kilitliyken sohbet alanını engelle
if config.VAULT_ENABLED and not st.session_state.get("vault_unlocked", False):
    st.warning("🔒 **Vault kilitli.** Sohbet başlatmak için sol panelden vault şifrenizi girin.")
    st.stop()


# ── Sohbet Geçmişi (Session State) ───────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# Geçmiş mesajları göster
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Waterfall ve Trace bilgisi
        if "waterfall" in message:
            wf = message["waterfall"]
            st.markdown(
                f"<div class='waterfall-bar'>"
                f"🏷️ <span class='badge-trace'>{wf['trace_id'][:16]}...</span> "
                f"⏱️ Toplam: <b>{wf['total_ms']:.0f}ms</b> "
                f"(<span class='badge-embed'>Embed: {wf['embedding_query_ms']:.0f}ms</span> "
                f"<span class='badge-qdrant'>Qdrant: {wf['qdrant_search_ms']:.0f}ms</span> "
                f"<span class='badge-llm'>LLM: {wf['llm_generation_ms']:.0f}ms</span>)"
                f"</div>",
                unsafe_allow_html=True
            )

        if "sources" in message and message["sources"]:
            with st.expander("📚 Kullanılan Kaynaklar"):
                for src in message["sources"]:
                    st.markdown(
                        f"- **{src['source_file']}** "
                        f"(parça {src['chunk_index'] + 1}, "
                        f"skor: {src['score']:.4f})"
                    )


# ── Soru Girişi ───────────────────────────────────────────────
if prompt := st.chat_input("Sorunuzu yazın (örn: Generads fizibilitesi nedir?)..."):
    # Kullanıcı mesajını ekle
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Cevap üret
    with st.chat_message("assistant"):
        # Veritabanı kontrolü
        try:
            chunk_count = database.get_chunk_count()
            if not chunk_count:
                st.warning(
                    "⚠️ Veritabanı boş! Önce belgeleri yükleyin:\n"
                    "`python main.py --ingest`"
                )
                st.stop()
        except Exception:
            st.error(
                "❌ Veritabanı bulunamadı! Önce Docker ve Ingestion çalıştırın:\n"
                "`docker compose up -d && python main.py --ingest`"
            )
            st.stop()

        with start_query_trace(prompt) as trace_ctx:
            with st.spinner("🔍 İlgili belgeler aranıyor..."):
                top_chunks = retrieval.get_top_chunks(prompt, trace_ctx=trace_ctx)

            if not top_chunks:
                st.warning("Bu konuda veritabanında yeterli bilgi bulunamadı.")
                st.stop()

            context = retrieval.format_context(top_chunks)

            with st.spinner("⏳ Cevap üretiliyor..."):
                answer = llm.generate_answer(prompt, context, trace_ctx=trace_ctx)

        # Cevabı göster
        st.markdown(answer)

        # Waterfall & Observability çubuğu
        wf_data = trace_ctx.to_dict()
        st.markdown(
            f"<div class='waterfall-bar'>"
            f"🏷️ <span class='badge-trace'>{wf_data['trace_id'][:16]}...</span> "
            f"⏱️ Toplam: <b>{wf_data['total_ms']:.0f}ms</b> "
            f"(<span class='badge-embed'>Embed: {wf_data['embedding_query_ms']:.0f}ms</span> "
            f"<span class='badge-qdrant'>Qdrant: {wf_data['qdrant_search_ms']:.0f}ms</span> "
            f"<span class='badge-llm'>LLM: {wf_data['llm_generation_ms']:.0f}ms</span>)"
            f"</div>",
            unsafe_allow_html=True
        )

        # Kaynakları göster
        sources_data = []
        with st.expander("📚 Kullanılan Kaynaklar"):
            for chunk in top_chunks:
                st.markdown(
                    f"**{chunk['source_file']}** "
                    f"(parça {chunk['chunk_index'] + 1}, "
                    f"skor: {chunk['score']:.4f})"
                )
                st.markdown(
                    f"> {chunk['text'][:200]}..."
                    if len(chunk['text']) > 200
                    else f"> {chunk['text']}"
                )
                st.divider()
                sources_data.append({
                    "source_file": chunk["source_file"],
                    "chunk_index": chunk["chunk_index"],
                    "score": chunk["score"],
                })

        # Sohbet geçmişine kaydet
        st.session_state.messages.append({
            "role": "assistant",
            "content": answer,
            "sources": sources_data,
            "waterfall": wf_data,
        })
