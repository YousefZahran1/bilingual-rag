"""External benchmark: MIRACL (Multilingual Information Retrieval Across a
Continuum of Languages), Arabic dev split -- retrieval recall on a public
set with human-annotated relevance judgments this project didn't author.
Every other eval number in this repo (docs/EVAL.md) comes from a
self-authored question set; this is the one number with independent ground
truth, reported here even though it's a narrower comparison than the other
"real" evals -- see "Methodology, honestly" below.

Usage:
    python scripts/bench_miracl.py                          # 200 queries, seed 42
    python scripts/bench_miracl.py --n-queries 500 --seed 7
    python scripts/bench_miracl.py --out eval/results/miracl_ar.json

Methodology, honestly:
    The official MIRACL benchmark retrieves each query against the FULL
    language corpus (~2M passages for Arabic) built from Wikipedia. Indexing
    2M passages with e5 embeddings is a real undertaking (hours of compute,
    GBs of storage) that doesn't fit this project's zero-cost-to-run design.
    Instead, this script scores recall over each query's own MIRACL-provided
    candidate pool (positive_passages + negative_passages, ~10-15 passages
    per query) -- the same passages MIRACL's own annotators judged for that
    query. This is a real, externally-authored, human-annotated retrieval
    task, but a substantially *easier* one than full-corpus retrieval (far
    fewer distractors), so these recall numbers are NOT comparable to the
    official MIRACL leaderboard and should never be quoted as such -- they
    measure "can the model tell the relevant passage apart from a curated
    set of judged distractors for this query," not "can it find the needle
    in 2 million passages." Reported as what it is, not oversold.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.rag.bm25_index import BM25Index
from src.rag.chunker import Chunk
from src.rag.fusion import reciprocal_rank_fusion

EMBED_MODEL = os.environ.get("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")


def _load_miracl_dev(lang: str, split: str):
    import pandas as pd
    from huggingface_hub import hf_hub_download

    path = hf_hub_download(
        "miracl/miracl", f"{lang}/{split}/0000.parquet",
        repo_type="dataset", revision="refs/convert/parquet",
    )
    return pd.read_parquet(path)


def _pool_for_query(row) -> tuple[list[dict], set[str]]:
    """De-duplicated candidate pool (positives + negatives) and the set of
    relevant docids for this query."""
    seen: dict[str, dict] = {}
    positive_ids: set[str] = set()
    for p in row["positive_passages"]:
        seen[p["docid"]] = p
        positive_ids.add(p["docid"])
    for p in row["negative_passages"]:
        seen.setdefault(p["docid"], p)
    return list(seen.values()), positive_ids


def _cosine_ranking(query_vec: np.ndarray, doc_vecs: np.ndarray, docids: list[str]) -> list[str]:
    sims = doc_vecs @ query_vec
    order = np.argsort(-sims)
    return [docids[i] for i in order]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="ar")
    ap.add_argument("--split", default="dev")
    ap.add_argument("--n-queries", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--top-k", type=int, default=4)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    print(f"Loading MIRACL {args.lang}/{args.split}...")
    df = _load_miracl_dev(args.lang, args.split)
    # Only queries with at least one positive AND at least one negative are
    # meaningful for recall (a query with zero negatives can't miss).
    df = df[
        df["positive_passages"].apply(len).gt(0) & df["negative_passages"].apply(len).gt(0)
    ].reset_index(drop=True)
    print(f"{len(df)} queries have both positive and negative judgments.")

    rng = random.Random(args.seed)
    idx = list(range(len(df)))
    rng.shuffle(idx)
    sample_idx = sorted(idx[: args.n_queries])
    sample = df.iloc[sample_idx].reset_index(drop=True)
    print(f"Subsampled {len(sample)} queries (seed={args.seed}).")

    print(f"Loading embedding model {EMBED_MODEL}...")
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMBED_MODEL)

    n_dense_r1 = n_dense_rk = n_hybrid_r1 = n_hybrid_rk = 0
    per_query = []

    for _, row in sample.iterrows():
        pool, positive_ids = _pool_for_query(row)
        docids = [p["docid"] for p in pool]
        texts = [p["text"] for p in pool]

        doc_vecs = model.encode(
            [f"passage: {t}" for t in texts], normalize_embeddings=True, show_progress_bar=False
        )
        query_vec = model.encode(
            f"query: {row['query']}", normalize_embeddings=True, show_progress_bar=False
        )
        dense_ranking = _cosine_ranking(query_vec, doc_vecs, docids)

        chunks = [Chunk(text=t, source=d, chunk_id=i, language=args.lang) for i, (d, t) in enumerate(zip(docids, texts))]
        bm25 = BM25Index(chunks)
        bm25_hits = bm25.search(row["query"], top_k=len(docids))
        bm25_ranking = [h.source for h in bm25_hits]

        fused = reciprocal_rank_fusion([dense_ranking, bm25_ranking])
        hybrid_ranking = [doc_id for doc_id, _ in fused]

        k = args.top_k
        dense_r1 = dense_ranking[0] in positive_ids
        dense_rk = bool(set(dense_ranking[:k]) & positive_ids)
        hybrid_r1 = hybrid_ranking[0] in positive_ids
        hybrid_rk = bool(set(hybrid_ranking[:k]) & positive_ids)

        n_dense_r1 += int(dense_r1)
        n_dense_rk += int(dense_rk)
        n_hybrid_r1 += int(hybrid_r1)
        n_hybrid_rk += int(hybrid_rk)

        per_query.append(
            {
                "query_id": str(row["query_id"]),
                "pool_size": len(pool),
                "n_positive": len(positive_ids),
                "dense_recall@1": dense_r1,
                f"dense_recall@{k}": dense_rk,
                "hybrid_recall@1": hybrid_r1,
                f"hybrid_recall@{k}": hybrid_rk,
            }
        )

    n = len(sample)
    k = args.top_k

    def pct(x: int) -> str:
        return f"{100 * x / n:.1f}%" if n else "n/a"

    print()
    print(f"MIRACL {args.lang}/{args.split}, {n} queries (seed={args.seed}), pool-based recall (see module docstring):")
    print(f"  dense_recall@1:    {n_dense_r1}/{n}  ({pct(n_dense_r1)})")
    print(f"  dense_recall@{k}:    {n_dense_rk}/{n}  ({pct(n_dense_rk)})")
    print(f"  hybrid_recall@1:   {n_hybrid_r1}/{n}  ({pct(n_hybrid_r1)})")
    print(f"  hybrid_recall@{k}:   {n_hybrid_rk}/{n}  ({pct(n_hybrid_rk)})")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "methodology": "pool-based recall over MIRACL-provided positive+negative "
                    "passages per query, NOT full-corpus (~2M passage) retrieval -- not "
                    "comparable to the official MIRACL leaderboard. See module docstring.",
                    "lang": args.lang,
                    "split": args.split,
                    "seed": args.seed,
                    "n_queries": n,
                    "top_k": k,
                    "embedding_model": EMBED_MODEL,
                    "metrics": {
                        "dense_recall@1": {"hit": n_dense_r1, "total": n},
                        f"dense_recall@{k}": {"hit": n_dense_rk, "total": n},
                        "hybrid_recall@1": {"hit": n_hybrid_r1, "total": n},
                        f"hybrid_recall@{k}": {"hit": n_hybrid_rk, "total": n},
                    },
                    "per_query": per_query,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        print(f"\nSnapshot written to {args.out}")


if __name__ == "__main__":
    main()
