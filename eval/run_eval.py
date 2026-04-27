"""Reproducible evaluation for the bilingual RAG pipeline.

Metrics:
  - retrieval_recall@k:   does the expected source appear in top-k?
  - keyword_coverage:     fraction of expected keywords present in answer
  - language_match:       does the answer language match the question language?

Usage:
    python -m eval.run_eval data/sample/eval_questions.jsonl --top-k 4
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from src.rag.generator import generate
from src.rag.lang import detect_language
from src.rag.store import VectorStore


def _load_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("eval_path", type=Path)
    ap.add_argument("--top-k", type=int, default=4)
    args = ap.parse_args()

    store = VectorStore()
    items = list(_load_jsonl(args.eval_path))
    print(f"Loaded {len(items)} eval questions.")

    n_correct_source = 0
    n_keywords_total = 0
    n_keywords_hit = 0
    n_lang_match = 0

    for item in items:
        q = item["question"]
        expected_source = item.get("expected_source", "")
        expected_keywords = item.get("expected_keywords", [])

        passages = store.retrieve(q, top_k=args.top_k)
        sources_in_topk = [p.source.split("/")[-1] for p in passages]
        if expected_source and any(expected_source in s for s in sources_in_topk):
            n_correct_source += 1

        result = generate(q, passages)
        ans_lower = result.answer.lower()
        for kw in expected_keywords:
            n_keywords_total += 1
            if kw.lower() in ans_lower:
                n_keywords_hit += 1

        q_lang = detect_language(q)
        if result.language == q_lang:
            n_lang_match += 1

    n = len(items)
    print()
    print(f"retrieval_recall@{args.top_k}:   {n_correct_source}/{n}  ({100*n_correct_source/n:.0f}%)")
    print(f"keyword_coverage:        {n_keywords_hit}/{n_keywords_total}  ({100*n_keywords_hit/max(n_keywords_total,1):.0f}%)")
    print(f"language_match:          {n_lang_match}/{n}  ({100*n_lang_match/n:.0f}%)")


if __name__ == "__main__":
    main()
