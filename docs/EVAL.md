# Evaluation Results

Run on the corpus in `data/sample/` (34 documents) with the eval set in
`data/sample/eval_questions.jsonl` (89 questions). v0.1 had 5 documents and 8
questions — recall@4 was saturated at 100%, which meant the eval wasn't
actually testing anything. This is the honest v0.2 read.

## How to reproduce

```bash
python -m src.rag.ingest data/sample --reset
python -m eval.run_eval data/sample/eval_questions.jsonl --top-k 4 --mode dense --out eval/results/v0.2_dense.json
python -m eval.run_eval data/sample/eval_questions.jsonl --top-k 4 --mode hybrid_rerank --out eval/results/v0.2_hybrid.json
```

Every run writes a versioned JSON snapshot (metrics + per-question
breakdown) to `eval/results/`. Numbers below are read directly from those
committed snapshots, not hand-edited.

## Headline numbers (mock LLM, multilingual-e5-small + BM25 + mmarco-mMiniLMv2 reranker, top_k=4)

| Metric | dense | hybrid_rerank |
|---|---|---|
| retrieval_recall@1 | 59/71 (83%) | 58/71 (82%) |
| retrieval_recall@4 | 65/71 (92%) | 67/71 (94%) |
| keyword_coverage | 35/95 (37%) | 38/95 (40%) — see mock caveat |
| language_match | 89/89 (100%) | 89/89 (100%) |
| abstain_correct | 0/18 (0%) | 0/18 (0%) — see mock caveat |

(`total` for recall is 71, not 89 — 18 questions are `is_answerable: false`
and deliberately have no expected source.)

## The honest finding: hybrid+rerank does NOT help uniformly

The plan going into this work hypothesized that hybrid retrieval would win
disproportionately on numeric questions (BM25's exact-token matching should
beat dense embeddings, which blur numbers). **That hypothesis was wrong.**
Breaking the 89-question set down by tag:

| Subset | dense recall@1 | hybrid recall@1 | dense recall@4 | hybrid recall@4 |
|---|---|---|---|---|
| numeric (49 q) | 84% (41/49) | 80% (39/49) | 94% (46/49) | 92% (45/49) |
| non-numeric (22 q) | 82% (18/22) | 86% (19/22) | 86% (19/22) | **100% (22/22)** |
| multi-document (15 q) | 93% (14/15) | 80% (12/15) | 80% (12/15) | 73% (11/15) |

Hybrid+rerank is a clear win on non-numeric/conceptual questions (recall@4
goes to a perfect 100%), roughly flat on the overall average, and actually
*worse* on numeric-exact-match and multi-document questions.

**Why, mechanistically:** the reranker
(`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`) is trained on MS MARCO
passage relevance — general semantic matching, not exact numeric matching.
When RRF fusion mixes in BM25's precise numeric-term hit alongside dense
candidates, the cross-encoder can still re-rank a "semantically similar but
numerically wrong" passage above it, because semantic similarity is what it
was trained to score. BM25 alone would likely do better on the numeric
subset than the full hybrid+rerank pipeline; this eval doesn't isolate that
(worth adding as a third `--mode bm25_only` if this gets investigated
further — see `docs/ROADMAP.md`).

This is why `retrieval_mode` is exposed as a real, user-facing choice in the
API/UI rather than hybrid_rerank silently replacing dense-only: the two
modes have different, honestly-measured strengths.

## Mock provider caveats

- **keyword_coverage** is inflated/deflated by `MockProvider` being
  extractive (it echoes retrieved passage text rather than generating a real
  answer) — it will change once a real LLM provider (`OPENAI_API_KEY` or
  `ANTHROPIC_API_KEY`) is wired in. Retrieval numbers (recall@1, recall@4)
  are provider-independent and are the meaningful ones here.
- **abstain_correct** is 0/18 under mock by construction: `MockProvider`
  cannot refuse to answer, it always echoes whatever passages it retrieved,
  relevant or not. This metric only becomes meaningful once a real LLM
  provider is used — it exists in the harness now so that comparison is
  possible later without further schema changes.

## What the eval does NOT cover (yet)

- Faithfulness / hallucination (planned: Ragas integration, see `docs/ROADMAP.md`)
- Latency / throughput
- The eval questions were authored by the same process that authored the
  documents (an LLM, in one pass) — `eval/validate_eval_set.py` (run as
  `tests/test_eval_set_integrity.py` in CI) checks that every claimed
  keyword actually appears in its source document, which catches "true in
  the author's head but never written down" errors, but it cannot prove the
  questions are hard or representative of real user phrasing. A human
  spot-check of ~15-20 questions is still recommended before citing these
  numbers as fully independent evidence.
