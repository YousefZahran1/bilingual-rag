# Evaluation Results

Run on the sample bilingual corpus (`data/sample/`) with the eval set in `data/sample/eval_questions.jsonl`.

## Latest snapshot (mock LLM, multilingual-e5-small embeddings, top_k=4)

| Metric | Result |
|---|---|
| retrieval_recall@4 | **8/8 (100%)** |
| keyword_coverage | **17/17 (100%)** — see caveat |
| language_match | **8/8 (100%)** |

> Caveat: with the mock LLM the "answer" is the concatenated retrieved passages, which is why keyword coverage is high. The retrieval and language-match numbers are the meaningful ones. Real LLM eval coming after wiring an API key.

## How to reproduce

```bash
python -m src.rag.ingest data/sample
python -m eval.run_eval data/sample/eval_questions.jsonl --top-k 4
```

## What the eval does NOT cover (yet)

- Faithfulness / hallucination (planned: Ragas integration)
- Latency / throughput (planned: simple `wrk` benchmark in `eval/perf.md`)
- Safety / refusal behavior (planned: red-team set in `eval/redteam.jsonl`)
