"""Streamlit UI for the bilingual RAG assistant.

Bilingual toggle, citation hover, last-3-questions memory in session state,
streaming responses via /chat/stream (SSE), and account login/quota.
"""
from __future__ import annotations

import html
import json
import os

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_URL = os.environ.get("API_URL", "http://localhost:8000")

# A curated pull from data/real/eval_questions.jsonl and
# data/real2/eval_questions.jsonl: guaranteed answerable, mixed EN/AR, plus
# a couple deliberately unanswerable ones so a new user can see the model
# abstain instead of guessing.
EXAMPLE_QUESTIONS = [
    "Within how many minutes must the Insurance Company approve a treatment request under the Unified Contract?",
    "خلال كم دقيقة تلتزم شركة التأمين بالرد على طلب الموافقة في العقد الموحد؟",
    "What is the maximum co-payment for generic medications for the total prescription?",
    "How many operational chapters is CHI's Providers Classification Program organized into?",
    "What is the CHI definition of Fraud among insurance parties?",
    "متى بدأ تطبيق المرحلة الأولى من مشروع الوثيقة الموحدة لصاحب العمل؟",
    "Within how many days of treatment must a Bupa member file a reimbursement claim form?",
    "What is the maximum lifetime coverage limit under Tawuniya's individual (non-family) medical insurance plan?",
    "هل تغطي وثيقة بوبا تكاليف علاج التجميل غير الضروري طبياً؟",
]

st.set_page_config(page_title="Bilingual RAG", page_icon="🇸🇦", layout="wide")

if "history" not in st.session_state:
    st.session_state.history = []
if "token" not in st.session_state:
    st.session_state.token = None
if "question_input" not in st.session_state:
    st.session_state.question_input = ""


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {st.session_state.token}"}


def _login_register_gate() -> None:
    st.title("Bilingual RAG")
    st.caption("Sign in or create an account to ask questions.")
    login_tab, register_tab = st.tabs(["Log in", "Register"])

    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in")
        if submitted:
            try:
                r = httpx.post(f"{API_URL}/auth/login", json={"email": email, "password": password}, timeout=15)
                if r.status_code == 200:
                    st.session_state.token = r.json()["access_token"]
                    st.rerun()
                else:
                    st.error(r.json().get("detail", "Login failed."))
            except httpx.HTTPError as e:
                st.error(f"Could not reach the API: {e}")

    with register_tab:
        with st.form("register_form"):
            new_email = st.text_input("Email", key="register_email")
            new_password = st.text_input(
                "Password", type="password", key="register_password", help="At least 8 characters."
            )
            register_submitted = st.form_submit_button("Create account")
        if register_submitted:
            try:
                r = httpx.post(
                    f"{API_URL}/auth/register",
                    json={"email": new_email, "password": new_password},
                    timeout=15,
                )
                if r.status_code == 201:
                    st.success("Account created. Log in on the other tab.")
                else:
                    detail = r.json().get("detail", "Registration failed.")
                    st.error(detail if isinstance(detail, str) else "Registration failed.")
            except httpx.HTTPError as e:
                st.error(f"Could not reach the API: {e}")


if not st.session_state.token:
    _login_register_gate()
    st.stop()

try:
    _health = httpx.get(f"{API_URL}/health", timeout=5).json()
    _unified_ready = _health.get("unified_index") == "ready"
except httpx.HTTPError:
    _unified_ready = False

try:
    _me = httpx.get(f"{API_URL}/auth/me", headers=_auth_headers(), timeout=5)
    if _me.status_code == 401:
        st.session_state.token = None
        st.rerun()
    _me_data = _me.json()
except httpx.HTTPError:
    _me_data = None

with st.sidebar:
    st.title("Bilingual RAG")
    st.caption("Arabic / English question answering over your documents.")

    if _me_data:
        st.markdown(f"**{_me_data['email']}**")
        st.progress(
            min(_me_data["queries_used"] / max(_me_data["query_limit"], 1), 1.0),
            text=f"{_me_data['queries_used']} / {_me_data['query_limit']} queries used",
        )
    if st.button("Log out"):
        st.session_state.token = None
        st.rerun()

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
    # text is LLM-generated (or, worst case, echoes injected content from a
    # retrieved document) and this renders via unsafe_allow_html=True --
    # escape it or a crafted answer/document becomes live HTML/JS in the
    # viewer's browser. direction is one of two hardcoded literals, never
    # user input, so it doesn't need escaping.
    return (
        f"<div dir='{direction}' style='padding: 0.75rem; "
        f"border-left: 3px solid #0F4C81; background: rgba(15,76,129,0.06);'>"
        f"{html.escape(text)}</div>"
    )


def _render_citations(citations: list[dict]) -> None:
    with st.expander(f"Citations ({len(citations)})"):
        for c in citations:
            label = f"`{c['source']}` chunk {c['chunk_id']}"
            if c.get("doc_title"):
                label = f"**{c['doc_title']}**" + (f", clause {c['clause']}" if c.get("clause") else "")
            st.markdown(f"- **[{c['index']}]** {label}  •  score `{c['score']}`")


st.title("Ask in Arabic or English")

with st.expander("Example questions", expanded=False):
    cols = st.columns(3)
    for i, q in enumerate(EXAMPLE_QUESTIONS):
        if cols[i % 3].button(q, key=f"example_{i}", use_container_width=True):
            st.session_state.question_input = q
            st.rerun()

question = st.text_input(
    "Question",
    key="question_input",
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
            with httpx.stream(
                "POST", f"{API_URL}/chat/stream", json=payload, headers=_auth_headers(), timeout=60
            ) as r:
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
            if e.response.status_code == 401:
                st.session_state.token = None
                st.rerun()
            elif e.response.status_code == 429:
                detail = e.response.json().get("detail", {})
                st.error(
                    f"Query limit reached ({detail.get('used', '?')}/{detail.get('limit', '?')})."
                )
            elif e.response.status_code == 409:
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
                r = httpx.post(f"{API_URL}/chat", json=payload, headers=_auth_headers(), timeout=60)
                r.raise_for_status()
                data = r.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    st.session_state.token = None
                    st.rerun()
                elif e.response.status_code == 429:
                    detail = e.response.json().get("detail", {})
                    st.error(
                        f"Query limit reached ({detail.get('used', '?')}/{detail.get('limit', '?')})."
                    )
                elif e.response.status_code == 409:
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
