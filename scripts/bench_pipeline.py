"""Build + regression-benchmark the unified pipeline (scaling plan step 5).

Ingests a corpus through the unified pipeline (structure/token routing +
parent-child + rich metadata) and scores retrieval on that corpus's
eval_questions.jsonl using the production retrieval path (hybrid dense+BM25+RRF
over children, expanded to parents). Prints two regression metrics and exits
non-zero if either falls below a threshold — so a CI job can gate new ingests.

Usage:
    python scripts/bench_pipeline.py --data data/real            # build + bench
    python scripts/bench_pipeline.py --data data/real --no-build # bench existing
    python scripts/bench_pipeline.py --data data/real --min-recall 0.9 --min-keyword 0.8
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.rag.pipeline import UnifiedIndex  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/real", help="corpus dir (with eval_questions.jsonl)")
    ap.add_argument("--persist", default="", help="index dir (default: /tmp/unified_<corpus>)")
    ap.add_argument("--no-build", action="store_true", help="use an existing index")
    ap.add_argument("--parent-k", type=int, default=4)
    ap.add_argument("--min-recall", type=float, default=0.9)
    ap.add_argument("--min-keyword", type=float, default=0.6)
    args = ap.parse_args()

    data = Path(args.data)
    persist = args.persist or f"/tmp/unified_{data.name}"
    idx = UnifiedIndex(persist)
    if not args.no_build:
        info = idx.build(str(data))
        print(f"built: {info['parents']} parents / {info['children']} children")
        for name, route in info["routing"].items():
            print(f"  {name:34} -> {route}")

    questions = [
        json.loads(line)
        for line in (data / "eval_questions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rec = kh = kt = 0
    for q in questions:
        passages = idx.retrieve(q["question"], parent_k=args.parent_k)
        sources = {p.source.split("/")[-1] for p in passages}
        rec += q.get("expected_source", "") in sources
        ctx = " ".join(p.text for p in passages).lower()
        for kw in q.get("expected_keywords", []):
            kt += 1
            kh += kw.lower() in ctx

    n = len(questions)
    recall = rec / n if n else 0.0
    keyword = kh / kt if kt else 0.0
    print(f"\nunified pipeline — {n} questions")
    print(f"  parent recall (expected_source in top-{args.parent_k}): {rec}/{n} ({recall:.0%})")
    print(f"  context keyword coverage:                    {kh}/{kt} ({keyword:.0%})")

    failed = recall < args.min_recall or keyword < args.min_keyword
    if failed:
        print(
            f"\nREGRESSION: recall {recall:.0%} (min {args.min_recall:.0%}) / "
            f"keyword {keyword:.0%} (min {args.min_keyword:.0%})"
        )
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
