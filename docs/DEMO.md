# Live demo deployment

The bilingual-rag repo is wired to deploy as a Hugging Face Space (Streamlit SDK, free CPU basic). One-time setup, then an idempotent `huggingface-cli upload` redeploys after every push.

## One-time setup (interactive — do this on your machine, not in CI)

1. Get an HF token at https://huggingface.co/settings/tokens (read + write to your namespace).
2. Install the CLI and log in:

   ```bash
   pip install --user huggingface_hub
   huggingface-cli login    # paste token; saved to ~/.cache/huggingface/token
   ```

3. Create the empty Space (one time):

   ```bash
   huggingface-cli repo create bilingual-rag --type space --space_sdk streamlit
   ```

## Deploy

From this repo's root:

```bash
huggingface-cli upload --repo-type=space YousefZahran1/bilingual-rag . .
```

The Space build kicks off automatically. Watch the logs at
`https://huggingface.co/spaces/YousefZahran1/bilingual-rag` -> Settings -> Logs.

Build time on free CPU tier: ~5 minutes (most of which is downloading
`intfloat/multilingual-e5-small` once).

## Configuration

Set these as Space secrets (Settings -> Variables and secrets) if you want
real-LLM answers instead of the mock provider:

| Secret | Purpose |
|---|---|
| `LLM_PROVIDER` | `openai` or `anthropic` (default: `mock`) |
| `OPENAI_API_KEY` | Required if `LLM_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | Required if `LLM_PROVIDER=anthropic` |

The Streamlit entry point is `app.py` (already in the repo).

## Updating the demo

After any code change:

```bash
huggingface-cli upload --repo-type=space YousefZahran1/bilingual-rag . .
```

The Space rebuilds automatically. No additional steps.

## Cost

Free CPU basic tier covers the embedding model and Streamlit UI. The mock LLM
provider is free; a real LLM adds per-token cost (charged to whatever API key
you set).

## Notes

- The `chroma_db/` directory is built on first request, not committed. The
  Space's ephemeral storage is sufficient for the 5-doc sample corpus.
- For a larger corpus that should persist across Space restarts, mount HF Hub
  Datasets storage (see ROADMAP.md for the upgrade path).
