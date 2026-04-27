"""Hugging Face Spaces entry point.

Spaces auto-detects this file (must be in repo root, named `app.py` for Gradio
or `streamlit_app.py` for Streamlit). We use Streamlit and shim the import
path to make `from src...` work when Spaces runs the file from repo root.

To deploy:
  1. `pip install huggingface_hub`
  2. `huggingface-cli login`
  3. `huggingface-cli upload --repo-type=space YousefZahran1/bilingual-rag . .`
     (after creating the Space at https://huggingface.co/spaces with SDK=streamlit)
  4. Set Space env var LLM_PROVIDER=mock (or wire your own key as a Space secret)
  5. Wait ~3 min for build; live URL appears
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# 1) Make sure the indexed corpus is built — Spaces starts from a clean slate
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

if not (HERE / "chroma_db").exists():
    subprocess.run(
        [sys.executable, "-m", "src.rag.ingest", "data/sample"],
        check=True,
    )

# 2) Then start Streamlit
os.environ.setdefault("LLM_PROVIDER", "mock")
os.execvp("streamlit", [
    "streamlit", "run", "src/ui/app.py",
    "--server.address", "0.0.0.0",
    "--server.port", "7860",  # HF Spaces standard port
    "--server.headless", "true",
])
