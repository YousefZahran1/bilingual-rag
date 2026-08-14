# Unified retrieval pipeline

The production retrieval architecture, implemented in `src/rag/pipeline.py`.
Built on the findings in `docs/RETRIEVAL_TUNING.md` (chunk-size sweep,
structure-aware chunking, parent-child, and the RAG/legal literature).

## Ingestion (`UnifiedIndex.build`)

```
document ──► infer metadata + route by doc_type
                 │
   structured (contract/policy/formulary/guideline) ──► structure-aware chunking
   unstructured (FAQ/prose)                          ──► sentence/token chunking
                 │
        parent-child split: parents ≤900 tok, children ≤200 tok (nested)
                 │
   children ──► Chroma vector index (e5, "passage:" prefix)  + BM25 sidecar
   parents  ──► parents.json ;  child metadata ──► child_meta.json
```

**Layout-aware ingestion.** `scripts/extract_pdfs.py` extracts source
documents with **PyMuPDF** (better reading order + RTL Arabic + born-digital
tables than pypdf, which stays as a fallback) and also accepts **.docx** via
python-docx. Engine is selectable with `EXTRACT_ENGINE=pymupdf|pypdf`.

**Step 1 — routing.** `infer_doc_type` (filename-first, body-scan fallback)
tags each doc (`contract`, `policy`, `formulary`, `guideline`, `faq`,
`document`); structured legal/regulatory types get the structure-aware chunker,
everything else falls back to sentence chunking. Both go through parent-child so
retrieval is precise and generation gets context.

**Step 2 — metadata.** Every child carries `doc_id, doc_title, doc_type,
version, effective_date, language, clause_number, parent_id`. This enables
**pre-search filtering** — narrowing the candidate set *before* the vector
search. Verified on the real corpus: the same query with `doc_type=formulary`
returns only formulary parents, `doc_type=contract` only the contract, and
`doc_type=policy` only the two policy docs.

## Retrieval (`UnifiedIndex.retrieve`)

**Step 3 — hybrid + parent expansion (the default path):**

1. **Dense** search (multilingual-e5-small) over children — with optional
   metadata `where` filter.
2. **Lexical** BM25 search over the same children (metadata-filtered via the
   child-meta map, since the lexical index can't use Chroma's `where`).
3. **Reciprocal Rank Fusion** (k=60) combines the two rankings.
4. Top fused children are **expanded to their parent sections** (de-duplicated),
   and those parents are what the LLM receives.

### Result on the real CCHI corpus (15 grounded questions)

| Config | parent recall (top-4) | context keyword coverage |
|---|---|---|
| **Unified: hybrid + parent** | **15/15 (100%)** | **26/26 (100%)** |
| structure-aware, dense only | 12/15 | 42% (mock) |
| token@200, dense only | 10/15 | 15% (mock) |

Hybrid fusion + parent expansion is the strongest configuration measured —
perfect source recall and 100% of expected answer-facts present in the context
handed to the generator.

## Two-stage (hierarchical) retrieval — `retrieve_two_stage`

For large corpora (hundreds of documents) a second, hierarchical path is
available:

1. **Document routing** — a lightweight **parent-summary** vector index
   (`unified_children_parents`) is searched first to pick a candidate set of
   documents.
2. **Clause search** — hybrid dense+BM25+RRF over children, restricted to those
   documents.
3. **Re-ranking** — a cross-encoder (`RERANKER_MODEL`, default the multilingual
   `mmarco-mMiniLMv2`) re-scores the top ~24 children so the best clause lands
   at rank 1.
4. **Parent expansion** — as above.

### When to use which (measured on the real 4-doc corpus)

| Pipeline | parent recall | keyword coverage |
|---|---|---|
| **single-stage (hybrid + parent)** | **15/15 (100%)** | **26/26 (100%)** |
| two-stage (route + hybrid + rerank\*) | 14/15 (93%) | 23/26 (88%) |

