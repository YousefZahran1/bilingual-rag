"""BM25Index build/search/save/load on a tiny synthetic corpus.

Pure Python statistics (rank_bm25), no neural model -- safe to run for real,
not stubbed.
"""
from src.rag.bm25_index import BM25Index
from src.rag.chunker import Chunk

CHUNKS = [
    Chunk(text="Outpatient cap is SAR 1,500 per day for shared rooms.", source="a.md", chunk_id=0, language="en"),
    Chunk(text="Maternity coverage includes prenatal visits and delivery.", source="b.md", chunk_id=0, language="en"),
    Chunk(text="Dental cleaning is covered twice per year under the rider.", source="c.md", chunk_id=0, language="en"),
]


def test_search_ranks_relevant_chunk_first():
    index = BM25Index.build(CHUNKS)
    results = index.search("outpatient room cap SAR", top_k=3)
    assert results[0].source == "a.md"


def test_search_respects_top_k():
    index = BM25Index.build(CHUNKS)
    results = index.search("coverage", top_k=1)
    assert len(results) == 1


def test_search_on_empty_index_returns_empty():
    index = BM25Index([])
    assert index.search("anything") == []


def test_save_and_load_roundtrip(tmp_path):
    index = BM25Index.build(CHUNKS)
    sidecar = tmp_path / "bm25_chunks.jsonl"
    index.save(str(sidecar))

    loaded = BM25Index.load(str(sidecar))
    results = loaded.search("dental cleaning rider", top_k=3)

    assert results[0].source == "c.md"


def test_load_missing_file_returns_empty_index(tmp_path):
    missing = tmp_path / "does_not_exist.jsonl"
    index = BM25Index.load(str(missing))
    assert index.search("anything") == []


def test_add_extends_and_rebuilds_index():
    index = BM25Index.build(CHUNKS[:2])
    index.add([CHUNKS[2]])
    results = index.search("dental cleaning rider", top_k=3)
    assert results[0].source == "c.md"
