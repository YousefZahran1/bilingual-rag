# Defense Brief — Bilingual RAG Assistant

> **Read this before any interview that mentions this repo.** Every section maps to questions an interviewer will likely ask.

## What this project does (60-second pitch)
"It's a question-answering system over Arabic and English documents. You feed it a folder — for example, the bilingual policy PDFs an insurer publishes — it chunks them, embeds them with a multilingual model, stores them in Chroma, and exposes a FastAPI endpoint plus a Streamlit UI. Ask a question in Arabic or English, get an answer in the same language with citations to the source passages. I built it to handle the messy realities of Gulf documents — RTL text, language-mixing, Arabic morphology — that off-the-shelf English-only RAG breaks on."

## Why I built it
Two reasons. First, my Nafsyte chatbot project showed me that bilingual conversational AI is a real Saudi-market need and there's not a lot of public, defensible examples of it. Second, every junior ML/AI Engineer JD in Riyadh, Dubai, and Berlin in 2026 is asking about RAG. I wanted a project where I could speak about retrieval design, evaluation, and deployment — not just throw OpenAI at a cookbook.

## Architecture walk-through

```
docs (AR/EN/mixed)
     │  language-aware chunker
     ▼
multilingual-e5-small embeddings
     │
     ▼
Chroma persistent store (cosine distance)
     │  top-k passages
     ▼
Answer generator (mock | OpenAI | Anthropic) ──▶ FastAPI /chat ──▶ Streamlit UI
```

The non-trivial parts are the chunker and the language-pair handling. The chunker uses different character budgets for Arabic and English (Arabic gets ~700 chars, English ~1100) because Arabic tokenizes more densely. The retrieval prefixes queries with `query:` per the multilingual-e5 paper's instruction style. The Streamlit UI flips `dir="rtl"` on the answer panel when the question is Arabic.

## Key design decisions

| What I picked | What I rejected | Why |
|---|---|---|
| `intfloat/multilingual-e5-small` | OpenAI ada-002 | Free, runs locally, EU/Germany compliance simpler, decent on Arabic |
| Chroma local persistent | Pinecone, Weaviate | Self-contained demo; no API key gate for reviewers; free |
| FastAPI | Flask, Django | Async + types + auto OpenAPI; idiomatic for ML serving in 2026 |
| Streamlit UI | React/Next | Faster to ship; recruiters know it; not the focus of the project |
| Pluggable LLM (mock/OpenAI/Anthropic) | hardcoded provider | The repo runs end-to-end without ANY API key — reviewers can clone and run it. Real providers swap in via env var. |
| Cosine distance, top_k=4 | dot-product, top_k=10 | e5 is normalized so cosine = dot; top_k=4 keeps prompt short and citation count manageable |
| Hard chunk budget + sentence-aware split | LangChain RecursiveCharacterTextSplitter | I wanted explicit control; LangChain's splitter doesn't know about Arabic budget tuning |

## How retrieval actually works (one level deeper than README)
1. User submits a question via Streamlit. Streamlit POSTs to FastAPI `/chat`.
2. FastAPI calls `VectorStore.retrieve(question, top_k)`. Chroma embeds the prefixed query (`"query: <question>"`), does a cosine kNN against the stored passages.
3. Returned passages are wrapped in `RetrievedPassage` objects with the cosine score (`1 - distance`).
4. `generate()` detects the question language, builds a system prompt in that language, formats the passages with `[1]`, `[2]` markers and source metadata, calls the configured LLM provider.
5. Response is structured: `{ answer, citations[], language }`. Streamlit renders the answer in the right text direction with citations as an expandable panel.

## What broke during development
1. **Embedding-direction drift.** First attempt embedded queries and passages without the e5 prefix convention, retrieval recall@4 was ~50%. After adding `passage:` / `query:` prefixes, recall went to 100% on the eval set. Lesson: read the model card, not just the model name.
2. **RTL bleeding into Streamlit's chrome.** When I set `direction: rtl` on the answer panel, the surrounding Streamlit widgets inherited it on Firefox. Fix: scope the `dir` attribute to the answer `<div>` only, not the parent container.
3. **Chroma "embedding function mismatch" error** when re-opening a persisted collection. Fix: pass the same `embedding_function` to `get_or_create_collection` on every open. Now stored as a constant in `store.py`.