\*sandbox test used a small **English** cross-encoder (the multilingual one
wouldn't download here), which handicaps Arabic. On a 4-document corpus,
document routing can only lose recall and the reranker adds no benefit, so
**single-stage is the default and the recommended config at this scale.**
Two-stage is implemented and correct (routing + filter + rerank all verified)
and is expected to win once the corpus grows to hundreds of documents and the
multilingual reranker is used — the standard hierarchical-RAG result.

## Step 4 — vector index / scaling

The index is **Chroma PersistentClient** with an **HNSW / cosine** child
collection and **payload metadata filtering** (used for the doc_type filtering
above) — so it already satisfies the "persistent DB + metadata filter + HNSW"
requirement at this scale. Migration path if volume grows into the millions of
chunks: swap the `_collection()` backend for **Qdrant** or **pgvector** (both
give the same payload-filter + HNSW semantics); the parent/child-meta sidecars
and the retrieval logic are backend-agnostic.

## Step 5 — regression benchmarking

`scripts/bench_pipeline.py` ingests a corpus and scores the production
retrieval path against that corpus's `eval_questions.jsonl`, exiting non-zero if
recall or keyword coverage drops below a threshold — a CI gate for new ingests.

```
python scripts/bench_pipeline.py --data data/real            # build + bench
python scripts/bench_pipeline.py --data data/real --no-build # bench existing
```

**Convention:** for every major document added to a corpus, add 5–10 grounded
Q&A pairs to that corpus's `eval_questions.jsonl`, then run the bench to confirm
the new docs don't regress recall/keyword coverage on existing queries.

## Wired in v0.5

`src/api/app.py`'s `/chat` and `src/ui/app.py`'s Streamlit sidebar both
expose `retrieval_mode: unified | unified_two_stage` alongside the legacy
`dense | hybrid_rerank | smart` modes.

- `ChatRequest.filters: dict[str, str] | None` — allowlisted keys
  (`doc_type`, `language`, `doc_id`, `version`) validated with a Pydantic
  `field_validator`; unknown keys reject with `422` before touching Chroma.
  The UI surfaces `doc_type`/`language` as sidebar select boxes when a
  unified mode is chosen.
- `Citation` gained optional `doc_type`, `doc_title`, `clause` fields.
  `RetrievedPassage` (`src/rag/store.py`) carries the same three fields,
  populated by `UnifiedIndex._expand_to_parents` and `None` for every
  legacy retrieval path, so old citation shapes are unaffected.
- If the index hasn't been built (`parents.json`/`child_meta.json` missing),
  `/chat` returns `409` with `{"error": "unified index not built", "fix":
  "python -m src.rag.pipeline build data/real"}` instead of a 500 or a
  silent empty result. `/health` reports `unified_index: "ready" |
  "not_built"` so the UI can warn before the first query instead of after.
- `UnifiedIndex` now has a CLI entrypoint: `python -m src.rag.pipeline build
  <data_dir> [--persist <dir>]` (defaults to `$UNIFIED_INDEX_DIR` or
  `./unified_index`) — `deploy/Dockerfile` runs this against `data/real` at
  image build time (see "Deploy" below).

### Eval parity (`eval/run_eval.py --mode unified|unified_two_stage`)

Both modes are now first-class `eval/run_eval.py` choices (`--unified-dir`
points at a pre-built index; the harness refuses to run and prints the
build command if it's missing, rather than silently erroring deep inside
retrieval). Full numbers in `README.md`'s "Unified retrieval pipeline"
section and `eval/results/v0.5_unified*.json`. Headline: `unified` beats
every other mode on `data/sample`'s recall@4 (96% vs `smart`/`hybrid_rerank`'s
93%) and language_match (92% vs 90%), but loses keyword_coverage to
`hybrid_rerank` (47% vs 58%) — so it is **not** the default `retrieval_mode`
per the "must match or beat `smart` on both recall@4 and keyword_coverage"
rule. On `data/real` it ties the bench_pipeline.py numbers above (15/15
parent recall); `keyword_coverage` under `eval/run_eval.py`'s `MockProvider`
reads much lower there (2/26, 8%) than `bench_pipeline.py`'s 100% — that's
the same known mock-provider truncation caveat documented in
`docs/EVAL.md` (MockProvider echoes the first 300 characters of the
concatenated *answer*, not the full retrieved *context* that
`bench_pipeline.py` scores directly), not a real regression.

### Deploy

`deploy/Dockerfile` builds the `UnifiedIndex` from `data/real` (not
`data/sample`) at image build time, into `$UNIFIED_INDEX_DIR`
(`/data/unified_index`) — the real corpus is what has actual clause
numbers and `doc_type` metadata worth filtering on; `data/sample` is
mostly unstructured prose ingested separately for the legacy modes.
