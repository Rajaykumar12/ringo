# Multilingual AI Chat System

> A fully open-source, cross-platform AI chat application supporting text and voice, built with modern high-performance technologies and a warm, polished mobile UI.

---

## Overview

This project delivers a robust AI chat experience with multilingual support, leveraging:

- **Groq (Llama 3.3-70b)** for fast text generation
- **HuggingFace** (`all-MiniLM-L6-v2`) for local semantic embeddings
- **ChromaDB** for persistent vector storage
- **PyMuPDF** for high-fidelity PDF parsing with per-page chunking
- **Tesseract OCR** for extracting text from embedded images in documents
- **BM25 + Semantic hybrid search** via `EnsembleRetriever`
- **OpenAI Whisper** for local audio transcription
- **langdetect** for language detection
- **edge-tts** for high-quality TTS generation
- **Redis** for persistent conversation memory

Frontend: **Expo (React Native)** — Web, iOS, Android  
Backend: **FastAPI**

---

## Features

- **Y-Shaped Pipeline** — Unified processing for text and audio inputs
- **Hybrid RAG** — BM25 keyword search (40%) + semantic search (60%) via `EnsembleRetriever`
- **Image-Aware Indexing** — OCR extracts text from figures, charts, and diagrams in PDFs/PPTX
- **LaTeX Normalization** — Regex-based math notation conversion before embedding
- **Streaming Toggle** — Switch between SSE token-by-token streaming and standard responses
- **Source Preview** — Inspect the exact document chunks used to generate each answer
- **Document Management** — Upload, list, and delete documents via API; persisted to Azure Blob or local folder
- **Conversation Memory** — Redis-backed session history with in-memory fallback
- **Multilingual** — English, Hindi, Tamil, and Telugu
- **On-Demand TTS** — Voice generation via `edge-tts` with playback controls
- **Rate Limiting** — 10 req/min on chat endpoints, 2 req/min on uploads (slowapi)
- **Analytics** — Query, response, sources, latency logged to Azure Table Storage

---

## Architecture

### Backend Pipeline (4-stage Y-shape)

1. **Input Processing** — text preprocessing / Whisper audio transcription
2. **Query Refinement** — language detection, query formatting
3. **RAG Retrieval** — BM25 + ChromaDB hybrid search with PyMuPDF/OCR-indexed chunks
4. **Response Generation** — Groq Llama-3.3-70B via LCEL chain with session history

### RAG Document Pipeline

```
PDF / PPTX / MD
       ↓
  PyMuPDF parse (per-page)
       ↓
  Image extraction → Tesseract OCR
       ↓
  LaTeX normalization (latex_utils.py)
       ↓
  ChromaDB (semantic) + BM25 index
       ↓
  EnsembleRetriever (0.4 BM25 / 0.6 semantic)
```

---

## Quick Start

```bash
# Full stack with Docker (recommended)
docker compose up --build
# Backend: http://localhost:8000
# Frontend: http://localhost:8081

# Backend only
cd backend
pip install -r requirements.txt
# Add GROQ_API_KEY to .env
python main.py

# Frontend only
cd frontend
npm install
npm start
```

### System dependencies (for OCR)

```bash
# Fedora/RHEL
sudo dnf install tesseract tesseract-langpack-eng

# Ubuntu/Debian
sudo apt install tesseract-ocr tesseract-ocr-eng
```

OCR is optional — the system falls back gracefully if Tesseract is not installed.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | Yes | — | Groq API key for Llama 3.3-70B |
| `REDIS_URL` | No | `redis://localhost:6379` | Session memory (falls back to in-memory) |
| `AZURE_STORAGE_CONNECTION_STRING` | No | — | Enables Azure Blob document sync + Table Storage logging |
| `AZURE_STORAGE_CONTAINER_NAME` | No | `documents` | Blob container name |
| `ALLOWED_ORIGINS` | No | `localhost:8081,8080,19006` | Comma-separated CORS origins |
| `MAX_MESSAGE_LENGTH` | No | `1000` | Max chat message characters |
| `MAX_AUDIO_SIZE_MB` | No | `10` | Max audio upload size |
| `MAX_DOCUMENT_SIZE_MB` | No | `20` | Max document upload size |

---

## Project Structure

```
ADK/
├── backend/
│   ├── main.py              # FastAPI server, rate limiting, all endpoints
│   ├── pipeline.py          # Y-shaped pipeline orchestrator
│   ├── rag.py               # RAG singleton and public API
│   ├── vectorstore.py       # PyMuPDF, OCR, BM25+semantic hybrid retrieval
│   ├── latex_utils.py       # LaTeX/math notation normalization
│   ├── memory.py            # Redis / in-memory conversation history
│   ├── blob_sync.py         # Azure Blob Storage sync, upload, delete
│   ├── rag_logger.py        # Azure Table Storage analytics logging
│   ├── requirements.txt
│   └── documents/           # Knowledge base files (PDF/PPTX/MD)
│
├── frontend/
│   ├── app/
│   │   ├── index.tsx        # Main chat screen (streaming toggle, document panel)
│   │   └── _layout.tsx      # Root layout and error boundary
│   ├── components/
│   │   ├── chat-messages.tsx     # Message list, source tags, source preview modal
│   │   ├── chat-input.tsx        # Animated send/mic/stop input bar
│   │   ├── language-selector.tsx # Language picker with flag + native name
│   │   └── documents-panel.tsx   # Document upload/list/delete panel
│   ├── constants/
│   │   └── theme.ts         # Design tokens: Colors, Radii, Shadows
│   └── services/
│       └── api.ts           # API client with SSE streaming + document endpoints
│
└── docker-compose.yml
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Vector store status, chunk count, Redis status |
| `POST` | `/chat/text` | Text chat (supports `stream=true`) |
| `POST` | `/chat/audio` | Audio chat with Whisper transcription |
| `POST` | `/tts/generate` | On-demand TTS generation |
| `GET` | `/documents/list` | List indexed documents with chunk counts |
| `POST` | `/documents/upload` | Upload and index a document |
| `DELETE` | `/documents/{filename}` | Delete a document and rebuild index |
| `GET` | `/documents/chunks` | Fetch chunks for a document (with optional query ranking) |
| `POST` | `/documents/refresh` | Re-sync from Azure Blob and rebuild vector store |

---

## Deployment

Optimized for **Azure Container Apps**:

- **Azure Blob Storage** — document persistence (`documents` container); local folder fallback for dev
- **Azure Table Storage** — RAG analytics logging (`raglogs` table)
- **Azure Cache for Redis** — scalable session memory
- **Azure Container Registry** — image hosting

Set `AZURE_STORAGE_CONNECTION_STRING` in the Container App's environment variables to enable all Azure features. Without it, the app runs fully locally.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
