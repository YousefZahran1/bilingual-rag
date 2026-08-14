# Bilingual RAG Assistant (Arabic / English)

[![CI](https://github.com/YousefZahran1/bilingual-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/YousefZahran1/bilingual-rag/actions/workflows/ci.yml)

A retrieval-augmented question-answering system tuned for Saudi healthcare and insurance documents. Bilingual: ingest documents in Arabic, English, or mixed; ask in either language; get an answer in the language you asked, with citations to the source passages.

> Built to demonstrate a production-flavoured RAG pipeline end-to-end: multilingual embeddings, vector search, FastAPI inference, Streamlit UI, and a real evaluation harness — not a toy notebook.

## Architecture

```mermaid
flowchart TD
    Docs["Documents (AR / EN / mixed)"] --> Chunk["Token-aware chunker<br/>400 tokens/chunk, measured with the<br/>e5 tokenizer -- see docs/TOKENIZATION.md"]
    Chunk --> Dense["① Native multilingual embeddings<br/>intfloat/multilingual-e5-small (Chroma)"]
    Chunk --> BM25idx["BM25 index<br/>Arabic-aware light normalization (lang.py)"]

    Query["User query (AR or EN)"] --> Router{"Numeric query?<br/>query_router.py"}
    Router -- "yes: counts, %, caps, SAR figures" --> BM25Search["BM25 search only<br/>(reranker specifically hurts these -- docs/EVAL.md)"]
    Router -- "no" --> Hybrid["② Hybrid search: dense top-20 + BM25 top-20<br/>→ Reciprocal Rank Fusion (k=60)<br/>→ ③ Cross-lingual reranker<br/>mmarco-mMiniLMv2-L12-H384-v1, 14 languages incl. Arabic"]
    Dense -.-> Hybrid
    BM25idx -.-> Hybrid
    BM25idx -.-> BM25Search

    BM25Search --> Passages["Top-4 passages + citations"]
    Hybrid --> Passages
    Passages --> Gen["④ Generator (pluggable: OpenAI / Anthropic / OpenRouter / mock)<br/>answers in the query's language -- 100% language_match, measured"]
    Gen --> API["FastAPI /chat"] --> UI["Streamlit UI (RTL-aware)"]
```

Four things this pipeline is built to get right for bilingual (Arabic/English) retrieval, all real and measured, not just architectural claims:

1. **Native multilingual embeddings** — `intfloat/multilingual-e5-small`, not English embeddings with documents translated on the fly.
2. **Hybrid search** — BM25 (with genuine Arabic-aware light normalization: diacritics/tatweel/alef-variant unification, *not* full morphological stemming — see `docs/TOKENIZATION.md`) fused with dense retrieval via Reciprocal Rank Fusion (k=60), so exact-term and semantic matching both contribute.
3. **Cross-lingual reranking** — `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` covers 14 languages including Arabic; a numeric-query router (`query_router.py`) bypasses it specifically for numeric questions, where it was empirically found to hurt (`docs/EVAL.md`).
4. **Language-consistent synthesis** — the generator answers in the language the question was asked in; measured at **100% language_match (89/89)** across every mock and real-LLM eval run this project has recorded.

`VectorStore.retrieve()` (dense-only) and `retrieve_pipeline()` (unconditional hybrid+rerank) both stay reachable via `retrieval_mode: dense | hybrid_rerank | smart` on `/chat` — `smart` (the router above) is the default because it matches or beats the other two on every measured subset, not because the alternatives are dead code; they're the explicit "before" comparison arms.

## Run locally

See **Quick start** below — works in ~2 minutes with no API key (mock provider included). Docker also available via `deploy/docker-compose.yml`. HF Spaces deployment instructions in [`docs/DEMO.md`](docs/DEMO.md).

## Eval (this commit, 34 docs / 89 questions — full breakdown in `docs/EVAL.md`)

**Mock LLM** (retrieval-only, zero API cost):

| Metric | **smart** (default) | dense | hybrid_rerank | bm25_only |
|---|---|---|---|---|
| retrieval_recall@1 | **59/71 (83%)** | 58/71 (82%) | 57/71 (80%) | 57/71 (80%) |
| retrieval_recall@4 | **69/71 (97%)** | 67/71 (94%) | 67/71 (94%) | 66/71 (93%) |
| keyword_coverage | 29/95 (31%) | 30/95 (32%) | 29/95 (31%) | 28/95 (29%) |
| language_match | 89/89 (100%) | 89/89 (100%) | 89/89 (100%) | 89/89 (100%) |

**Real LLM** (OpenRouter, `openai/gpt-oss-20b:free`) — predates the
token-based chunking switch and hasn't been re-run for `smart` mode yet
(blocked on a working OpenRouter key, see `docs/ROADMAP.md`); recall/
language numbers are provider-independent, so the mock table above is a
close proxy for what a fresh run would show:

| Metric | dense | hybrid_rerank | bm25_only |
|---|---|---|---|
| keyword_coverage | 69% | 70% | 67% |
| language_match | 100% | 100% | 100% |
| abstain_correct | 100% | 100% | 100% |

`smart` (a numeric query router — routes counts/percentages/caps to BM25
alone, everything else through hybrid+rerank) is the default `retrieval_mode`
because it matches or beats every single-strategy mode on every measured
subset. It exists because hybrid+rerank isn't a uniform win: it's a clear
improvement on non-numeric questions (recall@4 hits 100%) but a small
regression on numeric-exact-match questions — isolating BM25 alone
(`--mode bm25_only`) showed the regression is specifically caused by the
cross-encoder reranker, not by BM25 or the RRF fusion step. All four modes
stay exposed as a real API/UI toggle, not just the default.

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

## Tech stack and why

| Choice | Rejected | Why |
|---|---|---|
| `intfloat/multilingual-e5-small` | OpenAI ada-002 | No API key needed, runs locally, strong Arabic morphology support |
| Chroma (local persistent) | Pinecone | Self-contained demo; no API key gate for reviewers |
| `rank-bm25` (BM25Okapi) | Elasticsearch/OpenSearch | One light pure-Python dependency vs standing up a search service for a demo repo |
| Reciprocal Rank Fusion, fixed k=60 | Tuned/learned fusion weight | Literature-standard constant; tuning a hyperparameter against this project's own 89-question eval set and citing the result would be a credibility risk |
| `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` | `BAAI/bge-reranker-v2-m3`, Cohere Rerank-3/3.5 | mmarco covers 14 languages incl. Arabic at ~80MB vs bge's ~2.2GB (same small-model philosophy as picking `e5-small` over larger e5 variants); Cohere has best-in-class Arabic reranking but requires a paid API key, which breaks this project's zero-cost-to-run design — every provider choice here was made free/local-first |
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

Reproduces the table in `docs/EVAL.md`: retrieval recall@k, answer faithfulness, language-match accuracy. See `docs/TOKENIZATION.md` for the measured (not estimated) Arabic-vs-English token density behind the chunker's token budget.

## Deployment

`deploy/Dockerfile` + `deploy/docker-compose.yml`. One-command bring-up:

```bash
docker compose -f deploy/docker-compose.yml up
```

For free-tier hosting: Hugging Face Spaces (Streamlit template) or Fly.io.

## Roadmap

See `docs/ROADMAP.md`. Hybrid retrieval (BM25 + dense), cross-encoder re-ranking, the numeric query router (`smart` mode), and token-based chunking have shipped. Next: Ragas integration, deploy live demo.

## License

MIT — see `LICENSE`.
