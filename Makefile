.PHONY: install ingest api ui eval test docker docker-up docker-down deploy-hf

PYTHON ?= python3
PYTHONPATH := .

install:
	$(PYTHON) -m venv .venv
	. .venv/bin/activate && pip install -r requirements-dev.txt

ingest:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m src.rag.ingest data/sample

api:
	PYTHONPATH=$(PYTHONPATH) uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000

ui:
	PYTHONPATH=$(PYTHONPATH) streamlit run src/ui/app.py

eval:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m eval.run_eval data/sample/eval_questions.jsonl --top-k 4

test:
	PYTHONPATH=$(PYTHONPATH) pytest -q

docker:
	docker build -f deploy/Dockerfile -t bilingual-rag:0.1.0 .

docker-up:
	docker compose -f deploy/docker-compose.yml up -d

docker-down:
	docker compose -f deploy/docker-compose.yml down

# --- Hugging Face Spaces deploy ---
HF_USER ?= YousefZahran1
HF_SPACE ?= bilingual-rag

deploy-hf:
	@echo "1. Create the Space first at https://huggingface.co/new-space (SDK=Streamlit, hardware=CPU basic)"
	@echo "2. Then run: huggingface-cli upload --repo-type=space $(HF_USER)/$(HF_SPACE) . ."
	@echo "3. Set Space secret OPENAI_API_KEY (or ANTHROPIC_API_KEY) if you want a real LLM"
