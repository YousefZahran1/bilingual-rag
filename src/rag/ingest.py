"""Ingest a directory of .md / .txt files into the vector store.

Usage:
    python -m src.rag.ingest data/sample
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .chunker import chunk_document
from .store import VectorStore


SUPPORTED_SUFFIXES = {".md", ".txt"}


def ingest_path(path: Path, store: VectorStore) -> int:
    total = 0
    if path.is_file():
        files = [path]
    else:
        files = [
            p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
        ]
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        chunks = chunk_document(text, source=str(f.relative_to(path.parent)))
        store.add(chunks)
        total += len(chunks)
        print(f"  + {f.name}: {len(chunks)} chunks")
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest documents into the bilingual RAG store.")
    ap.add_argument("path", type=Path, help="Directory or single file to ingest")
    ap.add_argument("--reset", action="store_true", help="Drop the collection first")
    args = ap.parse_args()

    store = VectorStore()
    if args.reset:
        col = store._get_collection()  # noqa: SLF001
        col.delete(where={})
        print("Collection reset.")
    n = ingest_path(args.path, store)
    print(f"Done. Indexed {n} chunks.")


if __name__ == "__main__":
    main()
