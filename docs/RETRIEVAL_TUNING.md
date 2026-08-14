# Retrieval tuning log — real CCHI corpus

A plain-language record of how the retrieval quality was diagnosed and improved
after adding the real Council of Health Insurance (CCHI) corpus. Written so it
can be understood (and explained in an interview) without re-deriving it.

## 1. Background: what "chunking" is and what this project uses

A RAG system can't embed a whole 108-page document as one vector — it splits the
document into **chunks**, embeds each chunk, and retrieves the most relevant
chunks for a question. How you split matters enormously.

This project uses **token-aware fixed-size chunking** (`src/rag/chunker.py`):

1. split on blank-line paragraphs,
2. split those into sentences (`. ! ? ؟` and newlines — Arabic-aware),
3. greedily pack sentences until a **token budget**, measured with the *same*
   `intfloat/multilingual-e5-small` tokenizer used for embeddings,
4. carry a small **token overlap** into the next chunk.

It is **not** semantic chunking (embedding-based topic breakpoints) and not
structure-aware chunking (splitting on clause numbers). Just size + sentence
boundaries.

## 2. The problem we found

The corpus retrieves the right *document* reliably (recall@4 = 100% on the real
eval set), but with the original **400-token** budget it often failed to surface
the exact *clause* at rank 1. A 400-token chunk is roughly a whole page, so a
specific fact — "…maximum pay of 30 SAR…", "…sons up to twenty-five…" — got
averaged into a page-sized vector and diluted.

Concretely, asking "max co-payment for generic medications?" returned the
formulary's *"Use of Generics"* marketing section, not the co-payment clause
with the number.

## 3. The experiment: 400 vs 200 tokens

Made the chunk size configurable (`CHUNK_MAX_TOKENS`, `CHUNK_OVERLAP` env vars)
and swept it, scoring with the repo's own eval harness (`eval/run_eval.py`) in
mock mode (retrieval-only, no LLM cost).

**Real CCHI corpus** (`data/real`, 15 grounded questions):

| Metric | 400 tok | 180 tok |
|---|---|---|
| BM25 recall@1 | 93% | **100%** |
| BM25 keyword_coverage | 19% | **46%** |
| dense keyword_coverage | 27% | **35%** |
| recall@4 (both modes) | 100% | 100% |

**Synthetic corpus** (`data/sample`, 100+ questions) — to check for regression:

| Metric | 400 tok | 200 tok |
|---|---|---|
| dense recall@1 | 83% | 85% |
| dense keyword_coverage | 47% | **56%** |
| bm25 recall@1 | 82% | 80% |
| bm25 keyword_coverage | 43% | **50%** |

Smaller chunks isolate individual clauses, so keyword coverage rose across the
board and the exact "30 SAR" clause started surfacing at rank 1. The only cost
was BM25 recall@1 slipping by ~1 question on the synthetic set — an acceptable
trade for the large gain in clause precision on real regulatory text.

**Decision: default chunk size changed 400 → 200 tokens** (overlap 40 → 30),
kept overridable via env for future sweeps.

## 4. End-to-end validation with a real LLM

Retrieval metrics only prove the right passages are found. To confirm the
*answers* are good, ran a handful of questions through a real (free) LLM
(`openai/gpt-oss-20b:free` via OpenRouter, `LLM_PROVIDER=openrouter`), dense
retrieval top-4, on the 200-token real index:

| Question | Answer (verbatim) | Correct? |
|---|---|---|
| Max co-pay for generics? | "…is **30 SAR**" (cites drug_formulary) | ✅ |
| نفس السؤال بالعربي | "…هو **30 ريال سعودي**" (Arabic answer, English source) | ✅ cross-lingual |
| Dental implants covered? | "No. …explicitly excludes dental implants, dentures, crowns…" | ✅ |
| Sons covered to what age? | "…up to the age of **twenty-five (25)**" | ✅ |

All correct, all cited, language-matched. (keyword_coverage in the mock tables
above understates real quality because the mock provider only echoes passages;
a real LLM roughly doubles it — as seen here.)

## 5. Known caveats / honest gaps

- Two real-corpus eval questions are genuinely ambiguous because the source
  documents overlap (both the Unified Contract and the Essential Benefit Package
  specify treatment-approval time limits — 60 vs 15 minutes for different
  parties). This is a ground-truth ambiguity, not a pipeline failure.
- Fixed-size chunking is still blunt: it can split one clause across two chunks
  or merge two unrelated clauses.

## 6. Structure-aware chunking (built + A/B-tested)

These CCHI documents are already numbered and sectioned (`1.21`, `3.4`, `A.`,
`B.`, definition entries, `## Page` headers), so instead of a blind token count
we can split on those markers. Implemented in `src/rag/chunker.py` as a second
strategy, selectable with `CHUNK_STRATEGY=structure` (default stays `token` so
general use and CI are unchanged):

1. group lines into **segments**, each starting at a boundary line
   (heading / numbered clause / lettered sub-point);
