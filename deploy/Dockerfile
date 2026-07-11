FROM python:3.11-slim

WORKDIR /app

# System deps for sentence-transformers (libgomp), chroma (sqlite is bundled)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY data/ ./data/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    VECTOR_DIR=/data/chroma_db \
    INDEX_DIR=/data/index_data

EXPOSE 8000

# Ingest the sample corpus once at build, so the image works out of the box.
# This also builds the BM25 sidecar (src/rag/ingest.py writes both).
RUN python -m src.rag.ingest data/sample

# Warm the cross-encoder re-ranker at build time. Reranking only happens at
# query time (unlike the embedding model, which ingest.py above already
# exercises) -- without this it would silently lazy-download on the first
# live /chat request in production, which is bad for a demo and a hard
# failure if the deployed environment has restricted egress.
RUN python -c "from src.rag.reranker import CrossEncoderReranker; CrossEncoderReranker().warm()"

CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
