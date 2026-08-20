"""Hugging Face Spaces entry point.

Spaces auto-detects this file (must be in repo root, named `app.py` for Gradio
or `streamlit_app.py` for Streamlit). We use Streamlit and shim the import
path to make `from src...` work when Spaces runs the file from repo root.

Spaces exposes exactly one public port, but this app is two processes (the
FastAPI backend the Streamlit UI talks to over HTTP, same as local dev) --
so the backend is started here as a background subprocess bound to
127.0.0.1 only (never exposed publicly; the container's single public port
stays Streamlit's), and this process execs into Streamlit once the backend
answers /health.

To deploy:
  1. `pip install huggingface_hub`
  2. `huggingface-cli login`
  3. `huggingface-cli upload --repo-type=space YousefZahran1/bilingual-rag . .`
     (after creating the Space at https://huggingface.co/spaces with SDK=streamlit)
  4. Set Space env vars (see docs/DEMO.md's Configuration section) -- at
     minimum nothing is required, mock provider + a per-process dev JWT
     secret both work out of the box for a demo.
  5. Wait ~3-5 min for build; live URL appears
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

# 1) Make sure the indexed corpus is built — Spaces starts from a clean slate
if not (HERE / "chroma_db").exists():
    subprocess.run(
        [sys.executable, "-m", "src.rag.ingest", "data/sample"],
        check=True,
    )
    # Warm the cross-encoder re-ranker too, same reasoning as the Dockerfile:
    # reranking only happens at query time, so without this it would
    # lazy-download on the first live chat request instead of at boot.
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from src.rag.reranker import CrossEncoderReranker; CrossEncoderReranker().warm()",
        ],
        check=True,
    )

os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("AUTH_DB_PATH", "./data/users.db")

# 2) Start the FastAPI backend in the background, localhost-only -- the
# Streamlit UI (src/ui/app.py) is the only thing that talks to it.
api_process = subprocess.Popen(
    [
        sys.executable, "-m", "uvicorn", "src.api.app:app",
        "--host", "127.0.0.1", "--port", "8000",
    ],
)
os.environ.setdefault("API_URL", "http://127.0.0.1:8000")

_deadline = time.monotonic() + 60
while time.monotonic() < _deadline:
    if api_process.poll() is not None:
        raise RuntimeError(f"FastAPI backend exited early with code {api_process.returncode}")
    try:
        urllib.request.urlopen(f"{os.environ['API_URL']}/health", timeout=2)
        break
    except (urllib.error.URLError, TimeoutError):
        time.sleep(1)
else:
    raise RuntimeError("FastAPI backend did not become healthy within 60s")

# 3) Then start Streamlit as the foreground process (what Spaces supervises).
# Invoked via `python -m streamlit`, not the bare `streamlit` console
# script, so this doesn't depend on that shim being on PATH.
os.execv(sys.executable, [
    sys.executable, "-m", "streamlit", "run", "src/ui/app.py",
    "--server.address", "0.0.0.0",
    "--server.port", "7860",  # HF Spaces standard port
    "--server.headless", "true",
])
