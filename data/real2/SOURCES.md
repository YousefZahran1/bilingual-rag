# Real2 corpus — sources & provenance

This directory holds a **second slice of the healthcare/insurance domain**,
distinct from `data/real`'s corpus in angle rather than subject: `data/real`
covers CCHI's insurer-facing contract and benefit-package documents;
`data/real2` covers the **regulator's standards for qualifying and
classifying the payers and providers it oversees**, plus **two real private
insurers' own member-facing policy documents** (Bupa Arabia, Tawuniya) —
content `data/real` does not have at all. This is not a repeat of `data/real`
and not a different vertical (e.g. tax) — it is regulator-of-payers +
real-insurer documents within the same domain, added to test whether the
retrieval pipeline generalizes across document *types* within healthcare
insurance (classification/qualification standards, defined-term glossaries,
network rules, and actual consumer policy wordings), not just across topics.

All documents are **public regulatory and policy publications**. Copyright
clarification: this repository's PolyForm Noncommercial license governs the
code and retrieval pipeline only. The reproduced regulatory and policy text
remains the copyright of its issuing authority (the Council of Health
Insurance, "CHI") or insurer (Bupa Arabia, Tawuniya) — used here for
noncommercial research and demonstration, no ownership claimed.

**Language mix, honestly:** nine of the ten documents are English. One —
`unified_employer_document_ar.md` — is Arabic. This is a real reflection of
what was available/collected, not a deliberately balanced bilingual set like
`data/real`'s unified contract. Cross-lingual eval coverage on this corpus
therefore leans on English questions grounded in that one Arabic document
(and vice versa) rather than parallel EN/AR document pairs.

## Regulator (Council of Health Insurance, "CHI")

| Markdown | Source PDF | Pages | Language | Content |
|---|---|---|---|---|
| `chi_providers_classification_program.md` | `pdfs/chi_providers_classification_program.pdf` | 53 | English | CHI's program for classifying/qualifying health service providers — 4 chapters (Approvals & Revenue Cycle Management, Operational Excellence, Healthcare Information Management, Governmental Requirements) |
| `chi_payers_qualification_classification_program.md` | `pdfs/chi_payers_qualification_classification_program.pdf` | 53 | English | CHI's mirrored program for payers (insurance companies) — 8 chapters (Governance & Leadership, Beneficiary Rights, Providers Relationship, Population Health & Innovative Products, Value Based Healthcare, Healthcare Information Management, Quality & Risk Management, Governmental Requirements) |
| `definitions.md` | `pdfs/definitions.pdf` | 9 | English | Chapter One of the CHI Health Insurance Policy: 66 defined terms (Dependent, Preterm Baby, Fraud, Abuse, Negligence, etc.) and the policy's seven key objectives |
| `controls_and_exclusions.md` | `pdfs/controls_and_exclusions.pdf` | 3 | English | Standard CHI policy exclusions (26 numbered items: self-inflicted injury, fertility treatment, cosmetic procedures, war/nuclear/terrorism carve-outs, etc.) |
| `network.md` | `pdfs/network.pdf` | 5 | English | CHI provider-network standards — Minimum Network, Preferred Providers Network (PPN), access-time/distance requirements by area type |
| `sbs_code_mapping_guidelines.md` | `pdfs/sbs_code_mapping_guidelines.pdf` | 22 | English | CHI guideline (March 2023) for mapping provider service lists to the Saudi Billing System (SBS), based on the Australian classification, mandated by the Saudi Health Council |
| `claims_management_qualification_regulation.md` | `pdfs/claims_management_qualification_regulation.pdf` | 14 | English | CHI regulation for qualifying third-party Health Insurance Claims Management Companies — fees, insurance-coverage minimums, renewal deadlines, oversight |
| `unified_employer_document_ar.md` | `pdfs/unified_employer_document_ar.pdf` | 10 | Arabic | CHI's 4-phase rollout plan (2016–2017) requiring each employer to consolidate onto a single health insurance policy covering all employees and dependents |

## Private insurer

| Markdown | Source PDF | Pages | Language | Content |
|---|---|---|---|---|
| `bupa_member_guide_en.md` | `pdfs/bupa_member_guide_en.pdf` | 19 | English | Bupa Arabia's own member/membership booklet — FAQ-style guide to co-payment, claims/reimbursement (90-day window), MPN, and how coverage works, from the insurer's side, not CHI's |
| `tawuniya_my_family_leaflet_en.md` | `pdfs/tawuniya_my_family_leaflet_en.pdf` | 14 | English | Tawuniya's own policy wording for "MY Family" Medical Insurance Plans — definitions, terms and conditions as issued by the insurer |

Total: 10 documents, ~213 pages, ~301k characters.

## Excluded: MedGulf Group Health Policy

`pdfs/GROUP HEALTH POLICY.pdf` (MedGulf's Group Health Policy, 38 pages) was
collected but **is not part of the corpus**. Its text layer is corrupted —
confirmed with both extraction engines (`pymupdf` and `pypdf`), which
produced the same style of garbled, non-linguistic glyph output on every
content page (e.g. `"æ ò ø ÷ ó"` runs, or Latin-1-shifted gibberish like
`"Ì¸» °±´·½§¸±´¼»®"` instead of readable text) — a font/encoding problem in
the source PDF itself, not an extraction bug. Only its "Draft" watermark
pages and a handful of near-empty pages extract cleanly; every page with
actual policy content is unreadable. The PDF stays on local disk for
reference but is `.gitignore`d (not committed to the repo -- an unused,
5.8 MB broken binary isn't worth the repo weight) and deliberately excluded
from `CORPUS_DOCS` in `scripts/extract_pdfs.py` — extracting and shipping
garbled text would have
silently poisoned retrieval and eval with content that doesn't correspond
to what the document actually says.

## How the markdown was produced

`scripts/extract_pdfs.py --corpus real2` extracts the embedded text layer
(no OCR — these PDFs don't need it, MedGulf's issue is a codepoint mapping
problem OCR wouldn't fix either) and conservatively strips page furniture:
bare page numbers, `Page X of Y` footers, and the bare `public` watermark
line these CHI documents share with `data/real`'s CCHI documents (same
regulator, similar document template) — without ever rewriting the
regulatory or policy text itself.

Regenerate at any time with:

```bash
python scripts/extract_pdfs.py --corpus real2      # rebuilds data/real2/*.md from pdfs/
```

## Evaluation

`data/real2/eval_questions.jsonl` (46 questions, 24 dev / 22 test) is
grounded in the actual text of these ten documents, tagged
`numeric | definition | multi_doc | cross_lingual | unanswerable`.
Validated for internal consistency with:

```bash
python -m eval.validate_eval_set --corpus real2
```
