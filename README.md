# Multilingual AI Chat System

> A fully open-source, cross-platform AI chat application supporting both text and voice, built with modern, high-performance open-source technologies.

---

## Overview

This project delivers a robust AI chat experience with multilingual support, leveraging:

- **Groq (Llama 3.3-70b)** for blazing-fast, free text generation
- **HuggingFace** (`all-MiniLM-L6-v2`) for local, unlimited semantic embeddings
- **ChromaDB** for persistent, local vector storage
- **OpenAI Whisper** for accurate, local audio transcription
- **langdetect** for local language detection
- **edge-tts** for high-quality TTS generation
- **Redis** for persistent conversation memory

Frontend: **Expo (React Native)** (Web, iOS, Android)  
Backend: **FastAPI**

---

## Features

- **Y-Shaped Pipeline**: Unified processing for both text and audio inputs
- **Retrieval Augmented Generation (RAG)**: Professional-grade RAG using ChromaDB
- **Conversation Memory**: Remembers chat context using Redis session storage
- **Real-time Streaming**: Token-by-token SSE (Server-Sent Events) streaming to the UI
- **Source Attribution**: Transparently shows which PDF/PPTX documents were used to generate answers
- **Multilingual**: Supports English, Hindi, Tamil, and Telugu natively
- **On-Demand TTS**: High-quality voice generation using `edge-tts`
- **Smart Chunking**: Processes PDFs, Markdowns, and PowerPoint presentations (1 chunk per slide)
- **Analytics Ready**: Automatically logs inference latency, sources, and queries to Azure Table Storage

---

## Architecture

The backend implements a modular, 4-stage Y-shaped pipeline:

1. **Input Processing**
    - **Text**: Preprocessing and cleaning
    - **Audio**: Transcription via local Whisper model
2. **Query Refinement**
    - Language detection and unified query formatting
3. **RAG Retrieval**
    - Semantic search using HuggingFace embeddings and ChromaDB (with score thresholds)
4. **Response Generation**
    - Final answer generation using Groq API via LCEL chains
5. **Audio Output**: On-demand TTS generation with caching strategy

---

## Quick Start (Docker)

Run the entire stack (Frontend + Backend + Redis) with a single command:

```bash
# Start all services
docker compose up --build

# Backend API: http://localhost:8000
# Frontend App: http://localhost:8081
```

---

## Manual Setup

### 1. Backend

```bash
cd backend
# Install dependencies (Python 3.10+)
pip install -r requirements.txt

# Create .env file with your environment variables
cat << EOF > .env
GROQ_API_KEY=your_groq_api_key_here
REDIS_URL=redis://localhost:6379
EOF

# Start the FastAPI server
python main.py
```

### 2. Frontend

```bash
cd frontend
# Install dependencies
npm install

# Start the Expo app
npm start
```

---

## Environment Variables

| Variable | Description | Required | Default |
|---|---|---|---|
| `GROQ_API_KEY` | API Key for Llama 3 on Groq | Yes | — |
| `REDIS_URL` | Redis connection string for session history | No | `redis://localhost:6379` (Falls back to in-memory if invalid) |
| `AZURE_STORAGE_CONNECTION_STRING`| Syncs documents from blob storage & logs to Table Storage | No | Uses local `documents/` folder & skips logging |

---

## Project Structure

```
ADK/
├── backend/
│   ├── main.py              # FastAPI server & streaming routes
│   ├── pipeline.py          # Y-shaped pipeline orchestrator
│   ├── rag.py               # RAG Public API & Singleton
│   ├── vectorstore.py       # ChromaDB setup, chunking, & LCEL chain
│   ├── memory.py            # Redis / In-memory conversation history
│   ├── blob_sync.py         # Azure Blob Storage document synchronization
│   ├── rag_logger.py        # Azure Table Storage analytics logging
│   ├── requirements.txt     # Python dependencies
│   └── documents/           # Knowledge base files (PDF/PPTX/MD)
│
├── frontend/
│   ├── app/
│   │   └── index.tsx        # Main chat interface with Streaming
│   ├── components/
│   │   ├── chat-messages.tsx # Message list display & source tags
│   │   └── ...
│   └── services/
│       └── api.ts           # Axios client configured for SSE and Long-polling
└── docker-compose.yml       # Orchestrates App, Backend, and Redis
```

---

## Deployment

This project is optimized for **Azure Container Apps**:
- **Azure Blob Storage** for dynamic document management (`documents` container)
- **Azure Table Storage** for RAG analytics (`raglogs` table)
- **Azure Cache for Redis** for persistent, scalable session memory
- **Azure Container Registry** for secure image hosting

The backend, frontend, and database layers scale independently, ensuring reliability under load.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
