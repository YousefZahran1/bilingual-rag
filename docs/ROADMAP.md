# Roadmap

## v0.1 (now)
- [x] Multilingual embedding pipeline (multilingual-e5-small)
- [x] Chroma persistent vector store
- [x] Language-aware chunker
- [x] FastAPI `/chat` with citations
- [x] Streamlit UI with bilingual toggle
- [x] Mock LLM for end-to-end runs without API keys
- [x] Eval harness with retrieval + language metrics
- [x] Dockerfile + docker-compose

## v0.2 (now)
- [x] Hybrid retrieval (BM25 + dense, fused with Reciprocal Rank Fusion)
- [x] Re-ranker (cross-encoder) on top-20 → top-4
- [x] Corpus grown 5 → 34 docs, eval set grown 8 → 89 questions (see docs/EVAL.md)
- [x] Red-team / abstain set folded into the eval set (`is_answerable: false`, ~18 questions)
- [x] Fixed a real bug found during this work: `store.py` was missing the e5 `"passage: "` prefix on the document side (query side was already correct) — see `[C] Defense Brief.md`

## v0.3 (in progress)
- [x] Real LLM provider wired up (OpenRouter, `openai/gpt-oss-20b:free`) —
  `openai`/`anthropic` packages were also missing from `requirements.txt`
  and `.env` was never actually loaded anywhere; both fixed alongside this
