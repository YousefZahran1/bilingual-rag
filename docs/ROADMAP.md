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
- [ ] Ragas integration: faithfulness, answer relevancy, context precision
  (now unblocked — needs a real LLM provider, which now exists)
- [ ] Streaming responses
- [ ] Citation hover-preview in UI
- [ ] Conversation memory (short-term, per session)
- [ ] Live demo on Hugging Face Spaces or Fly.io

## Stretch
- [ ] Fine-tuned reranker on Saudi healthcare corpus
- [ ] Swap the reranker for `BAAI/bge-reranker-v2-m3` (better multilingual quality, but ~2.2GB — a deliberate size/quality tradeoff was made against this for v0.2, see the Defense Brief)
- [ ] PII detection + redaction pre-ingest
- [ ] Multi-tenant support (org-scoped collections)
- [x] ~~Investigate why hybrid+rerank underperforms dense-only on numeric-exact-match questions~~ — done in v0.3 via `--mode bm25_only`: it's the cross-encoder reranker specifically, not BM25 or RRF fusion (see docs/EVAL.md)
- [ ] Build the actual fix: a numeric-aware query router or reranker bypass, now that the cause is known (skip the cross-encoder step for numeric-tagged/detected queries and use BM25's own ranking instead)
- [ ] Multi-document question regression (hybrid_rerank recall drops vs dense there too) — same reranker-culprit hypothesis untested for this subset
