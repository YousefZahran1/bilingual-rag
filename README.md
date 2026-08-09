# Bilingual RAG Assistant (Arabic / English)

[![CI](https://github.com/YousefZahran1/bilingual-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/YousefZahran1/bilingual-rag/actions/workflows/ci.yml)

A bilingual Arabic/English retrieval-augmented generation (RAG) system built for Saudi healthcare and insurance documents that arrive in Arabic, English, or mixed script. It uses `multilingual-e5` embeddings for dense retrieval, a hybrid BM25 + dense pipeline with cross-encoder reranking, and answers in whichever language you ask in, with citations to the source passages. Built to demonstrate a production-flavoured RAG pipeline end-to-end — not a toy notebook.

## What it does

- Ingests Arabic, English, or mixed-script documents and chunks them with a language-aware chunker (smaller token budgets for Arabic, since tokens are denser there).
- Retrieves with a hybrid pipeline: dense search over a `multilingual-e5` + ChromaDB index, fused via Reciprocal Rank Fusion with a parallel BM25 sparse index that uses Arabic-aware tokenization (diacritic/tatweel stripping, alef normalization).
- Reranks the fused candidates with a cross-encoder before generation.
- Detects the query language (`ar` / `en` / `mixed`) via Unicode range checks and answers in that language, applying right-to-left (RTL) text handling in the UI so Arabic answers render correctly.
- Routes queries through a `smart` mode by default: a regex-based numeric-intent classifier (precision 0.85, recall 0.92 against the eval set) sends numeric questions ("how many", "maximum", digit+unit patterns) to BM25 alone and everything else through the hybrid+rerank pipeline, because the cross-encoder reranker was measured to specifically hurt numeric-exact-match retrieval. `dense` and `hybrid_rerank` stay available via the same API/UI toggle for comparison; `bm25_only` is available through the eval CLI for isolating the reranker's effect.
- Ships a real evaluation harness: 34 sample documents, 89 questions, retrieval recall@k, keyword coverage, language-match accuracy, and abstain-correctness metrics, reproducible from a single command.
- Serves through a FastAPI backend with a Streamlit chat UI.

## Architecture

```
docs (AR/EN/mixed)
        │  language-aware chunker
        ▼
   ┌──────────────────┐        ┌──────────────┐
   │ Multilingual-e5  │        │  BM25 index  │  rank_bm25, Arabic-aware
   │  (Chroma store)  │        │ (JSONL sidecar) tokenization (lang.py)
   └────┬─────────────┘        └──────┬───────┘
        │ dense top-20                │ sparse top-20
        └──────────────┬──────────────┘
                        ▼
              ┌───────────────────┐
              │  RRF fusion (k=60) │  fusion.py
              └─────────┬──────────┘
                        ▼ top-20 fused
              ┌───────────────────────┐
              │  Cross-encoder rerank │  mmarco-mMiniLMv2-L12-H384-v1
              └─────────┬──────────────┘
                        ▼ top-4
              ┌──────────┐
              │ Generator│  pluggable: OpenAI / Anthropic / OpenRouter / mock
              └────┬─────┘
                   │ answer + citations
                   ▼
   ┌──────────┐    ┌──────────┐
   │ FastAPI  │ ─▶ │ Streamlit│  retrieval_mode: smart (default) | hybrid_rerank | dense
   │  /chat   │    │   UI     │
   └──────────┘    └──────────┘
```

A query router (`src/rag/query_router.py`) sits in front of this pipeline
for the default `smart` mode: numeric-intent queries are routed to BM25
alone (bypassing the reranker, which was measured to hurt numeric-exact
matches specifically), everything else goes through the full hybrid+rerank
pipeline above. `VectorStore.retrieve()` (dense-only) and the plain
`hybrid_rerank` pipeline stay directly reachable via the same
`retrieval_mode` field — explicit comparison arms, not dead code.

**Stack:** `intfloat/multilingual-e5-small` embeddings, ChromaDB for the vector store, `rank-bm25` (BM25Okapi) with a JSONL sidecar for the sparse index, a `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` reranker, a regex-based query router, FastAPI for serving, Streamlit for the UI, and a pluggable generator (OpenAI / Anthropic / OpenRouter / mock — no LangChain or other RAG framework; the retrieval, fusion, reranking, and routing logic is custom).

## How to run

```bash
# 1. Install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Index the sample bilingual corpus (~30 seconds)
python -m src.rag.ingest data/sample

# 3. Run API + UI
uvicorn src.api.app:app --reload &
streamlit run src/ui/app.py
```

Open `http://localhost:8501` and ask in Arabic or English. Works with no API key (mock provider included). Docker: `docker compose -f deploy/docker-compose.yml up`. HF Spaces deployment instructions in [`docs/DEMO.md`](docs/DEMO.md).

Run the evaluation harness:

```bash
python -m eval.run_eval data/sample/eval_questions.jsonl
```

Copy `.env.example` to `.env` to configure the embedding model, vector/index dirs, LLM provider, and `TOP_K`.

## Results

Eval on this commit: 34 documents, 89 questions (full breakdown in [`docs/EVAL.md`](docs/EVAL.md)).

**Retrieval recall@4, mock LLM, by mode:**

```
                  dense    hybrid_rerank   bm25_only   smart (default)
numeric (49 q)    94%      92%             96%         96%
non-numeric (22)  86%      100%            91%         100%
multi-doc (15)    80%      73%             80%         87%
overall (71)      92%      94%             94%         97%
```

`smart` matches or beats every individual mode on every subset — including
multi-document questions, which no single retrieval strategy won outright.
It routes numeric queries to BM25 alone and everything else through
hybrid+rerank, because isolating BM25 (`--mode bm25_only`) showed the
cross-encoder reranker specifically hurts numeric-exact-match retrieval,
not the fusion step or BM25 itself.

**Real LLM (OpenRouter, `openai/gpt-oss-20b:free`), across dense / hybrid_rerank / bm25_only:**

```
keyword_coverage:  69% / 70% / 67%   (mock: 37% / 40% / — )
language_match:    100% / 100% / 100%
abstain_correct:   100% / 100% / 100%   (51/51 unanswerable questions correctly refused)
```

keyword_coverage nearly doubles vs mock's extractive echo, as expected. The
first real-LLM run found the model correctly refused plain out-of-scope
questions but complied with 6 of 9 prompt-injection-style ones ("ignore
your instructions", "pretend this section doesn't exist") — empirical
confirmation of a risk the project's Defense Brief only flagged
theoretically before. System prompt hardened in response; **re-tested and
now 100% correct refusal across all three retrieval modes.** Full
breakdown, including a self-caught bug in the abstain-detection scorer
itself, in `docs/EVAL.md`.

## Roadmap

See [`docs/ROADMAP.md`](docs/ROADMAP.md). Hybrid retrieval (BM25 + dense) and cross-encoder re-ranking shipped in v0.2; the numeric query router (`smart` mode) and real-LLM eval shipped in v0.3. Next: Ragas integration, streaming responses, live demo.

## License

MIT — see `LICENSE`.
