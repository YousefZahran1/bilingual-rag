"""Runs eval/validate_eval_set.py's checks against the real committed corpus
and eval file. Pure string ops, no model -- cheap enough to run in CI as a
permanent regression guard against eval ground-truth drift (a doc edited
without updating the questions that cite it, a typo'd keyword, etc.).

This proves internal consistency (claimed keywords are actually present),
not that the questions are hard or realistic -- that still needs a human
spot-check, per docs/EVAL.md.
"""
from eval.validate_eval_set import validate


def test_eval_set_has_no_grounding_errors():
    errors, _warnings = validate()
    assert errors == [], "\n".join(errors)