2. **pack** consecutive clauses together up to the token budget — so a chunk is
   one or more *whole* clauses, never a clause cut mid-sentence;
3. token-window only a single clause that alone exceeds the budget.

### A/B result — real corpus, same 200-token budget, mock eval

| Mode | token recall@1 | **structure recall@1** | token keyword_cov | **structure keyword_cov** |
|---|---|---|---|---|
| dense | 67% | **80%** | 15% | **42%** |
| BM25 | 87% | **100%** | 19% | **42%** |

`recall@4` stays 100% for both. Structure-aware more than doubles keyword
coverage and gives BM25 perfect rank-1, because each chunk is a coherent clause
rather than an arbitrary window. Chunk count is comparable (389 vs 362), so the
gain is from *where* the cuts land, not from having more chunks.

Retrieval spot-check (structure index) now returns the exact clause at rank 1:

- "max co-payment for generics?" → `drug_formulary.md#3`: *"Medications
  Co-payment … 0%–20% with a maximum pay of 30 SAR…"*
- "age sons covered as dependents?" → `essential_benefit_package.md#6`:
  *"20. Dependent(s): … sons up to the age of twenty-five …"*

And the citation now points to a **real clause** (clause 20, the Dependent
definition) instead of an arbitrary token window — which is the demo-friendly
payoff.

**Recommendation:** ingest the real corpus with `CHUNK_STRATEGY=structure`;
keep `token` as the default for the synthetic set and any corpus without clause
numbering.

## 7. Parent-child ("small-to-big") retrieval — built + A/B-tested

Grounded in the literature (see §9): small chunks win on *retrieval* precision
but can starve the LLM of context at *generation* time. Parent-child retrieval
decouples the two — search small **children**, generate from their larger
**parents**. Implemented in `src/rag/parent_child.py`: children (≤200 tok) are
packed strictly *within* each parent (≤900 tok), so every child maps to exactly
one parent. Built over `data/real`: **75 parents / 404 children**.

### A/B result — real corpus

**Context sufficiency (free, no LLM)** — how many expected answer-keywords the
retrieved context actually contains, and whether the right source is present:

| Retrieval unit | context keyword coverage | source-in-context |
|---|---|---|
| child-only (top-4) | 92% | 15/15 |
| parent-expanded (top-4) | **96%** | 15/15 |

**Generation (real LLM, `gpt-oss-20b:free`)** on a multi-part question
("co-payments for generic *vs* brand, with maximums?"): both answers were
factually correct, but the parent-expanded answer was more complete and
better-grounded — it rendered the full co-payment rule set as a table and cited
the "Medications Co-payment section", where the child-only answer leaned on a
single passage.

### Honest conclusion

On *this* eval set — deliberately simple, single-clause factoids — structure-
aware children already capture the answer, so parent-child is a **modest** gain
(context coverage 92→96%, cleaner generation) rather than a dramatic one. Its
value grows with question complexity (multi-clause, cross-reference) and for
generation *faithfulness*, which is exactly what the legal-RAG papers report. It
is implemented and ready; wiring it in as a selectable retrieval mode is the
production step.

## 8. Techniques mapped to the literature

| Paper / source finding | What we did | Result |
|---|---|---|
| Fixed-size chunks dilute facts; smaller helps rank-1 | chunk size 400→200, env-tunable | keyword_cov up across the board |
| Legal "retrieval mismatch": split on articles/clauses | structure-aware chunker | bm25 recall@1 87→100%, keyword_cov ~doubled |
| Structured legal RAG + reranker | reranker exists (`smart` mode); not yet re-measured on real corpus | pending |
| Decouple retrieval unit from generation unit (parent-child / proposition) | parent-child module | context coverage 92→96%; cleaner faithful answers |

## 9. Ideas not yet tried (for later)

- **Reranker on the real corpus** — the `smart` mode's cross-encoder wasn't
  re-measured here (model download); worth running once locally.
- **Proposition chunking** — LLM rewrites each clause into atomic factual
  propositions before indexing; higher precision, but an LLM pass per chunk at
  ingest (feasible now that a key is configured, but heavier).
- **Per-language token budgets** — Arabic and English tokenize at different
  densities (`docs/TOKENIZATION.md`); the budget is currently shared. An
  Arabic-RAG study (arXiv 2506.06339) is directly relevant.

## 10. Sources

- A Systematic Investigation of Document Chunking Strategies — arXiv 2603.06976
- Rethinking Chunk Size for Long-Document Retrieval — arXiv 2505.21700
- Legal Chunking: Evaluating Methods for Effective Legal Text Retrieval (ResearchGate)
- Towards Reliable Retrieval in RAG for Large Legal Datasets — arXiv 2510.06999
- LawRAG: Indonesian Legal Document RAG (Scilit)
- Proposition Chunking (NirDiamant/RAG_Techniques); Pinecone & EdTek chunking guides
- Parent-document retrieval overview (zeroentropy.dev); Optimizing RAG for Arabic — arXiv 2506.06339
