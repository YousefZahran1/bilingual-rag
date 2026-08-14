# [C] Diagram Prompts — bilingual-rag (verified against actual code)

**Why this file exists:** The previous 5 prompts referenced files that are NOT in the repo
(`parent_child.py`, `retrieval.py`, `pipeline.py`) and features that are NOT built
(BM25, RRF, cross-encoder reranking, metadata pre-filters, parent-child indexing).
Diagrams generated from those prompts would be fiction and would collapse in an interview.

Every prompt below was written after reading the real code at
`https://github.com/YousefZahran1/bilingual-rag` (v0.1, files under `src/` and `eval/`).
All function names, constants, and return types below are verbatim from the code.

---

## Prompt 1: Language-Aware Document Chunker

```
Create a visual explanation of how the language-aware document chunker works in
`src/rag/chunker.py` (`chunk_document`, `detect_language`, `_windowed`).

Use a step-by-step flowchart with clear annotations explaining each operation:
1. Language detection via `detect_language(text)` from `src/rag/lang.py` — counts Arabic
   Unicode-block characters vs ASCII letters; returns 'ar' (>=70% Arabic), 'en' (<=30%),
   or 'mixed' (in between). No external langdetect library — pure Unicode range checks
   over 5 Arabic blocks (0x0600–0x06FF, 0x0750–0x077F, 0x08A0–0x08FF, 0xFB50–0xFDFF,
   0xFE70–0xFEFF).
2. Per-language CHARACTER budget selection from CHUNK_BUDGET = {"ar": 700, "en": 1100,
   "mixed": 900} — Arabic gets smaller chunks because Arabic script is denser in tokens
   per character. OVERLAP = 120 characters.
3. Paragraph-first splitting on blank lines (regex `\n\s*\n`), then sentence splitting
   with SENTENCE_SPLIT = `(?<=[.!?؟।。])\s+|\n+` — note it handles the Arabic question
   mark ؟ and CJK full stops.
4. Greedy sentence assembly: sentences are appended to the current chunk until adding
   the next one would exceed the budget; then the chunk is flushed and the LAST 120
   characters of the previous chunk are carried forward as overlap into the next chunk.
5. Oversized-sentence fallback: any single sentence longer than the budget is sliced by
   `_windowed(text, budget, overlap)` — a hard sliding window stepping
   `i += budget - overlap`.
6. Output: `list[Chunk]` where Chunk is a frozen dataclass with exactly four fields:
   `text`, `source`, `chunk_id`, `language`.

Include small code snippets where relevant, but focus on making the logic visually
intuitive. Use color coding to distinguish between:
- Language Detection Phase
- Budget Selection Phase
- Paragraph/Sentence Splitting & Greedy Assembly Phase
- Overlap Carry & Oversized-Sentence Windowing Phase
- Output Chunk Assembly Phase

Make the visualization detailed enough for engineers (function signatures, the exact
regex, return type `list[Chunk]`) but clear enough for non-technical stakeholders to
understand why Arabic and English documents get different chunk sizes and why overlap
prevents answers from being cut in half at chunk boundaries.

IMPORTANT — do NOT invent features. This chunker has NO structural/heading parsing,
NO legal-clause detection, NO token counting (budgets are in characters), NO strategy
dispatcher. It is one strategy: paragraph → sentence → hard window fallback.
```

---

## Prompt 2: Vector Store — Lazy Chroma Wrapper, Ingestion & Retrieval

