"""
Local RAG AI Assistant — Streamlit Web Arayüzü
Tarayıcı tabanlı sohbet arayüzü.

Kullanım:
    streamlit run app.py
"""

import streamlit as st
import time

from src import config
from src import database
from src import retrieval
from src import llm


# ── Sayfa Ayarları ────────────────────────────────────────────
st.set_page_config(
    page_title="RAG AI Assistant",
    page_icon="🤖",
    layout="centered",
)

# ── Özel CSS ──────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 1rem 0;
    }
    .source-box {
        background-color: #f0f2f6;
        border-radius: 8px;
        padding: 10px 15px;
        margin: 5px 0;
        font-size: 0.85rem;
    }
    .stats-bar {
        font-size: 0.8rem;
        color: #888;
        text-align: right;
        padding: 5px 0;
    }
</style>
""", unsafe_allow_html=True)


# ── Başlık ────────────────────────────────────────────────────
st.markdown("<div class='main-header'>", unsafe_allow_html=True)
st.title("🤖 Local RAG AI Assistant")
st.caption("Microsoft Foundry Local ile tamamen offline çalışır")
st.markdown("</div>", unsafe_allow_html=True)


# ── Sidebar Bilgileri ─────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Ayarlar")
    st.markdown(f"**Chat Modeli:** `{config.CHAT_MODEL}`")
    st.markdown(f"**Embedding Modeli:** `{config.EMBEDDING_MODEL}`")
    st.markdown(f"**Veritabanı (Qdrant):** `{config.QDRANT_URL}`")
    st.markdown(f"**Top-K:** `{config.TOP_K}`")

    st.divider()

    # Veritabanı durumu
    try:
        chunk_count = database.get_chunk_count()
        sources = database.get_sources()
        st.success(f"📊 {chunk_count} parça, {len(sources)} kaynak")
        with st.expander("📁 Yüklü Belgeler"):
            for src in sorted(sources):
                st.markdown(f"- `{src}`")
    except Exception:
        st.warning("⚠️ Veritabanı bulunamadı!")
        st.markdown("Önce çalıştırın:\n```\npython main.py --ingest\n```")

    st.divider()
    st.markdown(
        "**Nasıl çalışır?**\n"
        "1. Sorunuzu yazın\n"
        "2. En ilgili belge parçaları bulunur\n"
        "3. Bağlam ile birlikte LLM cevap üretir\n"
        "4. Kaynaklar gösterilir"
    )


# ── Sohbet Geçmişi (Session State) ───────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# Geçmiş mesajları göster
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "sources" in message:
            with st.expander("📚 Kaynaklar"):
                for src in message["sources"]:
                    st.markdown(
                        f"- **{src['source_file']}** "
                        f"(parça {src['chunk_index'] + 1}, "
                        f"skor: {src['score']:.4f})"
                    )


# ── Soru Girişi ───────────────────────────────────────────────
if prompt := st.chat_input("Sorunuzu yazın..."):
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
                "❌ Veritabanı bulunamadı! Önce çalıştırın:\n"
                "`python main.py --ingest`"
            )
            st.stop()

        with st.spinner("🔍 İlgili belgeler aranıyor..."):
            start_time = time.time()
            top_chunks = retrieval.get_top_chunks(prompt)
            retrieval_time = time.time() - start_time

        if not top_chunks:
            st.warning("Bu konuda veritabanında bilgi bulunamadı.")
            st.stop()

        context = retrieval.format_context(top_chunks)

        with st.spinner("⏳ Cevap üretiliyor..."):
            start_time = time.time()
            answer = llm.generate_answer(prompt, context)
            llm_time = time.time() - start_time

        # Cevabı göster
        st.markdown(answer)

        # Süre bilgisi
        st.markdown(
            f"<div class='stats-bar'>"
            f"⏱️ Arama: {retrieval_time:.2f}s | Üretim: {llm_time:.2f}s"
            f"</div>",
            unsafe_allow_html=True,
        )

        # Kaynakları göster
        sources_data = []
        with st.expander("📚 Kaynaklar"):
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
        })
