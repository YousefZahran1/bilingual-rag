"""Language-aware chunker.

For Arabic, we keep chunks slightly smaller because tokens are denser.
For English, slightly larger. Splits on paragraph (`\n\n`), then sentence,
then a hard window if a sentence is too long.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Iterable

from .lang import detect_language

# rough character budgets (different by language because tokens-per-char differ)
CHUNK_BUDGET = {
    "ar": 700,
    "en": 1100,
    "mixed": 900,
}
OVERLAP = 120

# split pattern: keep punctuation; covers latin and arabic full-stops
SENTENCE_SPLIT = re.compile(r"(?<=[.!?؟।。])\s+|\n+")


@dataclass(frozen=True)
class Chunk:
    text: str
    source: str
    chunk_id: int
    language: str

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "source": self.source,
            "chunk_id": self.chunk_id,
            "language": self.language,
        }


def _windowed(text: str, budget: int, overlap: int) -> Iterable[str]:
    """Hard window for sentences that exceed the budget."""
    i = 0
    while i < len(text):
        yield text[i : i + budget]
        i += budget - overlap


def chunk_document(text: str, source: str) -> List[Chunk]:
    if not text or not text.strip():
        return []
    language = detect_language(text)
    budget = CHUNK_BUDGET[language]

    # paragraph-then-sentence assembly until we hit budget
    chunks: list[Chunk] = []
    cur: list[str] = []
    cur_len = 0
    chunk_id = 0
    paragraphs = re.split(r"\n\s*\n", text)
    for para in paragraphs:
        if not para.strip():
            continue
        sentences = SENTENCE_SPLIT.split(para.strip())
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            if len(sent) > budget:
                # flush current
                if cur:
                    joined = " ".join(cur).strip()
                    chunks.append(Chunk(joined, source, chunk_id, language))
                    chunk_id += 1
                    cur, cur_len = [], 0
                # window the long sentence
                for piece in _windowed(sent, budget, OVERLAP):
                    chunks.append(Chunk(piece, source, chunk_id, language))
                    chunk_id += 1
                continue

            if cur_len + len(sent) + 1 > budget:
                joined = " ".join(cur).strip()
                if joined:
                    chunks.append(Chunk(joined, source, chunk_id, language))
                    chunk_id += 1
                # carry overlap from the tail of the previous chunk
                tail = " ".join(cur)[-OVERLAP:] if cur else ""
                cur = [tail, sent] if tail else [sent]
                cur_len = sum(len(x) + 1 for x in cur)
            else:
                cur.append(sent)
                cur_len += len(sent) + 1
    if cur:
        joined = " ".join(cur).strip()
        if joined:
            chunks.append(Chunk(joined, source, chunk_id, language))
    return chunks
