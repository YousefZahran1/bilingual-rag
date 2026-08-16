"""Ragas faithfulness/relevancy/context metrics over this project's own
eval harness artifacts.

Every other eval in this repo (eval/run_eval.py, scripts/bench_pipeline.py,
scripts/bench_miracl.py) is free to run: mock provider, no API key, no
judge LLM. This script is the one exception, by necessity -- faithfulness
and answer_relevancy only mean something against a REAL generated answer,
and Ragas needs a real LLM to judge it. It is NOT run in CI and has no
mock-provider fallback that would produce a meaningful number (a mock
answer is literally an excerpt of its own context, so "faithfulness"
against a mock answer is close to tautological).

Requires OPENROUTER_API_KEY (or set RAGAS_JUDGE_* env vars to point at a
different OpenAI-compatible endpoint/model).

Two-phase design, both resumable:

  Phase 1 (build): retrieve + generate a REAL answer for each eval
  question, once. Checkpointed per-question to --out (JSONL) so an
  interrupted run (OpenRouter free-tier daily cap, same failure mode
  documented in docs/EVAL.md's real-LLM section) resumes with --resume
  instead of re-spending quota on already-completed questions. Ground
  truth: this project's eval sets have expected_keywords, not full
  reference answers, so a "reference" field is SYNTHESIZED from them (a
  flat sentence listing the expected keywords) -- documented here and in
  the output JSON as synthesized, not human-authored, so nobody mistakes
  it for real ground truth later.

  Phase 2 (judge): run ragas.evaluate() against the frozen Phase-1 dataset
  --runs times (default 3) -- LLM judges are noisy; a single run is not a
  number. Judge calls are disk-cached (ragas.cache.DiskCacheBackend,
  --cache-dir) keyed on (prompt, run_index) -- same run_index re-run is
  free (a crashed run resumes into the cache), but the --runs independent
  passes are NOT collapsed into one cached answer, or "3 runs" would
  measure nothing. Report mean +/- stdev per metric across runs.

Usage:
    export OPENROUTER_API_KEY=...
    python -m eval.run_ragas build --corpus real --out eval/results/ragas_real_dataset.jsonl
    python -m eval.run_ragas build --corpus sample --sample 30 --seed 42 --out eval/results/ragas_sample_dataset.jsonl --resume
    python -m eval.run_ragas judge --dataset eval/results/ragas_real_dataset.jsonl --runs 3 --out eval/results/ragas_real.json
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Eval questions include Arabic text; Windows consoles default to a cp1252
# codepage that can't encode it, crashing print() partway through a run
# (lost progress on whatever wasn't flushed to --out yet). Force UTF-8
# stdout instead of relying on the terminal's codepage.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.rag.bm25_index import BM25Index
from src.rag.fusion import retrieve_pipeline
from src.rag.generator import generate
from src.rag.reranker import CrossEncoderReranker
from src.rag.store import VectorStore

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _synthesize_reference(item: dict) -> str:
    """Not a real reference answer -- this project's eval sets record
    expected_keywords, not authored ground-truth answers. A flat sentence
    listing them is enough for Ragas's context_recall (which checks whether
    the retrieved context could support these facts), but it is NOT a
    substitute for a human-written reference and is labeled as synthesized
    in every output row so it's never mistaken for one."""
    kws = item.get("expected_keywords", [])
    if not kws:
        return ""
    return "The answer should include: " + ", ".join(kws) + "."


