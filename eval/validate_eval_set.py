"""Validates data/sample/eval_questions.jsonl against data/sample/*.md.

Pure string matching -- no models, no retrieval. This exists because the
same person (an LLM, authoring both the documents and the questions in one
pass) is "grading its own exam": it catches expected_keywords that were true
in the author's head but never actually written into the document, and flags
keyword sets that are ambiguous (they also match a document not listed in
expected_source(s)). It proves internal consistency, not that the questions
are hard or realistic -- see docs/EVAL.md for the manual spot-check caveat.

Usage:
    python -m eval.validate_eval_set
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"
EVAL_PATH = DATA_DIR / "eval_questions.jsonl"


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


def validate(eval_path: Path = EVAL_PATH, data_dir: Path = DATA_DIR) -> Tuple[List[str], List[str]]:
    """Returns (errors, warnings). Errors mean the eval set is factually
    wrong (a keyword that isn't in the document, a source that doesn't
    exist). Warnings mean the ground truth is ambiguous, not necessarily
    wrong."""
    errors: List[str] = []
    warnings: List[str] = []
    all_docs: Dict[str, str] = {p.name: p.read_text(encoding="utf-8") for p in data_dir.glob("*.md")}

    for i, item in enumerate(_load_jsonl(eval_path), start=1):
        question = item.get("question", "<missing question>")
        label = f"[{i}] '{question[:60]}'"
        is_answerable = item.get("is_answerable", True)
        expected = _expected_sources(item)
        keywords = item.get("expected_keywords", [])

        if not is_answerable:
            if expected or keywords:
                warnings.append(f"{label}: is_answerable=false but has expected_source(s)/keywords set")
            continue

        if not expected:
            continue

        for source in expected:
            if source not in all_docs:
                errors.append(f"{label}: expected_source '{source}' does not exist in {data_dir}")

        combined_text = " ".join(all_docs.get(s, "") for s in expected).lower()
        for kw in keywords:
            if kw.lower() not in combined_text:
                errors.append(f"{label}: keyword '{kw}' not found in {expected}")

        if len(expected) == 1 and keywords:
            for name, text in all_docs.items():
                if name in expected:
                    continue
                text_lower = text.lower()
                if all(kw.lower() in text_lower for kw in keywords):
                    warnings.append(
                        f"{label}: keyword set also fully matches '{name}' -- consider expected_sources"
                    )

    return errors, warnings


def main() -> None:
    errors, warnings = validate()
    for w in warnings:
        print(f"WARNING: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    print(f"\n{len(errors)} errors, {len(warnings)} warnings.")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
