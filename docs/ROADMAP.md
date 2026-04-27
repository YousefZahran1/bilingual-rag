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

## v0.2
- [ ] Hybrid retrieval (BM25 + dense) for better coverage on rare terms
- [ ] Re-ranker (cross-encoder) on top-20 → top-4
- [ ] Ragas integration: faithfulness, answer relevancy, context precision
- [ ] Red-team set (questions outside corpus, malicious inputs)

## v0.3
- [ ] Streaming responses
- [ ] Citation hover-preview in UI
- [ ] Conversation memory (short-term, per session)
- [ ] Live demo on Hugging Face Spaces or Fly.io

## Stretch
- [ ] Fine-tuned reranker on Saudi healthcare corpus
- [ ] PII detection + redaction pre-ingest
- [ ] Multi-tenant support (org-scoped collections)
