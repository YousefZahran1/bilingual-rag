"""Chunker unit tests."""
from src.rag.chunker import chunk_document


def test_chunks_a_single_short_doc():
    text = "This is a short document. It has only a couple of sentences."
    chunks = chunk_document(text, "test.md")
    assert len(chunks) == 1
    assert chunks[0].language == "en"
    assert chunks[0].source == "test.md"


def test_chunks_arabic_doc():
    text = "هذه وثيقة قصيرة. تحتوي على جملتين فقط."
    chunks = chunk_document(text, "test_ar.md")
    assert len(chunks) >= 1
    assert chunks[0].language == "ar"


def test_chunks_long_doc_into_multiple_chunks():
    paragraph = "This is a sentence. " * 200  # ~4000 chars in English budget
    chunks = chunk_document(paragraph, "long.md")
    assert len(chunks) > 1
    # chunk_ids monotonically increase
    assert [c.chunk_id for c in chunks] == sorted(c.chunk_id for c in chunks)


def test_handles_empty_input():
    assert chunk_document("", "empty.md") == []
    assert chunk_document("   \n\n  ", "empty.md") == []
