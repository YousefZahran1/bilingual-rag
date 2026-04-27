"""Streamlit UI for the bilingual RAG assistant.

Bilingual toggle, citation hover, last-3-questions memory in session state.
"""
from __future__ import annotations

import os

import httpx
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Bilingual RAG", page_icon="🇸🇦", layout="wide")

if "history" not in st.session_state:
    st.session_state.history = []

with st.sidebar:
    st.title("Bilingual RAG")
    st.caption("Arabic / English question answering over your documents.")
    top_k = st.slider("Top-k passages", min_value=1, max_value=10, value=4)
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
            r = httpx.post(
                f"{API_URL}/chat",
                json={"question": question, "top_k": top_k},
                timeout=60,
            )
            r.raise_for_status()
            data = r.json()
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
            st.markdown(f"- **[{c['index']}]** `{c['source']}` chunk {c['chunk_id']}  •  score `{c['score']}`")
