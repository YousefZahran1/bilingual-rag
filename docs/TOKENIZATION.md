# Token Management

## Why token count, not character count

This pipeline is constrained by the embedding model's real 512-token input
limit (`intfloat/multilingual-e5-small`), not an arbitrary character count
and not the LLM's much larger context window — those are two different
budgets for two different models, and only the embedding model's limit
affects retrieval quality if exceeded (text past token 512 is silently
truncated by the sentence-transformers pipeline, not rejected — a passage
could look complete and still be missing its second half in the vector
index).

`src/rag/chunker.py` measures chunk size with the same tokenizer used to
embed the chunk (`AutoTokenizer.from_pretrained
("intfloat/multilingual-e5-small")`), targeting `MAX_TOKENS = 400` per
chunk — about 20% headroom under the 512 limit, covering:
- the `"passage: "` prefix `store.py` adds before embedding (a few tokens)
- the tokenizer's own special tokens (BOS/EOS)
- general safety margin against subword-tokenization edge cases

Before this, chunk size was a per-language *character* budget (`{"ar": 700,
"en": 1100, "mixed": 900}`) — a reasonable estimate (it already accounted
for Arabic being denser per character), but an estimate, not a measurement
against the actual tokenizer. See `docs/EVAL.md`'s "v0.4: Token-based
chunking" section for the before/after retrieval numbers.

## Measured Arabic vs English token density

Computed by `scripts/measure_tokenization.py` over the real 34-document
corpus in `data/sample/`, using `intfloat/multilingual-e5-small`'s
tokenizer directly (not estimated, not a generic claim about Arabic
tokenization in general — this is this specific tokenizer on this specific
corpus):

| Language | Docs | Total words | Total tokens | Tokens/word |
|---|---|---|---|---|
| Arabic | 14 | 2,067 | 3,674 | **1.78** |
| English | 15 | 2,214 | 3,340 | **1.51** |
| Mixed | 5 | 1,088 | 1,807 | 1.66 |

**Arabic tokenizes ~1.18x denser than English on this tokenizer** — every
Arabic word costs about 18% more tokens on average than an English word of
equivalent meaning.

This is a smaller gap than the 2-4x figures sometimes cited for Arabic
tokenization — those numbers are typically measured against English-centric
BPE tokenizers (e.g. GPT's `tiktoken`), which were trained on
overwhelmingly-English corpora and fragment non-Latin scripts more
aggressively. `multilingual-e5-small`'s tokenizer is a SentencePiece
tokenizer trained on a genuinely multilingual (XLM-R) corpus, which is
specifically why it doesn't show the same blowup — worth stating plainly
rather than importing a number that doesn't apply to this model.

Practical effect: at `MAX_TOKENS = 400`, an average Arabic chunk holds
roughly 15% fewer words than an average English chunk of the same token
budget — a real, measured, small effect, not the 2-3x difference a naive
character-count budget might suggest if you assumed the commonly-cited
BPE ratio applied here too.

To reproduce or re-measure after a corpus or model change:
```bash
python -m scripts.measure_tokenization
```
