"""Numeric-intent query classification, used to route around the reranker.

docs/EVAL.md found that the cross-encoder reranker specifically hurts
numeric-answer questions (BM25 alone has the best measured recall@4 on
them) while helping everything else a lot. `is_numeric_query()` is the
routing signal `fusion.py:smart_retrieve()` uses to send numeric queries to
BM25 alone and everything else through the full hybrid+rerank pipeline.

The heuristic was tuned empirically against the real 89-question eval set
(data/sample/eval_questions.jsonl's manually-assigned "numeric" tag), not
guessed: precision 0.85, recall 0.92 (see tests/test_query_router.py's
data-driven regression test, which re-measures this against the committed
eval file so drift is caught). Two tiers:

1. Phrase patterns -- most numeric-tagged questions ask a quantity
   question without the number appearing in the question text itself
   (e.g. "How many dental cleanings are covered per year?").
2. A digit-followed-by-unit fallback for questions where the number IS in
   the query text (e.g. "beyond 6 sessions", "within 50 km", "100%").
   Scoping to digit+unit rather than a bare digit anywhere matters: a
   genuinely naive bare-digit check would also flag questions where a
   number merely *appears* without being asked about, e.g. source
   filenames or, notably, the prompt-injection question that contains
   "100%" as injected instruction text rather than a real numeric ask --
   that one specific question IS still a false positive here (it
   legitimately contains a digit+percent), and is counted in the measured
   precision above rather than hidden; the scoping mainly narrows the far
   larger set of bare-digit false positives a fully naive check would add
   (source references, IDs, etc.), it does not eliminate every edge case.
"""
from __future__ import annotations

import re

_EN_PHRASE_PATTERN = re.compile(
    r"how many|how much|how long|how soon|how often"
    r"|\b(?:maximum|max|cap|limit|penalty|rate|percentage|copay|co-pay|premium|allowance)\b"
    r"|grace period|waiting period|window|per year|per day|deadline|completed by",
    re.IGNORECASE,
)

_AR_PHRASE_PATTERN = re.compile(
    r"كم\b|ما هو الحد الأقصى|ما هي المدة|ما هو بدل|ما هي فترة"
    r"|خلال كم|مدة|فترة|بدل|الحد الأقصى"
)

_DIGIT_UNIT_PATTERN = re.compile(
    # No trailing \b: it fails right after "%" specifically, since "%" and
    # a following space/punctuation are both non-word characters, so no
    # word/non-word boundary exists there for \b to match -- silently
    # broke percentage detection entirely until caught by a direct test.
    r"\d+\s*(?:%|km|day(?:s)?|session(?:s)?|hour(?:s)?|year(?:s)?|month(?:s)?|sar|riyal)"
    r"|\b(?:day(?:s)?|session(?:s)?|hour(?:s)?|year(?:s)?|month(?:s)?)\s*\d+",
    re.IGNORECASE,
)


def is_numeric_query(query: str) -> bool:
    """True if the query is likely asking for a numeric answer (a count,
    cap, percentage, duration, etc.) -- the case where BM25 alone
    out-performs the full hybrid+rerank pipeline. Not a classifier, a
    calibrated heuristic; see the module docstring for its measured
    precision/recall."""
    if _EN_PHRASE_PATTERN.search(query):
        return True
    if _AR_PHRASE_PATTERN.search(query):
        return True
    if _DIGIT_UNIT_PATTERN.search(query):
        return True
    return False
