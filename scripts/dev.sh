#!/usr/bin/env bash
# Local development helper.
set -euo pipefail
case "${1:-help}" in
  install)
    python -m venv .venv
    . .venv/bin/activate && pip install -r requirements-dev.txt
    ;;
  ingest)
    PYTHONPATH=. python -m src.rag.ingest data/sample
    ;;
  api)
    PYTHONPATH=. uvicorn src.api.app:app --reload
    ;;
  ui)
    PYTHONPATH=. streamlit run src/ui/app.py
    ;;
  eval)
    PYTHONPATH=. python -m eval.run_eval data/sample/eval_questions.jsonl --top-k 4
    ;;
  test)
    PYTHONPATH=. pytest -q
    ;;
  *)
    echo "Usage: $0 {install|ingest|api|ui|eval|test}"
    ;;
esac
