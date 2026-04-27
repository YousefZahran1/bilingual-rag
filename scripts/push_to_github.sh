#!/usr/bin/env bash
# Push this project to GitHub with a progressive (multi-commit) history.
# Run from inside the project root after replacing GITHUB_USER and confirming gh / git are authenticated.
#
# Prereqs:
#   - git installed
#   - GitHub auth: either `gh auth login` OR a personal access token in your environment
#   - You created the repo on github.com first (or use `gh repo create`)

set -euo pipefail

GITHUB_USER="YousefZahran1"
REPO_NAME="bilingual-rag-assistant"
DESCRIPTION="Bilingual Arabic-English RAG with multilingual embeddings, FastAPI, Streamlit, and a real eval harness."

# 1. init repo
if [ ! -d ".git" ]; then
  git init -q
  git checkout -b main
fi
git config user.email "youssefzahran.y@gmail.com"
git config user.name  "Youssef Ibrahim"

# 2. progressive commits — each touches a distinct slice
git add README.md LICENSE .gitignore .env.example requirements.txt requirements-dev.txt
git commit -q -m "Initial scaffold: README, LICENSE, deps" || true

git add src/rag/__init__.py src/rag/lang.py src/rag/chunker.py
git commit -q -m "Add language detector and language-aware chunker" || true

git add src/rag/store.py src/rag/ingest.py
git commit -q -m "Add Chroma vector store wrapper and ingest CLI" || true

git add src/rag/generator.py src/rag/providers/
git commit -q -m "Add pluggable answer generator (mock / OpenAI / Anthropic)" || true

git add src/api/
git commit -q -m "Add FastAPI service with /chat and citation responses" || true

git add src/ui/
git commit -q -m "Add Streamlit UI with bilingual toggle and citations" || true

git add data/sample/
git commit -q -m "Add sample bilingual corpus and eval question set" || true

git add tests/
git commit -q -m "Add unit tests for lang detection, chunker, generator (mock)" || true

git add eval/ docs/
git commit -q -m "Add evaluation harness and docs (EVAL, ROADMAP)" || true

git add deploy/ .github/workflows/ci.yml
git commit -q -m "Add Docker, docker-compose, and GitHub Actions CI" || true

# 3. create remote (using gh) and push
if command -v gh >/dev/null 2>&1; then
  gh repo create "$GITHUB_USER/$REPO_NAME" --public --description "$DESCRIPTION" --source=. --remote=origin --push
else
  echo "gh not found. Add the remote and push manually:"
  echo "  git remote add origin https://github.com/$GITHUB_USER/$REPO_NAME.git"
  echo "  git push -u origin main"
fi

echo "Done."