- [x] First real-LLM eval run (partial: 62/89 questions, blocked by
  OpenRouter's free-tier daily cap, not by code) — keyword_coverage 37%→69%
  vs mock. See `docs/EVAL.md`.
- [x] Found and fixed a real prompt-injection vulnerability via the real-LLM
  run: model complied with 6/9 "ignore your instructions"-style questions.
  System prompt hardened.
- [x] Added `--mode bm25_only` and answered the "why does hybrid hurt
  numeric questions" question from v0.2: it's specifically the cross-encoder
  reranker, not BM25 or RRF fusion — BM25 alone has the best numeric
  recall@4 of all three modes. See `docs/EVAL.md`.
- [x] Finished the real-LLM eval across all three modes (dense/hybrid_rerank/
  bm25_only, 84-88 of 89 questions each) and re-verified the prompt-injection
  fix: **100% correct refusal across all three modes** (51/51 unanswerable
  questions that got a real answer), up from 33% before hardening.
- [x] Found and fixed a bug in the eval harness's own abstain-detection
  scorer along the way (curly-quote/phrasing mismatches caused genuine
  refusals to score as failures) — see docs/EVAL.md's "quieter finding"
- [x] Token-based chunking: replaced the language-aware character-budget
  chunker with one measured against the real embedding-model tokenizer
  (`MAX_TOKENS = 400` at the time, ~20% headroom under the 512-token limit;
  default later swept to 200 in v0.4 — see docs/RETRIEVAL_TUNING.md). recall@4
  unchanged (69/71), recall@1 up by 1 question — see docs/EVAL.md and
  docs/TOKENIZATION.md for the measured AR/EN token density this
  replaces an estimate with.
- [x] Architecture diagram moved to a GitHub-native Mermaid flowchart at the
  top of README.md (was ASCII, mid-document), explicitly labeling the 4
  cross-lingual signals (native multilingual embeddings, hybrid search,
  cross-lingual reranking, language-consistent synthesis) with their real
  measured numbers instead of just architectural claims. Added Cohere
  Rerank-3/3.5 to the reranker decision table as a considered-and-rejected
  alternative (paid API, conflicts with this project's free-cost design).
- [x] Ragas integration built (`eval/run_ragas.py`, `eval/_e5_embeddings.py`):
  two-phase (build real answers once, checkpointed/resumable; judge N times
  for mean±stdev, disk-cached per run so re-runs don't cost API calls
  twice). Tested with `LLM_PROVIDER=mock` (retrieval/checkpoint/resume
  logic only — a mock-generated dataset can't produce a meaningful
  faithfulness score, so `judge` itself wasn't run). **Not run for real
  numbers** — no `OPENROUTER_API_KEY` in this environment, the same
  blocker already noted below for the real-LLM eval. Also found and
  worked around a real upstream bug: `ragas` 0.4.3 (latest) fails to
  import at all (`ModuleNotFoundError` on a `langchain_community`
  submodule that no longer exists); pinned to `ragas==0.2.15`
  (`requirements-dev.txt`), the newest version confirmed to import
  cleanly. Full writeup in `docs/EVAL.md`.
- [ ] Streaming responses
- [ ] Citation hover-preview in UI
- [ ] Conversation memory (short-term, per session)
- [ ] Live demo on Hugging Face Spaces or Fly.io

## v0.4 (now) — real corpus + unified pipeline

- [x] Real CCHI corpus (`data/real`): Unified Contract, Essential Benefit
  Package, drug formulary, EBP tiers — extracted from the official PDFs with
  PyMuPDF (`scripts/extract_pdfs.py`; better reading order + RTL Arabic than
  pypdf, which stays as fallback via `EXTRACT_ENGINE`; `.docx` also supported).
  15 grounded eval questions in `data/real/eval_questions.jsonl`.
- [x] Chunk-size sweep on the real corpus: default `CHUNK_MAX_TOKENS` 400 → 200
  (overlap 40 → 30). BM25 recall@1 93→100%, BM25 keyword_coverage 19→46%,
  dense keyword_coverage 27→35%; synthetic set improved too. Full log in
  `docs/RETRIEVAL_TUNING.md`.
- [x] Structure-aware chunking (`CHUNK_STRATEGY=structure`): segments start at
  heading / numbered-clause / lettered-sub-point boundaries, whole clauses are
  packed to the token budget. A/B at the same 200-token budget: dense recall@1
  67→80%, BM25 recall@1 87→100%, keyword coverage ~doubled. Citations now land
  on real clauses (e.g. the Dependent definition, clause 20).
- [x] Parent-child ("small-to-big") retrieval (`src/rag/parent_child.py`):
  children ≤200 tok nested strictly inside parents ≤900 tok (75 parents / 404
  children on `data/real`). Context keyword coverage 92→96%; cleaner grounded
  generation on multi-part questions.
- [x] Unified production pipeline (`src/rag/pipeline.py`, `UnifiedIndex`):
  metadata inference (`doc_id, doc_type, version, effective_date, language,
  clause_number, parent_id`) + doc-type routing + metadata pre-filtering +
  hybrid dense+BM25+RRF over children + parent expansion. **15/15 parent
  recall, 100% context keyword coverage** on the real corpus — strongest
  configuration measured.
- [x] Two-stage hierarchical retrieval (`retrieve_two_stage`): parent-summary
  document routing → scoped hybrid → cross-encoder rerank → parent expansion.
  Verified correct; single-stage remains default at 4-doc scale (15/15 vs
  14/15 — routing can only lose recall on a tiny corpus).
- [x] Regression benchmark gate: `scripts/bench_pipeline.py` builds + scores a
  corpus against its eval set, non-zero exit on recall/coverage regression.
  Convention: every major new document adds 5–10 grounded Q&A pairs.
- [x] End-to-end real-LLM validation on the real corpus (OpenRouter,
  `gpt-oss-20b:free`): co-pay 30 SAR, dependent age 25, dental-implant
  exclusion — all correct, cited, language-matched (incl. Arabic question →
  Arabic answer from English source).
- [x] Relicensed MIT → PolyForm Noncommercial 1.0.0 (commercial use requires
  permission).
- [x] Wire `UnifiedIndex.retrieve`/`retrieve_two_stage` into FastAPI `/chat` +
  Streamlit: `retrieval_mode: unified | unified_two_stage`, allowlisted
  `filters` (doc_type/language/doc_id/version, 422 on unknown keys), 409
  guard + `/health` status when the index isn't built, doc_type/language UI
  facets, citations carrying doc_type/doc_title/clause. Eval parity added to
  `eval/run_eval.py`. Not the default `retrieval_mode` — `unified` beats
  `smart` on recall@4 and language_match but loses keyword_coverage, so per
  the decision rule `smart` stays default. See `docs/PIPELINE.md`'s "Wired
  in v0.5" section.
- [ ] Re-run two-stage with the multilingual reranker
  (`mmarco-mMiniLMv2`) locally; sandbox test used an English cross-encoder,
  which handicaps Arabic.
- [ ] Update `docs/TOKENIZATION.md` numbers from `MAX_TOKENS = 400` to the new
  200 default.
- [x] **Re-tuned/re-validated the numeric query router (`smart` mode)
  against the current 118-question `data/sample/eval_questions.jsonl`.**
  Retro-tagged `data/sample` and `data/real`'s eval questions with
  `split: dev|test` (~70/30, stratified by the `numeric` tag, seed 42) so
  the investigation could tune on dev and verify once on test, per this
  repo's discipline. Diagnosis: **not a router-classification bug** --
  `is_numeric_query()` precision/recall against the current set (0.890 /
  0.878) are basically unchanged from the original 0.85/0.92. The actual
  finding: within the numeric subset itself, BM25-alone is now the *worst*
  of the four modes at recall@1 on both dev (87% vs dense/hybrid_rerank's
  96%) and test (68% vs 73%) -- the empirical premise `smart` was built on
  (BM25 alone beats the reranker on numeric questions) no longer holds on
  this grown, differently-composed question set. Fix: default
  `retrieval_mode` changed from `smart` to `hybrid_rerank` in
  `src/api/app.py`/`src/ui/app.py` (v0.4.0) -- `hybrid_rerank` matches or
  beats every mode including `smart` on both splits, on recall@1,
  recall@4, and keyword_coverage. `smart`/`query_router.py` kept, not
  deleted -- it still ties `hybrid_rerank` on `data/real2`, so the routing
  idea is corpus-dependent, not dead. Full investigation, tables, and the
  root-cause discussion in `docs/EVAL.md`'s "v0.7" section.
- [x] Fixed a real bug in the eval harness: `language_match` compared the
  question's own detected language to itself (`result.language` was already
  `detect_language(query)`), so it could never fail — see
  `eval/run_eval.py`. Now scores `detect_language(result.answer)` instead.
  Top-line mock numbers in the README's Eval section and `docs/EVAL.md`
  updated to the honest post-fix results; the older real-LLM `language_match`
  numbers and the numeric/non-numeric/multi-doc subset breakdown in
  `docs/EVAL.md` still reflect the old vacuous metric and haven't been
  re-run — flagged inline in both docs, not silently left as claims.
- [x] Second real corpus (`data/real2`, 10 docs, CHI payer/provider
  classification standards + Bupa/Tawuniya private-insurer policy docs) to
  test generalization past `data/real`'s document types. 46 questions
  (dev/test split), all six retrieval modes run and reported test-split-only
  in `docs/EVAL.md`'s "v0.6" section. One collected PDF (MedGulf) excluded
  for confirmed text-layer corruption rather than extracted as garbage --
  see `data/real2/SOURCES.md`. `scripts/extract_pdfs.py` and
  `eval/validate_eval_set.py` generalized to a `--corpus` flag to support
  this and any future corpus.
- [x] External benchmark: `scripts/bench_miracl.py` against MIRACL Arabic
  dev (public, independently human-annotated -- the one eval number in this
  repo nobody here authored). Pool-based recall (not full 2M-passage
  retrieval -- see the script's docstring and `docs/EVAL.md` for why that
  scope choice is honest, not a shortcut hidden from the reader), 200
  queries, seed 42. Unflattering, reported anyway: dense-only beats hybrid
  at recall@1 (76.5% vs 68.5%) on MIRACL's general Wikipedia prose -- the
  opposite of every one of this project's own eval sets, where BM25 pulls
  its weight on structured regulatory text. The hybrid advantage is real
  for this project's document types, not universal.
- [x] Retro-tagged `data/sample` and `data/real`'s existing eval questions
  with a `split: dev|test` field (~70/30, stratified by the `numeric` tag,
  seed 42) -- used immediately by the router re-tune above.

## Stretch
- [ ] Fine-tuned reranker on Saudi healthcare corpus
- [ ] Swap the reranker for `BAAI/bge-reranker-v2-m3` (better multilingual quality, but ~2.2GB — a deliberate size/quality tradeoff was made against this for v0.2, see the Defense Brief)
- [ ] PII detection + redaction pre-ingest
- [ ] Multi-tenant support (org-scoped collections)
- [x] ~~Investigate why hybrid+rerank underperforms dense-only on numeric-exact-match questions~~ — done in v0.3 via `--mode bm25_only`: it's the cross-encoder reranker specifically, not BM25 or RRF fusion (see docs/EVAL.md)
- [x] Built the actual fix: `src/rag/query_router.py` + `--mode smart` /
  `smart_retrieve()` routes numeric queries to BM25 alone, everything else
  through hybrid+rerank. Matches or beats every individual mode on every
  measured subset (overall recall@4 97%, vs hybrid_rerank's 94%). Now the
  default `retrieval_mode`. See docs/EVAL.md.
- [x] Multi-document question regression — resolved as a side effect of the
  numeric router, not separately investigated: `smart` mode's multi-doc
  recall@4 (87%, 13/15) beats all three single-strategy modes, including
  dense (80%) and hybrid_rerank (73%). Turned out to share enough overlap
  with the numeric fix that no separate mechanism was needed.
