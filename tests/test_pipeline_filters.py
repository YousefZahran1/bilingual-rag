"""Unit tests for src/rag/pipeline.py's metadata-filter helpers.

_build_where feeds Chroma's `where` clause (dense side); _match filters the
BM25/lexical side against the child-meta sidecar, since the lexical index
can't use Chroma's `where` natively.
"""
from src.rag.pipeline import _build_where, _match


def test_build_where_none_when_no_filters():
    assert _build_where(None) is None
    assert _build_where({}) is None


def test_build_where_single_key_is_eq_clause():
    assert _build_where({"doc_type": "formulary"}) == {"doc_type": {"$eq": "formulary"}}


def test_build_where_multiple_keys_wrapped_in_and():
    result = _build_where({"doc_type": "formulary", "language": "ar"})
    assert result == {
        "$and": [{"doc_type": {"$eq": "formulary"}}, {"language": {"$eq": "ar"}}]
    }


def test_match_no_filters_is_noop():
    assert _match({"doc_type": "contract"}, None) is True
    assert _match({"doc_type": "contract"}, {}) is True


def test_match_all_filter_keys_must_match():
    meta = {"doc_type": "formulary", "language": "ar"}
    assert _match(meta, {"doc_type": "formulary"}) is True
    assert _match(meta, {"doc_type": "formulary", "language": "ar"}) is True
    assert _match(meta, {"doc_type": "contract"}) is False
    assert _match(meta, {"doc_type": "formulary", "language": "en"}) is False


def test_match_compares_as_strings():
    # Chroma metadata can carry non-string values (e.g. int chunk_id); _match
    # is also used for keys like that, so it must not require exact type match.
    assert _match({"chunk_id": 3}, {"chunk_id": "3"}) is True


def test_match_missing_key_fails():
    assert _match({"doc_type": "contract"}, {"language": "ar"}) is False