```
Create a visual explanation of how ingestion and vector storage/retrieval work in
`src/rag/ingest.py` (`ingest_path`) and `src/rag/store.py` (`VectorStore.add`,
`VectorStore.retrieve`, `_get_collection`).

Use a step-by-step flowchart with clear annotations explaining each operation:
1. Ingestion walk: `ingest_path` scans a directory recursively for `.md` / `.txt`
   files, reads each with UTF-8 (errors ignored), and calls `chunk_document(text,
   source)` per file.
2. Lazy initialization in `_get_collection()`: chromadb and sentence-transformers are
   imported only on first use, so the package stays importable in CI without heavy
   deps. Creates a `chromadb.PersistentClient` at VECTOR_DIR (default `./chroma_db`)
   with a SentenceTransformerEmbeddingFunction using
   `intfloat/multilingual-e5-small`, collection metadata `{"hnsw:space": "cosine"}`.
3. Upsert path in `add(chunks)`: document IDs are built as `f"{source}::{chunk_id}"`
   (idempotent re-ingestion — same file re-ingested overwrites, never duplicates);
   metadata per chunk is `{source, chunk_id, language}`.
4. Query path in `retrieve(query, top_k=4)`: the query is prefixed with `"query: "`
   because multilingual-e5 models require asymmetric query/passage prefixes for good
   retrieval — show this as a deliberate, model-specific step.
5. Chroma returns cosine DISTANCES; the code converts to a similarity score with
   `score = 1.0 - dist`, and returns `list[RetrievedPassage]` — a dataclass with
   `text, source, chunk_id, language, score`.

Include small code snippets where relevant, but focus on making the logic visually
intuitive. Use color coding to distinguish between:
- File Ingestion & Chunking Phase
- Lazy Client/Collection Initialization Phase
- Embedding & Upsert Phase
- Query Prefixing & Top-K Retrieval Phase
- Score Conversion & Output Phase

Make the visualization detailed enough for engineers (ID scheme, e5 prefix convention,
cosine distance-to-score conversion) but clear enough for non-technical stakeholders
to understand how a question in either language finds the right passages in a shared
multilingual vector space.

IMPORTANT — do NOT invent features. There is NO BM25, NO hybrid retrieval, NO rank
fusion, NO metadata pre-filtering, NO reranker. Retrieval is a single dense top-k
cosine query against one Chroma collection.
```

---

## Prompt 3: Answer Generation — Bilingual Prompting & Pluggable Providers

```
Create a visual explanation of how answer generation works in `src/rag/generator.py`
(`generate`, `_build_prompt`, `_provider`, `MockProvider`) and
`src/rag/providers/` (`OpenAIProvider`, `AnthropicProvider`).

Use a step-by-step flowchart with clear annotations explaining each operation:
1. Query-language detection: `generate(query, passages)` calls `detect_language(query)`
   — the ANSWER language follows the QUESTION language, not the document language.
2. Bilingual system-prompt selection in `_build_prompt`: if lang == 'ar' the system
   prompt is written in Arabic (answer only from passages, say "لا أعلم" if absent,
   cite sources); otherwise an equivalent English system prompt. Show both side by side.
3. Passage block construction: each retrieved passage is numbered
   `[i] (source: ..., chunk_id: ...)` and appended under "Passages:" after
   "Question: {query}".
4. Provider dispatch in `_provider()` — reads env var LLM_PROVIDER
   ('mock' default / 'openai' / 'anthropic') and lazily imports only the chosen
   provider. All providers implement one Protocol method:
   `complete(system: str, user: str) -> str`.
5. MockProvider path: deterministic extractive fallback — finds "Passages:" in the
   user prompt and returns the first 300 characters. This is why the pipeline runs
   end-to-end with zero API keys, and why keyword_coverage in the eval is low under
   mock but rises with a real LLM.
6. Output assembly: `AnswerWithCitations(answer, citations, language)` where citations
   is a list of `{index, source, chunk_id, score}` dicts (score rounded to 3 decimals).

Include small code snippets where relevant, but focus on making the logic visually
intuitive. Use color coding to distinguish between:
- Language Detection & Prompt Selection Phase
- Passage Block Assembly Phase
- Provider Dispatch Phase (mock / openai / anthropic branches)
- Answer + Citation Assembly Phase

Make the visualization detailed enough for engineers (the Protocol interface, env-var
dispatch, lazy imports) but clear enough for non-technical stakeholders to understand
how the same pipeline answers in the user's language and stays grounded in retrieved
text with citations.

IMPORTANT — do NOT invent features. There is NO streaming, NO conversation memory in
the generator, NO reranking. One provider call per question.
```

---

## Prompt 4: End-to-End Request Flow — FastAPI /chat + Streamlit UI

