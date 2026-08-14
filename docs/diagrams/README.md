# Module flowcharts

Hand-checked visual explanations of the core modules, verified line-by-line
against the code they document.

| Diagram | Module | Notes |
|---|---|---|
| ![chunker](01-chunker-v01.jpg) | `src/rag/chunker.py` | **v0.1 baseline** — depicts the original character-budget chunker (ar 700 / en 1100 / mixed 900, overlap 120). Superseded in v0.3+ by the token-aware chunker (`CHUNK_MAX_TOKENS=200`, `CHUNK_STRATEGY=token\|structure`); kept as the documented starting point of the chunking evolution in `RETRIEVAL_TUNING.md`. |
| ![store](02-ingestion-store.jpg) | `src/rag/ingest.py`, `src/rag/store.py` | Dense ingestion/retrieval path: lazy Chroma init, `source::chunk_id` idempotent upsert, e5 `query:` prefix, `score = 1 − distance`. This is the `dense` retrieval mode; BM25/RRF/rerank layers sit on top (see `PIPELINE.md`). |
| ![generator](03-generator.jpg) | `src/rag/generator.py` | Bilingual prompt selection (AR/EN), provider dispatch via `LLM_PROVIDER`, mock extractive fallback. Note: citations are built directly from the retrieved passages, not parsed from the model's answer. OpenRouter provider added after this diagram. |
| ![lifecycle](04-request-lifecycle.jpg) | `src/api/app.py`, `src/ui/app.py` | Streamlit → httpx → FastAPI (Pydantic validation) → retrieve + generate → typed response → RTL-aware rendering. Drawn before the `retrieval_mode` toggle was added. |
| ![eval](05-eval-harness.jpg) | `eval/run_eval.py` | The three baseline metrics (recall@k, keyword_coverage, language_match) on the original 8-question set. The harness has since grown (89 questions, abstain metrics, `--mode`). |
