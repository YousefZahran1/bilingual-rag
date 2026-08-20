# Live demo deployment

The bilingual-rag repo is wired to deploy as a Hugging Face Space (Streamlit SDK, free CPU basic). One-time setup, then an idempotent `huggingface-cli upload` redeploys after every push.

The app is two processes -- a FastAPI backend the Streamlit UI talks to over
HTTP, same split as local dev -- but Spaces only exposes one public port.
Root `app.py` (the Spaces entry point) starts the FastAPI backend as a
background subprocess bound to `127.0.0.1:8000` (never exposed publicly),
waits for it to answer `/health`, then execs into Streamlit on the public
port. If the backend fails to start or doesn't become healthy within 60s,
`app.py` raises loudly instead of leaving a half-working Space.

Since v0.8, `/chat` and `/chat/stream` require a logged-in account (see the
README's "Accounts & quota" section) -- visitors register/log in from the
UI itself, no separate setup needed. The account DB (`AUTH_DB_PATH`,
default `./data/users.db`) lives on the Space's ephemeral storage: it does
not persist across a Space rebuild, so registered demo accounts reset when
the Space redeploys. `JWT_SECRET` is left unset by default, which means a
random per-process secret is used -- acceptable for a demo (documented
tradeoff in `docs/SECURITY.md`), but it also means logged-in sessions don't
survive the Space restarting (free-tier Spaces spin down after
inactivity). Set `JWT_SECRET` as a Space secret if persistent sessions
across restarts matter more than that simplicity.

**Cold start:** the embedding model and cross-encoder reranker are warmed
at boot only on a fresh build (see `app.py`'s ingest branch) -- on a truly
fresh Space this means the first real chat request after the Space wakes
is fast. If `chroma_db/` somehow persists across a restart (it shouldn't;
it's gitignored and not committed, so `huggingface-cli upload` always
starts from a clean slate), warming is skipped and the very first request
lazy-loads both models, which can take 15-30s or more on free-tier CPU --
tested locally under this repo's dev-time system load and reproduced (see
git history around the accounts/security PR). The UI's httpx client uses a
60s timeout, which covers this, but a still-colder or more loaded instance
could exceed it. Not fixed further here — it's a known, bounded
cold-start cost, not a hang.

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
`[Space not yet deployed]` → once live: https://huggingface.co/spaces/YousefZahran1/bilingual-rag → Settings → Logs.

Build time on free CPU tier: ~5 minutes (most of which is downloading
`intfloat/multilingual-e5-small` once).

## Configuration

Set these as Space secrets (Settings -> Variables and secrets) if you want
real-LLM answers instead of the mock provider:

| Secret | Purpose |
|---|---|
| `LLM_PROVIDER` | `openai`, `anthropic`, `openrouter`, or `gemini` (default: `mock`) |
| `OPENAI_API_KEY` | Required if `LLM_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | Required if `LLM_PROVIDER=anthropic` |
| `OPENROUTER_API_KEY` | Required if `LLM_PROVIDER=openrouter` |
| `GEMINI_API_KEY` | Required if `LLM_PROVIDER=gemini` |

Optional, for the accounts system (see the cold-start/session note above for why these are optional rather than required):

| Secret | Purpose |
|---|---|
| `JWT_SECRET` | Set for login sessions to survive a Space restart. Unset -> a per-process random secret, fine for a demo. |
| `AUTH_DB_PATH` | Where the SQLite user DB lives (default `./data/users.db`, ephemeral). |

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
