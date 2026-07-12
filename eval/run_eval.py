"""Reproducible evaluation for the bilingual RAG pipeline.

Metrics:
  - retrieval_recall@1:    does the top-1 passage match an expected source?
                            (any-of, for multi-source questions)
  - retrieval_recall@k:    do ALL expected sources appear in top-k?
                            (all-of -- stricter, since multi-source questions
                            are deliberately designed to need every source)
  - keyword_coverage:      fraction of expected keywords present in answer
  - language_match:        does the answer language match the question language?
  - abstain_correct:       for is_answerable=false questions, did the answer
                            correctly refuse rather than confidently answer?
                            NOTE: MockProvider is extractive and structurally
                            cannot abstain -- this metric is only meaningful
                            once a real LLM provider is used. See docs/EVAL.md.

--mode dense uses VectorStore.retrieve() (dense-only, unchanged baseline).
--mode hybrid_rerank uses src.rag.fusion.retrieve_pipeline() (BM25+dense RRF
fusion, then cross-encoder rerank) -- both draw from the same CLI so before/
after numbers can't drift apart from being run as separate scripts.

Usage:
    python -m eval.run_eval data/sample/eval_questions.jsonl --top-k 4 --mode dense
    python -m eval.run_eval data/corpus/eval_questions.jsonl --top-k 4 --mode hybrid_rerank --out eval/results/v0.2_hybrid.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List, Optional

from src.rag.bm25_index import BM25Index
from src.rag.fusion import retrieve_pipeline
from src.rag.generator import generate
from src.rag.lang import detect_language
from src.rag.reranker import CrossEncoderReranker
from src.rag.store import VectorStore

# Light EN/AR "refused to answer" phrase list -- not exhaustive, just enough
# to score the mock provider's structural inability to abstain vs a real
# LLM's actual refusals.
ABSTAIN_MARKERS = [
    "i don't know",
    "i do not know",
    "cannot find",
    "not in the passages",
    "not covered in",
    "no information",
    "لا أعرف",
    "لا يوجد",
    "غير متوفر",
    "لم أجد",
]


def _load_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _expected_sources(item: dict) -> List[str]:
    if item.get("expected_sources"):
        return list(item["expected_sources"])
    if item.get("expected_source"):
        return [item["expected_source"]]
    return []


def _basenames(passages) -> List[str]:
    # Split on both separators explicitly rather than pathlib.Path(...).name,
    # which is platform-native: a backslash-separated source string (e.g.
    # produced by ingesting on Windows) doesn't split correctly when this
    # code runs on Linux, since POSIX paths don't treat '\' as a separator.
    return [p.source.replace("\\", "/").rsplit("/", 1)[-1] for p in passages]


def _looks_like_abstain(answer: str) -> bool:
    lower = answer.lower()
    return any(marker in lower for marker in ABSTAIN_MARKERS)


def _retrieve(
    query: str,
    top_k: int,
    mode: str,
    store: VectorStore,
    bm25_index: Optional[BM25Index],
    reranker: Optional[CrossEncoderReranker],
):
    if mode == "hybrid_rerank":
        return retrieve_pipeline(
            query, store, bm25_index, reranker, top_k=top_k, fusion_top_n=max(20, top_k * 5)
        )
    return store.retrieve(query, top_k=top_k)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("eval_path", type=Path)
    ap.add_argument("--top-k", type=int, default=4)
    ap.add_argument("--mode", choices=["dense", "hybrid_rerank"], default="dense")
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write a versioned JSON snapshot of metrics + per-question breakdown",
    )
    args = ap.parse_args()

    store = VectorStore()
    bm25_index = BM25Index.load() if args.mode == "hybrid_rerank" else None
    reranker = CrossEncoderReranker() if args.mode == "hybrid_rerank" else None

    items = list(_load_jsonl(args.eval_path))
    print(f"Loaded {len(items)} eval questions.")

    n = len(items)
    n_recall_eligible = 0
    n_recall_1 = 0
    n_recall_k = 0
    n_keywords_total = 0
    n_keywords_hit = 0
    n_lang_match = 0
    n_abstain_eligible = 0
    n_abstain_correct = 0

    per_question = []

    for item in items:
        q = item["question"]
        expected = _expected_sources(item)
        expected_keywords = item.get("expected_keywords", [])
        is_answerable = item.get("is_answerable", True)
        tags = item.get("tags", [])

        passages = _retrieve(q, args.top_k, args.mode, store, bm25_index, reranker)
        basenames = _basenames(passages)

        recall_1_hit = None
        recall_k_hit = None
        if expected:
            n_recall_eligible += 1
            # recall@1: any expected source at position 1 (partial credit,
            # sensible even for multi-doc questions).
            recall_1_hit = bool(set(expected) & set(basenames[:1]))
            # recall@k: ALL expected sources present -- multi-doc questions
            # are deliberately designed to need every source.
            recall_k_hit = set(expected).issubset(set(basenames))
            n_recall_1 += int(recall_1_hit)
            n_recall_k += int(recall_k_hit)

        result = generate(q, passages)
        ans_lower = result.answer.lower()
        kw_hits = 0
        for kw in expected_keywords:
            n_keywords_total += 1
            if kw.lower() in ans_lower:
                n_keywords_hit += 1
                kw_hits += 1

        q_lang = detect_language(q)
        lang_hit = result.language == q_lang
        n_lang_match += int(lang_hit)

        abstain_hit = None
        if not is_answerable:
            n_abstain_eligible += 1
            abstain_hit = _looks_like_abstain(result.answer)
            n_abstain_correct += int(abstain_hit)

        per_question.append(
            {
                "question": q,
                "tags": tags,
                "is_answerable": is_answerable,
                "expected_sources": expected,
                "retrieved_sources": basenames,
                "recall_1_hit": recall_1_hit,
                "recall_k_hit": recall_k_hit,
                "keyword_hits": kw_hits,
                "keyword_total": len(expected_keywords),
                "language_match": lang_hit,
                "abstain_hit": abstain_hit,
            }
        )

    metrics = {
        "n_questions": n,
        "mode": args.mode,
        "top_k": args.top_k,
        "retrieval_recall@1": {"hit": n_recall_1, "total": n_recall_eligible},
        f"retrieval_recall@{args.top_k}": {"hit": n_recall_k, "total": n_recall_eligible},
        "keyword_coverage": {"hit": n_keywords_hit, "total": n_keywords_total},
        "language_match": {"hit": n_lang_match, "total": n},
        "abstain_correct": {"hit": n_abstain_correct, "total": n_abstain_eligible},
    }

    def pct(hit: int, total: int) -> str:
        return f"{100 * hit / total:.0f}%" if total else "n/a"

    print()
    print(f"mode:                     {args.mode}")
    print(
        f"retrieval_recall@1:       {n_recall_1}/{n_recall_eligible}  ({pct(n_recall_1, n_recall_eligible)})"
    )
    print(
        f"retrieval_recall@{args.top_k}:   {n_recall_k}/{n_recall_eligible}  ({pct(n_recall_k, n_recall_eligible)})"
    )
    print(
        f"keyword_coverage:        {n_keywords_hit}/{n_keywords_total}  ({pct(n_keywords_hit, n_keywords_total)})"
    )
    print(f"language_match:          {n_lang_match}/{n}  ({pct(n_lang_match, n)})")
    print(
        f"abstain_correct:         {n_abstain_correct}/{n_abstain_eligible}  ({pct(n_abstain_correct, n_abstain_eligible)})"
    )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as f:
            json.dump(
                {"metrics": metrics, "per_question": per_question},
                f,
                ensure_ascii=False,
                indent=2,
            )
        print(f"\nSnapshot written to {args.out}")


if __name__ == "__main__":
    main()