def _build_dataset(args: argparse.Namespace) -> None:
    data_dir = DATA_ROOT / args.corpus
    eval_path = data_dir / "eval_questions.jsonl"
    items = [it for it in _load_jsonl(eval_path) if it.get("is_answerable", True)]

    if args.sample and args.sample < len(items):
        rng = random.Random(args.seed)
        idx = list(range(len(items)))
        rng.shuffle(idx)
        items = [items[i] for i in sorted(idx[: args.sample])]

    out_path = args.out
    done_questions: set[str] = set()
    if args.resume:
        done_questions = {row["question"] for row in _load_jsonl(out_path)}
        print(f"Resuming: {len(done_questions)} questions already in {out_path}.")

    store = VectorStore()
    bm25_index = BM25Index.load()
    reranker = CrossEncoderReranker()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if args.resume and out_path.exists() else "w"
    with out_path.open(mode, encoding="utf-8") as f:
        for i, item in enumerate(items, start=1):
            q = item["question"]
            if q in done_questions:
                continue
            passages = retrieve_pipeline(q, store, bm25_index, reranker, top_k=args.top_k)
            try:
                result = generate(q, passages)
            except Exception as exc:  # noqa: BLE001 -- one failure (rate limit, etc.) must not kill the build
                print(f"  [{i}/{len(items)}] generation error, skipping: {exc}")
                continue
            row = {
                "question": q,
                "answer": result.answer,
                "contexts": [p.text for p in passages],
                "reference": _synthesize_reference(item),
                "reference_synthesized": True,
                "tags": item.get("tags", []),
                "split": item.get("split"),
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            print(f"  [{i}/{len(items)}] {q[:60]!r}")

    print(f"\nDataset written to {out_path}.")


def _judge(args: argparse.Namespace) -> None:
    if "OPENROUTER_API_KEY" not in os.environ:
        raise SystemExit(
            "OPENROUTER_API_KEY not set. This script makes real judge LLM calls -- "
            "see the module docstring for why there's no mock fallback."
        )

    from datasets import Dataset
    from langchain_openai import ChatOpenAI
    from ragas import evaluate
    from ragas.cache import DiskCacheBackend
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import (
        AnswerRelevancy,
        ContextPrecision,
        ContextRecall,
        Faithfulness,
    )

    from ._e5_embeddings import E5Embeddings  # local, no new heavy dependency

    rows = _load_jsonl(args.dataset)
    if not rows:
        raise SystemExit(f"No rows in {args.dataset} -- run `build` first.")

    dataset = Dataset.from_list(
        [
            {
                "user_input": r["question"],
                "response": r["answer"],
                "retrieved_contexts": r["contexts"],
                "reference": r["reference"],
            }
            for r in rows
        ]
    )

    judge_model = os.environ.get("RAGAS_JUDGE_MODEL", os.environ.get("OPENROUTER_MODEL", "openai/gpt-oss-20b:free"))
    metrics = [Faithfulness(), AnswerRelevancy(), ContextPrecision(), ContextRecall()]

    per_run_scores: dict[str, list[float]] = {m.name: [] for m in metrics}
    per_run_results = []

    for run_idx in range(args.runs):
        print(f"\n=== Judge run {run_idx + 1}/{args.runs} ===")
        cache = DiskCacheBackend(cache_dir=str(args.cache_dir))
        chat = ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
            model=judge_model,
            # run_idx folded into every prompt via a cache-only marker so
            # each of the --runs passes gets independent judge samples
            # instead of all collapsing onto run 0's cached answer -- see
            # module docstring. Doesn't affect what the judge actually
            # sees; only affects the cache key ragas hashes on.
            model_kwargs={"extra_headers": {"X-Ragas-Run-Index": str(run_idx)}},
        )
        llm = LangchainLLMWrapper(chat, cache=cache)
        embeddings = LangchainEmbeddingsWrapper(E5Embeddings(), cache=cache)

        result = evaluate(dataset=dataset, metrics=metrics, llm=llm, embeddings=embeddings)
        df = result.to_pandas()
        run_means = {m.name: float(df[m.name].mean()) for m in metrics}
        for name, val in run_means.items():
            per_run_scores[name].append(val)
        per_run_results.append(run_means)
        print({k: round(v, 3) for k, v in run_means.items()})

    import statistics

    summary = {}
    for name, scores in per_run_scores.items():
        summary[name] = {
            "mean": round(statistics.mean(scores), 4),
            "stdev": round(statistics.stdev(scores), 4) if len(scores) > 1 else 0.0,
            "runs": [round(s, 4) for s in scores],
        }

    print("\n=== Summary (mean +/- stdev across runs) ===")
    for name, s in summary.items():
        print(f"  {name}: {s['mean']:.3f} +/- {s['stdev']:.3f}  (runs: {s['runs']})")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "dataset": str(args.dataset),
                    "n_questions": len(rows),
                    "judge_model": judge_model,
                    "runs": args.runs,
                    "reference_note": "reference field is synthesized from expected_keywords, "
                    "not a human-authored ground truth -- see _synthesize_reference() docstring",
                    "summary": summary,
                    "per_run": per_run_results,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        print(f"\nResults written to {args.out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    build_p = sub.add_parser("build", help="Retrieve + generate real answers, checkpointed.")
    build_p.add_argument("--corpus", default="real", choices=["real", "real2", "sample"])
    build_p.add_argument("--sample", type=int, default=None, help="Stratified-by-index subsample size")
    build_p.add_argument("--seed", type=int, default=42)
    build_p.add_argument("--top-k", type=int, default=4)
    build_p.add_argument("--out", type=Path, required=True)
    build_p.add_argument("--resume", action="store_true")

    judge_p = sub.add_parser("judge", help="Run Ragas metrics against a built dataset, N times.")
    judge_p.add_argument("--dataset", type=Path, required=True)
    judge_p.add_argument("--runs", type=int, default=3)
    judge_p.add_argument("--cache-dir", type=Path, default=Path(".ragas_cache"))
    judge_p.add_argument("--out", type=Path, default=None)

    args = ap.parse_args()
    if args.cmd == "build":
        _build_dataset(args)
    else:
        _judge(args)


if __name__ == "__main__":
    main()
