FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Remove local documents — they will be synced from Azure Blob Storage at runtime
RUN rm -rf /app/documents && mkdir -p /app/documents

# Ensure chroma_db directory exists for volume mount
RUN mkdir -p /app/chroma_db

EXPOSE 8000

CMD ["python", "main.py"]