```
Create a visual explanation of the full request lifecycle across `src/api/app.py`
(FastAPI `/chat`) and `src/ui/app.py` (Streamlit UI).

Use a step-by-step flowchart with clear annotations explaining each operation:
1. User types a question (Arabic or English) in the Streamlit UI; a top-k slider
   (1–10, default 4) sets retrieval depth.
2. Streamlit POSTs `{question, top_k}` via httpx to `{API_URL}/chat` (default
   http://localhost:8000, 60s timeout) with error handling on HTTPError.
3. FastAPI validates the request with Pydantic: `ChatRequest` enforces
   question length 1–2000 chars and top_k in [1, 20].
4. The endpoint runs the two-step pipeline against a single module-level
   `VectorStore` instance shared across requests:
   `passages = _store.retrieve(req.question, top_k)` then
   `result = generate(req.question, passages)`.
5. Typed response: `ChatResponse {answer, citations: List[Citation], language}`.
6. UI rendering: the answer div direction flips to `dir='rtl'` when
   response language == 'ar' (RTL-correct Arabic rendering); citations render in an
   expander with source, chunk_id, and score; session state keeps the last 3 Q&A pairs.
7. Also show the `/health` endpoint returning `{status, version}` as the ops sidecar.

Include small code snippets where relevant, but focus on making the logic visually
intuitive. Use color coding to distinguish between:
- UI Input & HTTP Request Phase
- API Validation Phase (Pydantic constraints)
- Retrieval + Generation Pipeline Phase
- Typed Response & RTL-Aware Rendering Phase

Make the visualization detailed enough for engineers (Pydantic field constraints,
shared store instance, timeout values) but clear enough for non-technical stakeholders
to follow one question traveling from the text box to a cited, correctly-rendered
answer.

IMPORTANT — do NOT invent features. There is NO auth, NO streaming, NO server-side
conversation memory (history lives only in Streamlit session state, last 3 items).
```

---

## Prompt 5: Evaluation Harness — Three Reproducible Metrics

```
Create a visual explanation of how the evaluation harness works in
`eval/run_eval.py` over `data/sample/eval_questions.jsonl`.

Use a step-by-step flowchart with clear annotations explaining each operation:
1. Load eval items from JSONL — each item has `question`, `expected_source`, and
   `expected_keywords`.
2. For every question, run the SAME production pipeline (no special eval path):
   `store.retrieve(q, top_k)` then `generate(q, passages)`.
3. Metric 1 — retrieval_recall@k: does `expected_source` appear among the basenames
   of the top-k retrieved passages' sources? (substring match on filename).
4. Metric 2 — keyword_coverage: fraction of `expected_keywords` found
   (case-insensitive substring) in the generated answer. Annotate that under the
   default MockProvider this is intentionally low (~18%) because the mock answer is
   just an extractive 300-char slice — the metric isolates GENERATOR quality from
   RETRIEVER quality.
5. Metric 3 — language_match: does `detect_language(answer)` equal
   `detect_language(question)`? Verifies the bilingual contract end-to-end.
6. Output: printed summary table (the same numbers committed in docs/EVAL.md and the
   README: recall@4 8/8, language_match 8/8, keyword_coverage 3/17 under mock).

Include small code snippets where relevant, but focus on making the logic visually
intuitive. Use color coding to distinguish between:
- Eval Set Loading Phase
- Pipeline Execution Phase (identical to production path)
- Per-Metric Scoring Phase (three parallel metric lanes)
- Aggregation & Reporting Phase

Make the visualization detailed enough for engineers (JSONL schema, exact matching
rules, why the metrics decouple retrieval from generation) but clear enough for
non-technical stakeholders to understand how the system proves it retrieves the right
document and answers in the right language — reproducibly, with one command.

IMPORTANT — do NOT invent features. There is NO Ragas, NO LLM-as-judge, NO
faithfulness scoring. Three deterministic string/set metrics, by design (roadmapped
Ragas integration is v0.2, not built).
```

---

## Notes

- The old "Prompt 1" (structure-aware dispatcher / legal clauses) described functions
  that do not exist: `_chunk_structured`, `_chunk_token`, `_segments`,
  `_split_oversized`. The real chunker is corrected in Prompt 1 above.
- Old Prompts 2–5 (parent-child indexing, hybrid BM25+RRF, cross-encoder rerank,
  two-stage routing) target v0.2+ roadmap features. If you build them later, those
  prompts can be resurrected — but only after the code exists.
- Each prompt ends with an explicit "do NOT invent features" guard. That line is what
  stops the diagram tool from hallucinating like last time.
