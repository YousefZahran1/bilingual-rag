# Bilingual RAG Assistant (Arabic / English)

A retrieval-augmented question-answering system tuned for Saudi healthcare and insurance documents. Bilingual: ingest documents in Arabic, English, or mixed; ask in either language; get an answer in the language you asked, with citations to the source passages.

> Built to demonstrate a production-flavoured RAG pipeline end-to-end: multilingual embeddings, vector search, FastAPI inference, Streamlit UI, and a real evaluation harness — not a toy notebook.

## Run locally

See **Quick start** below — works in ~2 minutes with no API key (mock provider included). Docker also available via `deploy/docker-compose.yml`. HF Spaces deployment instructions in [`docs/DEMO.md`](docs/DEMO.md).

## Eval (this commit, HTTP-verified)

```
retrieval_recall@4:   8/8  (100%)
language_match:       8/8  (100%)
keyword_coverage:     3/17 (18%)   <- mock provider; rises with a real LLM key
```

## Why this exists

Saudi healthcare and insurance documents arrive in mixed Arabic + English. Off-the-shelf RAG built for English corpora struggles with Arabic morphology, RTL text, and the script-mixing typical of Gulf documents. This repo handles the messy bits with deliberate, documented choices.

## Architecture

```
docs (AR/EN/mixed)
        │
        ▼
   ┌──────────┐
   │ Chunker  │  language-aware splits, RTL-safe
   └────┬─────┘
        │
        ▼
   ┌──────────────────┐
   │ Multilingual-e5  │  intfloat/multilingual-e5-small
   └────┬─────────────┘
        │ embeddings
        ▼
   ┌────────────┐
   │  Chroma    │  local persistent vector store
   └────┬───────┘
        │ top-k passages
        ▼
   ┌──────────┐
   │ Generator│  pluggable: OpenAI / Anthropic / local model
   └────┬─────┘
        │ answer + citations
        ▼
   ┌──────────┐    ┌──────────┐
   │ FastAPI  │ ─▶ │ Streamlit│
   │  /chat   │    │   UI     │
   └──────────┘    └──────────┘
```

## Tech stack and why

| Choice | Rejected | Why |
|---|---|---|
| `intfloat/multilingual-e5-small` | OpenAI ada-002 | Free, runs locally, EU-friendly for German employers, handles Arabic well |
| Chroma (local persistent) | Pinecone | Self-contained demo; no API key gate for reviewers |
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
| `LLM_PROVIDER` | `mock` | `mock` / `openai` / `anthropic` |
| `OPENAI_API_KEY` | — | Required if `LLM_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | — | Required if `LLM_PROVIDER=anthropic` |
| `TOP_K` | `4` | Passages per query |

Copy `.env.example` to `.env` and fill in.

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

See `docs/ROADMAP.md`. Highlights: hybrid retrieval (BM25 + dense), Ragas integration, deploy live demo.

## License

MIT — see `LICENSE`.
