"""Streamlit UI for the bilingual RAG assistant.

Bilingual toggle, citation hover, last-3-questions memory in session state,
streaming responses via /chat/stream (SSE).
"""
from __future__ import annotations

import json
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
    mode_options = ["hybrid_rerank", "smart", "dense", "unified", "unified_two_stage"]
    retrieval_mode = st.selectbox(
        "Retrieval mode",
        mode_options,
        help="hybrid_rerank (default as of v0.7): BM25 + dense fused with "
        "RRF, then cross-encoder reranked. smart: routes numeric questions "
        "(counts, caps, percentages) to BM25 alone instead of the reranker "
        "-- this used to be the default and still ties hybrid_rerank on "
        "data/real2, but on the current data/sample eval set hybrid_rerank "
        "now matches or beats it on every measured metric (recall@1, "
        "recall@4, keyword_coverage) -- see docs/EVAL.md's 'v0.7' section "
        "for the full investigation. dense: the original dense-only path. "
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

    stream_response = st.checkbox(
        "Stream response",
        value=True,
        help="Uses /chat/stream (SSE): citations render immediately, the "
        "answer streams token-by-token underneath. Uncheck to use /chat "
        "(unchanged, waits for the full answer before rendering anything).",
    )

    if st.button("Clear history"):
        st.session_state.history = []

def _answer_html(direction: str, text: str) -> str:
    return (
        f"<div dir='{direction}' style='padding: 0.75rem; "
        f"border-left: 3px solid #0F4C81; background: rgba(15,76,129,0.06);'>"
        f"{text}</div>"
    )


def _render_citations(citations: list[dict]) -> None:
    with st.expander(f"Citations ({len(citations)})"):
        for c in citations:
            label = f"`{c['source']}` chunk {c['chunk_id']}"
            if c.get("doc_title"):
                label = f"**{c['doc_title']}**" + (f", clause {c['clause']}" if c.get("clause") else "")
            st.markdown(f"- **[{c['index']}]** {label}  •  score `{c['score']}`")


st.title("Ask in Arabic or English")
question = st.text_input(
    "Question",
    placeholder="مثال: ما هي تغطية التأمين الصحي؟  /  e.g. What's covered by the health plan?",
)

just_streamed = False

if st.button("Ask") and question.strip():
    payload = {"question": question, "top_k": top_k, "retrieval_mode": retrieval_mode}
    if filters:
        payload["filters"] = filters
    data = None

    if stream_response:
        st.markdown(f"### Q: {question}")
        answer_box = st.empty()
        citations_box = st.empty()
        answer_text, citations, language = "", [], "en"
        try:
            with httpx.stream("POST", f"{API_URL}/chat/stream", json=payload, timeout=60) as r:
                r.raise_for_status()
                event_type = None
                for line in r.iter_lines():
                    if line.startswith("event: "):
                        event_type = line.removeprefix("event: ")
                    elif line.startswith("data: ") and event_type:
                        event_data = json.loads(line.removeprefix("data: "))
                        if event_type == "citations":
                            citations = event_data["citations"]
                            language = event_data["language"]
                            with citations_box.container():
                                _render_citations(citations)
                        elif event_type == "token":
                            answer_text += event_data["text"]
                            direction = "rtl" if language == "ar" else "ltr"
                            answer_box.markdown(_answer_html(direction, answer_text), unsafe_allow_html=True)
                        elif event_type == "error":
                            st.error(f"Generation error: {event_data['error']}")
                        elif event_type == "done":
                            break
            data = {"answer": answer_text, "citations": citations, "language": language}
            just_streamed = True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                detail = e.response.json().get("detail", {})
                st.error(
                    f"{detail.get('error', 'Retrieval unavailable')}. "
                    f"Fix: `{detail.get('fix', '')}`"
                )
            else:
                st.error(f"Request failed: {e}")
        except httpx.HTTPError as e:
            st.error(f"Request failed: {e}")
    else:
        with st.spinner("Retrieving and generating..."):
            try:
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
            except httpx.HTTPError as e:
                st.error(f"Request failed: {e}")

    if data:
        st.session_state.history.insert(0, (question, data))

# The just-streamed question was already rendered live above (citations +
# token-by-token answer) -- skip it here so it doesn't render twice; the
# history loop only replays older questions in that case.
history_to_replay = st.session_state.history[1:3] if just_streamed else st.session_state.history[:3]
for q, data in history_to_replay:
    direction = "rtl" if data.get("language") == "ar" else "ltr"
    st.markdown(f"### Q: {q}")
    st.markdown(_answer_html(direction, data["answer"]), unsafe_allow_html=True)
    _render_citations(data["citations"])