## What I'd do differently with more time
1. **Hybrid retrieval (BM25 + dense).** Pure dense misses rare numeric tokens like "SAR 1500". A simple BM25 reranker on top-20 → top-4 would help.
2. **Cross-encoder re-ranker.** A multilingual cross-encoder (e.g., `bge-reranker-v2-m3`) would meaningfully improve answer quality, at ~50ms latency cost.
3. **Real Ragas eval.** Right now the eval is bespoke. Ragas would give me faithfulness and answer relevancy with comparable metrics across versions.
4. **Stream the response.** With OpenAI/Anthropic streaming, perceived latency drops a lot. Streamlit supports it via generators.
5. **Drift monitoring.** No mechanism today to detect when newly ingested docs are out of distribution from the eval set.

## Likely interview questions + tight answers

**Q: Why multilingual-e5 instead of OpenAI embeddings?**
A: Three reasons — cost (free at scale), data residency (some employers won't send queries to OpenAI), and Arabic quality is competitive with paid options. e5-small specifically is a sweet spot of size (~118MB) and quality.

**Q: How would you evaluate this in production?**
A: Three layers. Offline: Ragas faithfulness + answer relevancy on a labeled set, retrieval recall@k. Online: thumbs-up/down on each answer logged to Postgres, weekly aggregate. Drift: embedding distance distribution of incoming questions vs. the eval set, alert on shift.

**Q: What's the biggest weakness of this design?**
A: The chunker doesn't understand document structure — it splits on paragraph and sentence but doesn't know "this is a table" or "this row maps to this header." For real insurance documents that's a problem; tables get shredded. Fix would be a structure-aware ingestion pass before chunking.

**Q: How would you handle 1000 concurrent users?**
A: Three changes. Replace local Chroma with a hosted vector DB (pgvector on Postgres or Pinecone). Move embeddings to a model server (Triton or HF Inference Endpoints) shared across replicas. Cache the top-N most common queries in Redis. The FastAPI layer scales horizontally behind a load balancer.

**Q: What stops a user from prompt-injecting their way past the system prompt?**
A: Today, nothing strong. The system prompt says "answer only from passages" but a sufficiently crafted user message can override it on most LLMs. Mitigation: structured output with a "claims_supported_by_passages" boolean the LLM has to set, and a downstream validator that checks claim spans against passages.

**Q: Why mock by default?**
A: Two reasons. Reviewers can clone and run the repo without any API key — that's a good first-impression bar. And in CI I don't want tests gated on a paid API; mock keeps the test surface deterministic.

**Q: What does "score" mean in the citation response?**
A: Cosine similarity between the query embedding and the passage embedding. e5 embeddings are normalized so cosine ranges roughly 0.0 to 1.0; in practice useful matches are >0.7.

**Q: Why is Arabic chunked at 700 chars but English at 1100?**
A: Arabic tokenizers produce more tokens per character — multilingual-e5 has a 512-token context, and at 700 Arabic chars I stay safely under. English averages closer to 4 chars/token, so I can use 1100. I tested both and 700/1100 stayed under the model limit on every chunk.

**Q: How do you prevent hallucination?**
A: Three layers. The system prompt explicitly says "if not in passages, say I don't know." The mock provider is extractive (so worst case is a low-quality answer, not a hallucinated one). And the citations array is part of the response contract — the UI displays them prominently so the user can verify.

**Q: What if a question matches passages in both languages?**
A: The retriever returns the top-k regardless of language. The generator's system prompt is in the question's language, but the passages can be in either. This is a feature in mixed-corpus situations: an Arabic question can be answered with citations to an English passage if it's the best match. The answer language matches the question.

**Q: Walk me through the Dockerfile.**
A: Python 3.11 slim base. Install libgomp1 for sentence-transformers. Pip-install deps. Copy src and data. Run `python -m src.rag.ingest data/sample` at build time so the image ships with the sample corpus already indexed. Set `PYTHONPATH=/app`. Default CMD is uvicorn on port 8000. The compose file adds a Streamlit container that points at the API.

**Q: Tests?**
A: pytest unit tests on language detection, chunker, and generator (mock provider). I don't unit-test Chroma itself — I treat it as a third-party dependency. CI runs ruff + pytest on every PR.

## Red flags Youssef should own (preempt the interviewer)
1. "The eval set is small (8 questions)." — "Yes, this is a v0.1 — for a real deployment I'd grow it to 200+ with stratified sampling across question types and languages."
2. "There's no real LLM in the demo run." — "Right, the mock provider is intentional so it runs end-to-end with no API key. There's a one-line env-var swap to use OpenAI or Anthropic; I just didn't want to gate the demo on a paid key."
3. "No live demo URL yet." — "Next on the roadmap. Hugging Face Spaces is the cheapest path; I have the Dockerfile ready."
4. "Test coverage is light." — "Honest answer: I prioritized end-to-end working pipeline over coverage. Highest-leverage tests next would be retrieval recall on a larger eval set."
