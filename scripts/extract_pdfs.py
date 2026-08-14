"""Extract the real CCHI source PDFs into clean bilingual markdown.

These are public Council of Health Insurance (CCHI, Saudi Arabia) regulatory
documents -- see data/real/SOURCES.md for provenance. This script is the
reproducible bridge from the shipped PDFs (data/real/pdfs/*.pdf) to the
markdown corpus the RAG pipeline ingests (data/real/*.md).

It is deliberately conservative: it extracts the embedded text layer (no OCR,
none of these PDFs need it), strips repeated page furniture (page numbers,
the "public" watermark, the CCHI form-code running footer) and collapses
whitespace, but never rewrites or paraphrases the regulatory text.

Usage:
    python scripts/extract_pdfs.py            # extract all
    python scripts/extract_pdfs.py --check    # report char counts only
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

REAL_DIR = Path(__file__).resolve().parent.parent / "data" / "real"
PDF_DIR = REAL_DIR / "pdfs"

# Layout-aware extraction. PyMuPDF preserves reading order (and RTL Arabic)
# better than pypdf and also handles born-digital tables more cleanly; pypdf is
# kept as a dependency-light fallback. DOCX is handled via python-docx. Engine
# is selectable with EXTRACT_ENGINE=pymupdf|pypdf (default pymupdf if installed).
ENGINE = os.environ.get("EXTRACT_ENGINE", "pymupdf")


def _pdf_pages_pymupdf(path: Path):
    import pymupdf  # PyMuPDF

    with pymupdf.open(path) as doc:
        # "text" mode returns natural reading order; RTL runs come back logical.
        return [page.get_text("text") for page in doc]


def _pdf_pages_pypdf(path: Path):
    from pypdf import PdfReader

    return [(p.extract_text() or "") for p in PdfReader(str(path)).pages]


def _docx_pages(path: Path):
    import docx  # python-docx

    d = docx.Document(str(path))
    # Treat the whole document as one "page"; headings/paragraphs keep their
    # order and the structure-aware chunker re-discovers sections downstream.
    lines = [p.text for p in d.paragraphs]
    return ["\n".join(lines)]


def extract_pages(path: Path):
    """Return a list of page texts for a .pdf or .docx source."""
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return _docx_pages(path)
    if suffix == ".pdf":
        if ENGINE == "pymupdf":
            try:
                return _pdf_pages_pymupdf(path)
            except Exception:
                return _pdf_pages_pypdf(path)
        return _pdf_pages_pypdf(path)
    raise ValueError(f"Unsupported source type: {path.suffix}")


def _find_source(stem: str) -> Path:
    for ext in (".pdf", ".docx"):
        cand = PDF_DIR / f"{stem}{ext}"
        if cand.exists():
            return cand
    return PDF_DIR / f"{stem}.pdf"

# stem -> (human title, one-line description used as the markdown H1 / lead)
DOCS = {
    "unified_contract": (
        "The Unified Contract between Insurance Company and Health Service Provider",
        "Bilingual (Arabic/English) standard contract governing the relationship "
        "between insurers and private-sector health service providers in Saudi Arabia.",
    ),
    "ebp_5_tiers": (
        "Tiers Benefit Package for Private Health Insurance Beneficiaries",
        "Five-tier benefit package summary for private health insurance beneficiaries.",
    ),
    "drug_formulary": (
        "Insurance Drug Formulary (IDF)",
        "Overview of the CCHI evidence-based insurance drug formulary, co-payment "
        "rules, and the prescription filling process.",
    ),
    "essential_benefit_package": (
        "Updated Essential Benefit Package (effective 1 October 2022)",
        "The Basic Health Insurance Policy and Essential Benefit Package that "
        "defines minimum required coverage.",
    ),
}

# Lines that are pure page furniture and carry no regulatory content.
_DROP_PATTERNS = [
    re.compile(r"^\s*public\s*$", re.IGNORECASE),
    re.compile(r"^\s*Council of Health Insurance\s*-\s*Public\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d{1,4}\s*$"),                       # bare page numbers
    re.compile(r"^\s*CCHI-\S+\s*$", re.IGNORECASE),        # form-code footer (LTR part)
    re.compile(r"^\s*Page\s+\d+\s+of\s+\d+\s*$", re.IGNORECASE),
]
# The running footer on the contract mixes a form code with Arabic; drop the
# whole line if it contains the form code anywhere.
_FORMCODE = re.compile(r"CCHI-\d", re.IGNORECASE)

# Latin typographic ligatures the CCHI PDFs embed (e.g. "beneﬁts"). Normalizing
# them to ASCII makes both keyword search and dense retrieval see real words.
_LIGATURES = {
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi",
    "ﬄ": "ffl", "ﬅ": "ft", "ﬆ": "st",
}


def _normalize(line: str) -> str:
    for lig, repl in _LIGATURES.items():
        line = line.replace(lig, repl)
    # PDF layout sometimes injects a space before a hyphen ("twenty -five")
    line = re.sub(r"\s+-\s*(?=[A-Za-z])", "-", line)
    return line


def _clean(text: str) -> str:
    out = []
    for raw in text.splitlines():
        line = _normalize(raw.rstrip())
        if not line.strip():
            out.append("")
            continue
        if _FORMCODE.search(line):
            continue
        if any(p.match(line) for p in _DROP_PATTERNS):
            continue
        # collapse runs of >1 internal space (PDF layout artifacts)
        line = re.sub(r"[ \t]{2,}", " ", line).strip()
        out.append(line)
    # collapse 3+ blank lines down to a single blank line
    joined = "\n".join(out)
    joined = re.sub(r"\n{3,}", "\n\n", joined)
    return joined.strip() + "\n"


def extract_one(stem: str, title: str, desc: str) -> tuple[int, int]:
    src = _find_source(stem)
    pages = extract_pages(src)
    parts = [f"# {title}\n", f"> {desc}\n",
             f"> Source: data/real/pdfs/{src.name} (public CCHI document).\n"]
    for i, page in enumerate(pages, start=1):
        body = _clean(page or "")
        if body.strip():
            parts.append(f"\n## Page {i}\n\n{body}")
    md = "\n".join(parts).strip() + "\n"
    out_path = REAL_DIR / f"{stem}.md"
    out_path.write_text(md, encoding="utf-8")
    return len(pages), len(md)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report only, do not write")
    args = ap.parse_args()
    print(f"engine: {ENGINE}")
    for stem, (title, desc) in DOCS.items():
        src = _find_source(stem)
        if not src.exists():
            print(f"  ! missing {src}")
            continue
        if args.check:
            print(f"  {stem}: {len(extract_pages(src))} pages ({src.suffix})")
            continue
        pages, chars = extract_one(stem, title, desc)
        print(f"  + {stem}.md  <- {pages} pages, {chars:,} chars")


if __name__ == "__main__":
    main()
