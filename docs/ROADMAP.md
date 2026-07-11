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
- [ ] Ragas integration: faithfulness, answer relevancy, context precision

## v0.3
- [ ] Streaming responses
- [ ] Citation hover-preview in UI
- [ ] Conversation memory (short-term, per session)
- [ ] Live demo on Hugging Face Spaces or Fly.io

## Stretch
- [ ] Fine-tuned reranker on Saudi healthcare corpus
- [ ] Swap the reranker for `BAAI/bge-reranker-v2-m3` (better multilingual quality, but ~2.2GB — a deliberate size/quality tradeoff was made against this for v0.2, see the Defense Brief)
- [ ] PII detection + redaction pre-ingest
- [ ] Multi-tenant support (org-scoped collections)
- [ ] Investigate why hybrid+rerank underperforms dense-only on numeric-exact-match and multi-document questions (see docs/EVAL.md) — likely needs a numeric-aware fusion weight or query router instead of always reranking
