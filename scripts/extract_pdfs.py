"""Extract real regulatory source PDFs into clean bilingual markdown.

The reproducible bridge from shipped PDFs (data/<corpus>/pdfs/*.pdf) to the
markdown corpus the RAG pipeline ingests (data/<corpus>/*.md). Supports two
corpora, selected with --corpus:
  - "real" (default): Council of Health Insurance (CCHI, Saudi Arabia)
    regulatory documents -- see data/real/SOURCES.md.
  - "real2": Zakat, Tax and Customs Authority (ZATCA, Saudi Arabia) VAT
    guidelines, a second, unrelated regulatory domain -- see
    data/real2/SOURCES.md. Added to test that the pipeline generalizes
    beyond the healthcare-insurance domain it was originally tuned on.

It is deliberately conservative: it extracts the embedded text layer (no OCR,
none of these PDFs need it), strips repeated page furniture (bare page
numbers, corpus-specific running footers/watermarks) and collapses
whitespace, but never rewrites or paraphrases the regulatory text.

Usage:
    python scripts/extract_pdfs.py                       # extract data/real
    python scripts/extract_pdfs.py --corpus real2         # extract data/real2
    python scripts/extract_pdfs.py --corpus real2 --check # report char counts only
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"

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
            except Exception:  # noqa: BLE001 -- any PyMuPDF failure falls back to pypdf
                return _pdf_pages_pypdf(path)
        return _pdf_pages_pypdf(path)
    raise ValueError(f"Unsupported source type: {path.suffix}")


def _find_source(pdf_dir: Path, stem: str) -> Path:
    for ext in (".pdf", ".PDF", ".docx"):
        cand = pdf_dir / f"{stem}{ext}"
        if cand.exists():
            return cand
    return pdf_dir / f"{stem}.pdf"

# corpus -> {stem: (human title, one-line description used as the markdown H1 / lead)}
_CONTRACT_DESC = (
    "Bilingual (Arabic/English) standard contract governing the relationship between "
    "insurers and private-sector health service providers in Saudi Arabia."
)
_FORMULARY_DESC = (
    "Overview of the CCHI evidence-based insurance drug formulary, co-payment rules, "
    "and the prescription filling process."
)
_EBP_DESC = (
    "The Basic Health Insurance Policy and Essential Benefit Package that defines "
    "minimum required coverage."
)
_CHI_PROVIDERS_CLASS_DESC = (
    "CHI's program for classifying and qualifying health service providers -- "
    "objectives, governance, and standards chapters (Beneficiary Rights, "
    "Provider Relationship, Population Health)."
)
_CHI_PAYERS_CLASS_DESC = (
    "CHI's program for qualifying and classifying payers (health insurance "
    "companies) -- mission, strategic objectives (2020-2024), and standards "
    "chapters mirroring the Providers Classification Program."
)
_CONTROLS_EXCLUSIONS_DESC = (
    "Standard exclusions from Health Insurance Policy coverage under CHI "
    "regulation -- self-inflicted injury, fertility treatment, congenital "
    "conditions, and related carve-outs."
)
_DEFINITIONS_DESC = (
    "Chapter One of the CHI Health Insurance Policy: the seven key policy "
    "objectives and the defined terms used throughout CHI regulation."
)
_NETWORK_DESC = (
    "CHI standards for insurer provider networks -- Minimum Network, "
    "Preferred Providers Network (PPN), and network quality/coverage "
    "requirements."
)
_SBS_CODING_DESC = (
    "CHI guideline (March 2023) for mapping provider service lists to "
    "standard code sets (SBS)."
)
_CLAIMS_MGMT_REG_DESC = (
    "CHI regulation governing qualification, tasks, and oversight of "
    "third-party Health Insurance Claims Management Companies."
)
_UNIFIED_EMPLOYER_AR_DESC = (
    "CHI's rollout plan (Arabic) for the Unified Document for the Employer -- "
    "project definition and implementation phases."
)
_BUPA_MEMBER_GUIDE_DESC = (
    "Bupa Arabia member/membership booklet: a private insurer's own member-"
    "facing policy guide, not a CHI regulatory document."
)
_TAWUNIYA_FAMILY_DESC = (
    "Tawuniya's \"MY Family\" Medical Insurance Plan policy wording -- a "
    "private insurer's own policy document, not a CHI regulatory document."
)

CORPUS_DOCS = {
    "real": {
        "unified_contract": (
            "The Unified Contract between Insurance Company and Health Service Provider",
            _CONTRACT_DESC,
        ),
        "ebp_5_tiers": (
            "Tiers Benefit Package for Private Health Insurance Beneficiaries",
            "Five-tier benefit package summary for private health insurance beneficiaries.",
        ),
        "drug_formulary": ("Insurance Drug Formulary (IDF)", _FORMULARY_DESC),
        "essential_benefit_package": (
            "Updated Essential Benefit Package (effective 1 October 2022)",
            _EBP_DESC,
        ),
    },
    "real2": {
        "chi_providers_classification_program": (
            "CHI Providers Classification Program",
            _CHI_PROVIDERS_CLASS_DESC,
        ),
        "chi_payers_qualification_classification_program": (
            "CHI's Payers' Qualification and Classification Program",
            _CHI_PAYERS_CLASS_DESC,
        ),
        "controls_and_exclusions": (
            "Controls and Exclusions (CHI Health Insurance Policy)",
            _CONTROLS_EXCLUSIONS_DESC,
        ),
        "definitions": (
            "Definitions (CHI Health Insurance Policy, Chapter One)",
            _DEFINITIONS_DESC,
        ),
        "network": (
            "Network Standards (CHI Health Insurance Policy)",
            _NETWORK_DESC,
        ),
        "sbs_code_mapping_guidelines": (
            "Guidelines for Mapping Provider Service Lists to Standard Code Sets (March 2023)",
            _SBS_CODING_DESC,
        ),
        "claims_management_qualification_regulation": (
            "Regulation of Qualification of Health Insurance Claims Management Companies",
            _CLAIMS_MGMT_REG_DESC,
        ),
        "unified_employer_document_ar": (
            "الوثيقة الموحدة لصاحب العمل",
            _UNIFIED_EMPLOYER_AR_DESC,
        ),
        "bupa_member_guide_en": (
            "Bupa Arabia -- Your Membership Booklet",
            _BUPA_MEMBER_GUIDE_DESC,
        ),
        "tawuniya_my_family_leaflet_en": (
            'Tawuniya -- Policy Wording for "MY Family" Medical Insurance Plans',
            _TAWUNIYA_FAMILY_DESC,
        ),
    },
}

# Lines that are pure page furniture and carry no regulatory content.
# Generic patterns apply to every corpus; corpus-specific ones are scoped so
# a pattern tuned for one document set can't accidentally eat real content
# in another (e.g. CCHI's "CCHI-\d" form-code footer has no ZATCA analogue).
_GENERIC_DROP_PATTERNS = [
    re.compile(r"^\s*\d{1,4}\s*$"),                        # bare page numbers
    re.compile(r"^\s*Page\s+\d+\s+of\s+\d+\s*$", re.IGNORECASE),
]
_CORPUS_DROP_PATTERNS = {
    "real": [
        re.compile(r"^\s*public\s*$", re.IGNORECASE),
        re.compile(r"^\s*Council of Health Insurance\s*-\s*Public\s*$", re.IGNORECASE),
        re.compile(r"^\s*CCHI-\S+\s*$", re.IGNORECASE),    # form-code footer (LTR part)
    ],
    # real2's CHI documents (a different slice of the same regulator's output
    # -- provider/payer classification, definitions, network standards, not
    # the CCHI unified-contract template "real" uses) carry the same bare
    # "public" watermark line but not the "real" corpus's specific
    # "Council of Health Insurance - Public" full-phrase footer or CCHI-\d
    # form code, which are tied to that specific document template.
    "real2": [
        re.compile(r"^\s*public\s*$", re.IGNORECASE),
    ],
}
# The running footer on the CCHI contract mixes a form code with Arabic; drop
# the whole line if it contains the form code anywhere. No ZATCA equivalent.
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


def _clean(text: str, corpus: str) -> str:
    drop_patterns = _GENERIC_DROP_PATTERNS + _CORPUS_DROP_PATTERNS[corpus]
    out = []
    for raw in text.splitlines():
        line = _normalize(raw.rstrip())
        if not line.strip():
            out.append("")
            continue
        if corpus == "real" and _FORMCODE.search(line):
            continue
        if any(p.match(line) for p in drop_patterns):
            continue
        # collapse runs of >1 internal space (PDF layout artifacts)
        line = re.sub(r"[ \t]{2,}", " ", line).strip()
        out.append(line)
    # collapse 3+ blank lines down to a single blank line
    joined = "\n".join(out)
    joined = re.sub(r"\n{3,}", "\n\n", joined)
    return joined.strip() + "\n"


def extract_one(real_dir: Path, pdf_dir: Path, corpus: str, stem: str, title: str, desc: str) -> tuple[int, int]:
    src = _find_source(pdf_dir, stem)
    pages = extract_pages(src)
    parts = [f"# {title}\n", f"> {desc}\n",
             f"> Source: data/{corpus}/pdfs/{src.name} (public document).\n"]
    for i, page in enumerate(pages, start=1):
        body = _clean(page or "", corpus)
        if body.strip():
            parts.append(f"\n## Page {i}\n\n{body}")
    md = "\n".join(parts).strip() + "\n"
    out_path = real_dir / f"{stem}.md"
    out_path.write_text(md, encoding="utf-8")
    return len(pages), len(md)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", choices=sorted(CORPUS_DOCS), default="real")
    ap.add_argument("--check", action="store_true", help="report only, do not write")
    args = ap.parse_args()
    real_dir = DATA_ROOT / args.corpus
    pdf_dir = real_dir / "pdfs"
    docs = CORPUS_DOCS[args.corpus]
    print(f"corpus: {args.corpus}  engine: {ENGINE}")
    for stem, (title, desc) in docs.items():
        src = _find_source(pdf_dir, stem)
        if not src.exists():
            print(f"  ! missing {src}")
            continue
        if args.check:
            print(f"  {stem}: {len(extract_pages(src))} pages ({src.suffix})")
            continue
        pages, chars = extract_one(real_dir, pdf_dir, args.corpus, stem, title, desc)
        print(f"  + {stem}.md  <- {pages} pages, {chars:,} chars")


if __name__ == "__main__":
    main()
