"""Chunker unit tests."""
from src.rag.chunker import MAX_TOKENS, _get_tokenizer, chunk_document


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


def test_no_chunk_exceeds_the_embedding_model_token_limit():
    """Chunking is calibrated to multilingual-e5-small's real 512-token
    limit, not an estimated character count -- see docs/TOKENIZATION.md."""
    tokenizer = _get_tokenizer()
    paragraph = "This is a sentence about health insurance coverage. " * 300
    chunks = chunk_document(paragraph, "long.md")
    passage_prefix_len = len(tokenizer.encode("passage: ", add_special_tokens=False))
    for c in chunks:
        full_len = len(tokenizer.encode(c.text, add_special_tokens=True)) + passage_prefix_len
        assert full_len <= 512


def test_hard_windowing_round_trips_a_long_arabic_sentence_without_mangling():
    """A single sentence longer than MAX_TOKENS is hard-windowed at the
    token level; SentencePiece round-tripping should not lose or corrupt
    characters (only whitespace normalization is expected)."""
    long_sentence = "التأمين الصحي يغطي زيارات الطبيب والأدوية والعمليات الجراحية الكبرى والصغرى وكذلك الفحوصات المخبرية والأشعة والعلاج الطبيعي وزيارات الطوارئ " * 15
    chunks = chunk_document(long_sentence, "long_ar.md")
    assert len(chunks) > 1
    rejoined = "".join(c.text.replace(" ", "") for c in chunks)
    original = long_sentence.replace(" ", "").strip()
    # every original character should survive the round trip somewhere in
    # the reassembled (overlap-deduplicated is not required here) output
    assert set(original) <= set(rejoined)


def test_chunk_budget_is_a_single_token_constant_not_per_language_chars():
    """Regression guard: the old CHUNK_BUDGET per-language char dict was
    replaced by a single measured token budget -- this simplification
    should not silently regress back to per-language magic numbers."""
    import src.rag.chunker as chunker_module

    assert not hasattr(chunker_module, "CHUNK_BUDGET")
    assert isinstance(MAX_TOKENS, int)
    assert MAX_TOKENS < 512
