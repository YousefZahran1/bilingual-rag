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
    VECTOR_DIR=/data/chroma_db

EXPOSE 8000

# Ingest the sample corpus once at build, so the image works out of the box.
RUN python -m src.rag.ingest data/sample

CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
