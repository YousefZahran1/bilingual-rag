"""VectorStore.add() must embed passages with the e5 'passage: ' prefix
while keeping the stored/displayed text unprefixed. No live model/Chroma."""
from src.rag.chunker import Chunk
from src.rag.store import VectorStore


class FakeEmbedder:
    def __init__(self):
        self.calls = []

    def __call__(self, texts):
        self.calls.append(list(texts))
        return [[0.0, 0.0] for _ in texts]


class FakeCollection:
    def __init__(self):
        self.upsert_calls = []

    def upsert(self, ids, documents, metadatas, embeddings=None):
        self.upsert_calls.append(
            {
                "ids": ids,
                "documents": documents,
                "metadatas": metadatas,
                "embeddings": embeddings,
            }
        )


def _store_with_fakes():
    store = VectorStore()
    embedder = FakeEmbedder()
    collection = FakeCollection()
    store._embedder = embedder
    store._collection = collection
    store._get_collection = lambda: collection
    return store, embedder, collection


def test_add_embeds_passages_with_prefix():
    store, embedder, collection = _store_with_fakes()
    chunks = [
        Chunk(text="Outpatient cap is SAR 1,500/day.", source="a.md", chunk_id=0, language="en"),
        Chunk(text="سقف الغرفة اليومية 1500 ريال.", source="b.md", chunk_id=0, language="ar"),
    ]

    store.add(chunks)

    assert embedder.calls == [
        ["passage: Outpatient cap is SAR 1,500/day.", "passage: سقف الغرفة اليومية 1500 ريال."]
    ]


def test_add_stores_unprefixed_text():
    store, embedder, collection = _store_with_fakes()
    chunks = [Chunk(text="Outpatient cap is SAR 1,500/day.", source="a.md", chunk_id=0, language="en")]

    store.add(chunks)

    call = collection.upsert_calls[0]
    assert call["documents"] == ["Outpatient cap is SAR 1,500/day."]
    assert call["embeddings"] == [[0.0, 0.0]]


def test_add_noop_on_empty_chunks():
    store, embedder, collection = _store_with_fakes()

    store.add([])

    assert embedder.calls == []
    assert collection.upsert_calls == []
