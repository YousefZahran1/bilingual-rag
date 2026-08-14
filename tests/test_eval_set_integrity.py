"""Runs eval/validate_eval_set.py's checks against every committed corpus and
its eval file. Pure string ops, no model -- cheap enough to run in CI as a
permanent regression guard against eval ground-truth drift (a doc edited
without updating the questions that cite it, a typo'd keyword, etc.).

This proves internal consistency (claimed keywords are actually present),
not that the questions are hard or realistic -- that still needs a human
spot-check, per docs/EVAL.md.
"""
from pathlib import Path

import pytest

from eval.validate_eval_set import DATA_ROOT, validate

CORPORA = ["sample", "real2"]


@pytest.mark.parametrize("corpus", CORPORA)
def test_eval_set_has_no_grounding_errors(corpus):
    data_dir = DATA_ROOT / corpus
    eval_path = data_dir / "eval_questions.jsonl"
    errors, _warnings = validate(eval_path, data_dir)
    assert errors == [], "\n".join(errors)


def test_corpora_list_is_complete():
    # Regression guard: every data/<corpus>/eval_questions.jsonl on disk must
    # be covered by CORPORA above, or it silently stops being CI-validated.
    on_disk = {
        p.parent.name for p in DATA_ROOT.glob("*/eval_questions.jsonl")
    }
    # data/real predates this parametrized test and isn't validated the same
    # way yet (no *.md content check wired here) -- tracked separately, not
    # a silent gap.
    assert on_disk - {"real"} == set(CORPORA), (
        f"data/*/eval_questions.jsonl on disk ({sorted(on_disk)}) doesn't "
        f"match CORPORA ({sorted(CORPORA)}) -- add the missing corpus above."
    )


def test_real2_pdfs_have_provenance():
    sources = Path(DATA_ROOT / "real2" / "SOURCES.md")
    assert sources.exists(), "data/real2/SOURCES.md is required for any committed PDF"
