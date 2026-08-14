# Real corpus — sources & provenance

This directory holds the **real** document corpus for the bilingual RAG assistant,
alongside the small synthetic `data/sample/` set used for fast quick-start and CI.

All four documents are **public regulatory publications of the Council of Health
Insurance (CCHI / مجلس الضمان الصحي التعاوني), Saudi Arabia** — each carries a
"public" marking in its source PDF. They are included here for demonstration and
reproducibility. Copyright remains with the CCHI; no ownership is claimed.

| Markdown | Source PDF | Pages | Language | Content |
|---|---|---|---|---|
| `unified_contract.md` | `pdfs/unified_contract.pdf` | 30 | Arabic + English (bilingual, clause-by-clause) | Standard contract between insurers and private-sector health service providers |
| `essential_benefit_package.md` | `pdfs/essential_benefit_package.pdf` | 108 | English | Basic Health Insurance Policy / Essential Benefit Package (effective 1 Oct 2022) |
| `ebp_5_tiers.md` | `pdfs/ebp_5_tiers.pdf` | 15 | English | Tiers Benefit Package summary for private health insurance beneficiaries |
| `drug_formulary.md` | `pdfs/drug_formulary.pdf` | 7 | English | Insurance Drug Formulary (IDF): co-payment rules, prescription filling process |

Total: ~166 pages, ~256k characters — roughly 8× the text volume of `data/sample/`.

## How the markdown was produced

`scripts/extract_pdfs.py` extracts the embedded text layer (no OCR — none of these
PDFs need it), then conservatively cleans page furniture without ever rewriting the
regulatory text:

- strips page numbers, the "public" watermark line, and the CCHI form-code running footer;
- normalizes Latin typographic ligatures (e.g. `beneﬁts` → `benefits`) so keyword and
  dense retrieval see real words;
- fixes stray spaces injected before hyphens (`twenty ‑five` → `twenty-five`);
- collapses layout whitespace.

Regenerate at any time with:

```bash
python scripts/extract_pdfs.py      # rebuilds data/real/*.md from pdfs/
```

## Not included

The two blank submission forms that shipped with the source set — the *Healthcare
provider addition request form* and the *Pharmaceutical company submission form* —
are process templates with no question-answerable content, so they are intentionally
excluded from the corpus.

## Evaluation

`data/real/eval_questions.jsonl` contains questions grounded in the actual text of
these documents (bilingual, including Arabic questions against the Unified Contract),
validated for internal consistency with:

```bash
python -c "from pathlib import Path; from eval.validate_eval_set import validate; \
e,w=validate(Path('data/real/eval_questions.jsonl'), Path('data/real')); \
print(len(e),'errors', len(w),'warnings')"
```
