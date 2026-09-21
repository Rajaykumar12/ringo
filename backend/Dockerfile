FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

COPY . .

# Model caches. HOME is /app (useradd -d), so Whisper and HuggingFace both want to
# write under /app/.cache — which the root-owned source tree below would deny,
# and the backend then dies at startup downloading base.en. Pointed at explicit
# paths rather than relying on HOME so the writable set stays obvious.
ENV HOME=/app \
    XDG_CACHE_HOME=/app/.cache \
    HF_HOME=/app/.cache/huggingface

# Source stays root-owned and read-only to the runtime user: a write primitive in
# the app should not become persistent code execution. Only the directories the
# app genuinely writes to are handed over.
RUN mkdir -p /app/documents /app/chroma_db /app/data /app/embedding_cache /app/.cache \
    && chown -R appuser:appuser /app/documents /app/chroma_db /app/data /app/embedding_cache /app/.cache

USER appuser

EXPOSE 8000

CMD ["python", "main.py"]
