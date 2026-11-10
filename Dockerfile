FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/home/app/.cache/huggingface \
    TC_EMBEDDING_BACKEND=sentence-transformers

WORKDIR /app
RUN useradd -m -u 10001 app

# CPU-only torch keeps the image far smaller than the default CUDA build
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[api,ml,llm,zendesk]"

USER app

# Bake the embedding model into the image so containers start fast and work offline
ARG TC_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${TC_EMBEDDING_MODEL}')"

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)"

# $PORT is honoured on platforms like Render / Cloud Run / Railway
CMD ["sh", "-c", "uvicorn ticketsorter.api:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
