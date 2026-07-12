# Bilingual RAG Assistant (Arabic / English)

[![CI](https://github.com/YousefZahran1/bilingual-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/YousefZahran1/bilingual-rag/actions/workflows/ci.yml)

A retrieval-augmented question-answering system tuned for Saudi healthcare and insurance documents. Bilingual: ingest documents in Arabic, English, or mixed; ask in either language; get an answer in the language you asked, with citations to the source passages.

> Built to demonstrate a production-flavoured RAG pipeline end-to-end: multilingual embeddings, vector search, FastAPI inference, Streamlit UI, and a real evaluation harness — not a toy notebook.

## Run locally

See **Quick start** below — works in ~2 minutes with no API key (mock provider included). Docker also available via `deploy/docker-compose.yml`. HF Spaces deployment instructions in [`docs/DEMO.md`](docs/DEMO.md).

## Eval (this commit, 34 docs / 89 questions — full breakdown in `docs/EVAL.md`)

```
mock LLM:             dense          hybrid_rerank   bm25_only
retrieval_recall@1:   59/71 (83%)    58/71 (82%)     58/71 (82%)
retrieval_recall@4:   65/71 (92%)    67/71 (94%)     67/71 (94%)
keyword_coverage:     35/95 (37%)   38/95 (40%)      —
language_match:       89/89 (100%)  89/89 (100%)     —

real LLM (OpenRouter, openai/gpt-oss-20b:free):
keyword_coverage:     69%            70%             67%
language_match:       100%           100%            100%
abstain_correct:      100%           100%            100%
```

Hybrid+rerank isn't a uniform win — it's a clear improvement on non-numeric
questions (recall@4 hits 100%) and a small regression on numeric-exact-match
questions. Isolating BM25 alone (`--mode bm25_only`) shows the regression is
specifically caused by the cross-encoder reranker, not by BM25 or the RRF
fusion step — BM25 alone actually has the *best* numeric recall@4 of the
three modes. `retrieval_mode` is exposed as a real API/UI toggle so all modes
are usable, not just the default.

**Real LLM findings:** keyword_coverage nearly doubles vs mock's extractive
echo, as expected. The interesting one: the first real-LLM run found the
model correctly refused plain out-of-scope questions but complied with 6 of
9 prompt-injection-style ones ("ignore your instructions", "pretend this
section doesn't exist") — empirical confirmation of a risk the Defense Brief
only flagged theoretically before. System prompt hardened in response;
**re-tested and now 100% correct refusal across all three retrieval modes**
(51/51 unanswerable questions that got a real answer). Full breakdown,
including a self-caught bug in the abstain-detection scorer itself, in
`docs/EVAL.md`.

## Why this exists

Saudi healthcare and insurance documents arrive in mixed Arabic + English. Off-the-shelf RAG built for English corpora struggles with Arabic morphology, RTL text, and the script-mixing typical of Gulf documents. This repo handles the messy bits with deliberate, documented choices.

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
   │ FastAPI  │ ─▶ │ Streamlit│  retrieval_mode: dense | hybrid_rerank
   │  /chat   │    │   UI     │
   └──────────┘    └──────────┘
```

`VectorStore.retrieve()` (dense-only) is still directly reachable via
`retrieval_mode: "dense"` — it's the explicit "before" comparison arm, not
dead code.

## Tech stack and why

| Choice | Rejected | Why |
|---|---|---|
| `intfloat/multilingual-e5-small` | OpenAI ada-002 | No API key needed, runs locally, strong Arabic morphology support |
| Chroma (local persistent) | Pinecone | Self-contained demo; no API key gate for reviewers |
| `rank-bm25` (BM25Okapi) | Elasticsearch/OpenSearch | One light pure-Python dependency vs standing up a search service for a demo repo |
| Reciprocal Rank Fusion, fixed k=60 | Tuned/learned fusion weight | Literature-standard constant; tuning a hyperparameter against this project's own 89-question eval set and citing the result would be a credibility risk |
| `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` | `BAAI/bge-reranker-v2-m3` | ~80MB vs ~2.2GB; keeps the same small-model philosophy as picking `e5-small` over larger e5 variants |
| JSONL sidecar for the BM25 index | Binary-serializing `BM25Okapi` | Human-diffable, safe to commit, survives library/Python version upgrades; rebuild from tokenized text is fast and pure Python |
| OpenRouter (`openai` SDK, custom `base_url`) | Only OpenAI/Anthropic direct | Free-tier access to real models for eval at no cost; OpenRouter's chat completions API is a drop-in OpenAI-compatible endpoint, so no new HTTP client dependency was needed |
| FastAPI | Flask, Django | Async + types + auto OpenAPI |
| Streamlit | React/Next | Ships in hours; recruiters know it |
| Ragas-style eval | manual eval | Reproducible numbers committed in `docs/EVAL.md` |

## Quick start

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

Open `http://localhost:8501` and ask in Arabic or English.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-small` | Embeddings model |
| `VECTOR_DIR` | `./chroma_db` | Where Chroma persists |
| `INDEX_DIR` | `./index_data` | Where the BM25 sidecar persists |
| `LLM_PROVIDER` | `mock` | `mock` / `openai` / `anthropic` / `openrouter` |
| `OPENAI_API_KEY` | — | Required if `LLM_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | — | Required if `LLM_PROVIDER=anthropic` |
| `OPENROUTER_API_KEY` | — | Required if `LLM_PROVIDER=openrouter` |
| `OPENROUTER_MODEL` | `openai/gpt-oss-20b:free` | Any OpenRouter model id; pick a non-expiring free one — check openrouter.ai/models for "going away" flags |
| `TOP_K` | `4` | Passages per query |

Copy `.env.example` to `.env` and fill in. `.env` is loaded automatically
(via `python-dotenv`) by every entrypoint — the API, the UI, `ingest.py`,
and `eval/run_eval.py`.

## Evaluation

```bash
python -m eval.run_eval data/sample/eval_questions.jsonl
```

Reproduces the table in `docs/EVAL.md`: retrieval recall@k, answer faithfulness, language-match accuracy.

## Deployment

`deploy/Dockerfile` + `deploy/docker-compose.yml`. One-command bring-up:

```bash
docker compose -f deploy/docker-compose.yml up
```

For free-tier hosting: Hugging Face Spaces (Streamlit template) or Fly.io.

## Roadmap

See `docs/ROADMAP.md`. Hybrid retrieval (BM25 + dense) and cross-encoder re-ranking shipped in v0.2. Next: Ragas integration, deploy live demo.

## License

MIT — see `LICENSE`.
