FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Documents folder is normally bind-mounted as a volume at runtime (see docker-compose.yml)
RUN mkdir -p /app/documents

# Ensure chroma_db directory exists for volume mount
RUN mkdir -p /app/chroma_db

RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["python", "main.py"]