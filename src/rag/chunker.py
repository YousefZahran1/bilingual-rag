"""Token-aware chunker.

Chunk size is measured with the same tokenizer used to embed documents
(`intfloat/multilingual-e5-small`, 512-token max sequence length), not an
estimated character count. See docs/TOKENIZATION.md for the measured
Arabic-vs-English token density this is calibrated against. Splits on
paragraph (`\n\n`), then sentence, then a hard token window if a single
sentence alone exceeds the budget.
"""
from __future__ import annotations

import os
import re
from collections.abc import Iterable
from dataclasses import dataclass

from .lang import detect_language

# Target tokens per chunk. The ceiling is the embedding model's real 512-token
# limit minus headroom for the "passage: " prefix (store.py) and special
# tokens. Smaller chunks isolate individual clauses/facts (better rank-1
# precision on specific numeric/definition questions) at the cost of more
# chunks; larger chunks give more context per passage. Tunable via env so the
# size can be swept against the eval harness without code edits.
MAX_TOKENS = int(os.environ.get("CHUNK_MAX_TOKENS", "200"))
OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "30"))

# Chunking strategy: "token" (fixed-size, sentence-packed) or "structure"
# (split on clause/section markers, token-pack oversized clauses). Structure
# fits already-numbered regulatory text (the CCHI corpus); token is the safe
# general default.
CHUNK_STRATEGY = os.environ.get("CHUNK_STRATEGY", "token")
# Segments shorter than this (in tokens) are merged into the previous chunk so
# structure splitting doesn't emit lone headers / one-line fragments.
MIN_STRUCT_TOKENS = int(os.environ.get("CHUNK_MIN_STRUCT_TOKENS", "24"))

_TOKENIZER_NAME = "intfloat/multilingual-e5-small"
_tokenizer = None


def _get_tokenizer():
    global _tokenizer
    if _tokenizer is None:
        from transformers import AutoTokenizer  # noqa: WPS433

        _tokenizer = AutoTokenizer.from_pretrained(_TOKENIZER_NAME)
    return _tokenizer


def _token_len(text: str) -> int:
    return len(_get_tokenizer().encode(text, add_special_tokens=False))


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
    """Hard token window for a single sentence that exceeds the budget."""
    tokenizer = _get_tokenizer()
    ids = tokenizer.encode(text, add_special_tokens=False)
    i = 0
    while i < len(ids):
        yield tokenizer.decode(ids[i : i + budget]).strip()
        i += budget - overlap


def _tail_tokens(text: str, overlap: int) -> str:
    """Last `overlap` tokens of `text`, decoded back to a string."""
    if not text:
        return ""
    ids = _get_tokenizer().encode(text, add_special_tokens=False)
    if not ids:
        return ""
    return _get_tokenizer().decode(ids[-overlap:]).strip()


def chunk_document(text: str, source: str) -> list[Chunk]:
    """Chunk a document using the configured strategy (CHUNK_STRATEGY)."""
    if CHUNK_STRATEGY == "structure":
        return _chunk_structured(text, source)
    return _chunk_token(text, source)


# --- structure-aware strategy -------------------------------------------------

# A line that begins a new logical unit in the CCHI regulatory documents:
#   markdown headings ("## Page 7"), numbered clauses ("1.21 ...", "3.4 ...",
#   "20. ..."), or lettered sub-points ("A. ...", "f) ...").
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S")
_CLAUSE_RE = re.compile(r"^\s{0,3}\d{1,3}(?:\.\d{1,3}){0,3}[.)؛:]?\s+\S")
_LETTER_RE = re.compile(r"^\s{0,3}[A-Za-z][.)]\s+\S")


def _is_boundary(line: str) -> bool:
    return bool(
        _HEADING_RE.match(line) or _CLAUSE_RE.match(line) or _LETTER_RE.match(line)
    )


def _split_oversized(text: str) -> list[str]:
    """A single clause longer than the budget is token-windowed; otherwise
    returned as-is."""
    return [text] if _token_len(text) <= MAX_TOKENS else list(
        _windowed(text, MAX_TOKENS, OVERLAP)
    )


def _segments(text: str) -> list[str]:
    """Group lines into structural segments — each starts at a boundary line
    (heading / numbered clause / lettered sub-point)."""
    segs: list[str] = []
    cur: list[str] = []
    for line in text.splitlines():
        if _is_boundary(line) and cur:
            segs.append("\n".join(cur).strip())
            cur = [line]
        else:
            cur.append(line)
    if cur:
        segs.append("\n".join(cur).strip())
    return [s for s in segs if s.strip()]


def _chunk_structured(text: str, source: str) -> list[Chunk]:
    """Split on clause/section markers, then pack consecutive clauses up to the
    token budget (never splitting a clause across chunks unless the clause alone
    exceeds the budget). Chunks stay aligned to real clause boundaries, so a
    citation lands on a coherent section instead of an arbitrary token window,
    while packing keeps chunk count and size sensible."""
    if not text or not text.strip():
        return []

    chunks: list[Chunk] = []
    buf: list[str] = []
    buf_tok = 0
    cid = 0

    def flush() -> None:
        nonlocal buf, buf_tok, cid
        if not buf:
            return
        joined = "\n".join(buf).strip()
        for piece in _split_oversized(joined):
            chunks.append(Chunk(piece, source, cid, detect_language(piece)))
            cid += 1
        buf, buf_tok = [], 0

    for seg in _segments(text):
        seg_tok = _token_len(seg)
        if seg_tok > MAX_TOKENS:
            flush()  # oversized clause stands alone, then gets windowed
            for piece in _split_oversized(seg):
                chunks.append(Chunk(piece, source, cid, detect_language(piece)))
                cid += 1
            continue
        if buf_tok + seg_tok > MAX_TOKENS:
            flush()
        buf.append(seg)
        buf_tok += seg_tok
    flush()
    return chunks


def _chunk_token(text: str, source: str) -> list[Chunk]:
    if not text or not text.strip():
        return []
    language = detect_language(text)

    # paragraph-then-sentence assembly until we hit the token budget
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
            sent_len = _token_len(sent)
            if sent_len > MAX_TOKENS:
                # flush current
                if cur:
                    joined = " ".join(cur).strip()
                    chunks.append(Chunk(joined, source, chunk_id, language))
                    chunk_id += 1
                    cur, cur_len = [], 0
                # window the long sentence
                for piece in _windowed(sent, MAX_TOKENS, OVERLAP):
                    chunks.append(Chunk(piece, source, chunk_id, language))
                    chunk_id += 1
                continue

            if cur_len + sent_len > MAX_TOKENS:
                joined = " ".join(cur).strip()
                if joined:
                    chunks.append(Chunk(joined, source, chunk_id, language))
                    chunk_id += 1
                # carry overlap from the tail of the previous chunk
                tail = _tail_tokens(" ".join(cur), OVERLAP) if cur else ""
                cur = [tail, sent] if tail else [sent]
                cur_len = sum(_token_len(x) for x in cur)
            else:
                cur.append(sent)
                cur_len += sent_len
    if cur:
        joined = " ".join(cur).strip()
        if joined:
            chunks.append(Chunk(joined, source, chunk_id, language))
    return chunks
