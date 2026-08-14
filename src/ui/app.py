"""Streamlit UI for the bilingual RAG assistant.

Bilingual toggle, citation hover, last-3-questions memory in session state.
"""
from __future__ import annotations

import os

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Bilingual RAG", page_icon="🇸🇦", layout="wide")

if "history" not in st.session_state:
    st.session_state.history = []

try:
    _health = httpx.get(f"{API_URL}/health", timeout=5).json()
    _unified_ready = _health.get("unified_index") == "ready"
except httpx.HTTPError:
    _unified_ready = False

with st.sidebar:
    st.title("Bilingual RAG")
    st.caption("Arabic / English question answering over your documents.")
    top_k = st.slider("Top-k passages", min_value=1, max_value=10, value=4)
    mode_options = ["smart", "hybrid_rerank", "dense", "unified", "unified_two_stage"]
    retrieval_mode = st.selectbox(
        "Retrieval mode",
        mode_options,
        help="smart (default): routes numeric questions (counts, caps, "
        "percentages) to BM25 alone -- the reranker specifically hurts "
        "those -- everything else through hybrid_rerank. NOTE: on the "
        "current 118-question eval set smart is no longer uniformly best -- "
        "see docs/EVAL.md. hybrid_rerank: BM25 + dense fused with RRF, then "
        "cross-encoder reranked. dense: the original dense-only path. "
        "unified: UnifiedIndex hybrid+parent-child retrieval with metadata "
        "filters (doc_type/language facets below). unified_two_stage: adds "
        "document-routing + rerank before parent expansion -- see "
        "docs/PIPELINE.md.",
    )

    filters: dict[str, str] = {}
    if retrieval_mode in ("unified", "unified_two_stage"):
        if not _unified_ready:
            st.warning(
                "Unified index not built yet. Run:\n\n"
                "`python -m src.rag.pipeline build data/real`\n\n"
                "then restart the API before using this mode."
            )
        doc_type = st.selectbox(
            "Filter: doc_type",
            ["All", "contract", "policy", "formulary", "guideline", "faq", "document"],
        )
        if doc_type != "All":
            filters["doc_type"] = doc_type
        language = st.selectbox("Filter: language", ["All", "ar", "en"])
        if language != "All":
            filters["language"] = language

    if st.button("Clear history"):
        st.session_state.history = []

st.title("Ask in Arabic or English")
question = st.text_input(
    "Question",
    placeholder="مثال: ما هي تغطية التأمين الصحي؟  /  e.g. What's covered by the health plan?",
)

if st.button("Ask") and question.strip():
    with st.spinner("Retrieving and generating..."):
        try:
            payload = {"question": question, "top_k": top_k, "retrieval_mode": retrieval_mode}
            if filters:
                payload["filters"] = filters
            r = httpx.post(f"{API_URL}/chat", json=payload, timeout=60)
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                detail = e.response.json().get("detail", {})
                st.error(
                    f"{detail.get('error', 'Retrieval unavailable')}. "
                    f"Fix: `{detail.get('fix', '')}`"
                )
            else:
                st.error(f"Request failed: {e}")
            data = None
        except httpx.HTTPError as e:
            st.error(f"Request failed: {e}")
            data = None
    if data:
        st.session_state.history.insert(0, (question, data))

for q, data in st.session_state.history[:3]:
    direction = "rtl" if data.get("language") == "ar" else "ltr"
    st.markdown(f"### Q: {q}")
    st.markdown(
        f"<div dir='{direction}' style='padding: 0.75rem; "
        f"border-left: 3px solid #0F4C81; background: rgba(15,76,129,0.06);'>"
        f"{data['answer']}</div>",
        unsafe_allow_html=True,
    )
    with st.expander(f"Citations ({len(data['citations'])})"):
        for c in data["citations"]:
            label = f"`{c['source']}` chunk {c['chunk_id']}"
            if c.get("doc_title"):
                label = f"**{c['doc_title']}**" + (f", clause {c['clause']}" if c.get("clause") else "")
            st.markdown(f"- **[{c['index']}]** {label}  •  score `{c['score']}`")
