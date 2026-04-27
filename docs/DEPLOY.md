# Deployment

Three deployable surfaces, ranked by friction.

## 1. Hugging Face Spaces (recommended for the demo)

**Friction:** very low. **Cost:** free (CPU basic).
**Why:** the Space gets a public URL like `https://huggingface.co/spaces/YousefZahran1/bilingual-rag` — perfect to drop into a CV bullet.

```bash
# one-time setup
pip install huggingface_hub
huggingface-cli login   # paste your HF token

# create the Space at https://huggingface.co/new-space
#   SDK = Streamlit
#   hardware = CPU basic (free)
#   visibility = public

# upload everything
huggingface-cli upload --repo-type=space YousefZahran1/bilingual-rag . .

# Spaces auto-detects app.py in repo root and runs it
```

The `app.py` in repo root is the Spaces entry point. It re-runs the corpus ingest on first cold-start (Spaces gives you ephemeral filesystem) then launches Streamlit on port 7860.

## 2. Fly.io (for a hosted FastAPI demo with persistent vector store)

**Friction:** low. **Cost:** free for the smallest VM with persistent volume; ~$2/mo if you scale up.

```bash
flyctl launch --no-deploy           # creates fly.toml
flyctl volumes create chroma_data --size 1
flyctl secrets set LLM_PROVIDER=mock
flyctl deploy
```

`fly.toml` should mount the volume at `/data/chroma_db` and set `VECTOR_DIR=/data/chroma_db`.

## 3. Local Docker

**Friction:** none.
```bash
make docker-up
# API at http://localhost:8000  •  UI at http://localhost:8501
```

## Production checklist before you point a real audience at it

- [ ] `LLM_PROVIDER` set to `openai` or `anthropic` with a real key (in Space secrets, not committed)
- [ ] Rate limit on `/chat` (FastAPI middleware: 30 req / IP / minute is generous)
- [ ] Logs with `loguru` going to stdout (HF Spaces captures these)
- [ ] Optional: pre-warm the embedding model in the Dockerfile to skip 30s cold-start
