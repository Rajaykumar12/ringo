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

Frontend: **Vite + React + TypeScript** (web)  
Backend: **FastAPI**

Fully self-hostable: no cloud vendor lock-in — documents live on local disk, analytics in a local SQLite file, sessions in Redis (or an in-memory fallback).

---

## Features

- **Y-Shaped Pipeline** — Unified processing for text and audio inputs
- **Hybrid RAG** — BM25 keyword search (40%) + semantic search (60%) via `EnsembleRetriever` (k=10 per retriever, deduplicated)
- **Document Structure Indexing** — TOC, chapter headings, and slide titles extracted at ingestion as dedicated structure chunks; injected automatically for structural queries ("what sections are in this book?")
- **Metadata-Enriched Context** — Retrieved chunks carry `[Source: file.pdf, Page N]` headers so the LLM can reason about document layout and location
- **Image-Aware Indexing** — OCR extracts text from figures, charts, and diagrams in PDFs/PPTX
- **LaTeX Normalization** — Regex-based math notation conversion before embedding
- **Streaming Toggle** — Switch between SSE token-by-token streaming and standard responses
- **Source Preview** — Inspect the exact document chunks used to generate each answer
- **Document Management** — Upload, list, and delete documents via API; persisted to a local folder (Docker volume in production)
- **Conversation Memory** — Redis-backed session history with in-memory fallback
- **Multilingual** — English, Hindi, Tamil, and Telugu
- **On-Demand TTS** — Voice generation via `edge-tts` with playback controls
- **Rate Limiting** — 10 req/min on chat endpoints, 2 req/min on uploads (slowapi)
- **Analytics** — Query, response, sources, latency logged to a local SQLite store, readable from the admin dashboard

---

## Architecture

### Backend Pipeline (4-stage Y-shape)

1. **Input Processing** — text preprocessing / Whisper audio transcription
2. **Query Refinement** — language detection, query formatting
3. **RAG Retrieval** — Hybrid BM25 + ChromaDB search; structure-chunk injection for structural queries; deduplication and metadata-enriched context assembly
4. **Response Generation** — Groq Llama-3.3-70B via LCEL chain with session history

### RAG Document Pipeline

```
PDF / PPTX / MD
       ↓
  Structure extraction (TOC / headings / slide titles) → structure chunk
       ↓
  PyMuPDF parse (per-page)
       ↓
  Image extraction → Tesseract OCR
       ↓
  LaTeX normalization (latex_utils.py)
       ↓
  Per-type chunking (PDF: 800 chars, MD: 600 chars, PPTX: 1 per slide)
       ↓
  ChromaDB (semantic, k=10) + BM25 index (k=10)
       ↓
  EnsembleRetriever (0.4 BM25 / 0.6 semantic)
       ↓
  Deduplication → structural query routing → metadata-enriched context
```

---

## Quick Start

```bash
# Full stack with Docker (recommended)
cp backend/.env.example backend/.env   # add your GROQ_API_KEY
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
npm run dev
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
| `ALLOWED_ORIGINS` | No | `localhost:5173` | Comma-separated CORS origins — set to your frontend's deployed origin(s) |
| `ALLOWED_ORIGIN_REGEX` | No | — | Regex alternative/addition to `ALLOWED_ORIGINS` |
| `ADMIN_API_KEY` | Yes | — | Required to access `/admin/*` routes |
| `LOCAL_LOGS_DB_PATH` | No | `backend/data/rag_logs.db` | Where analytics are stored (SQLite) |
| `MAX_MESSAGE_LENGTH` | No | `1000` | Max chat message characters |
| `MAX_AUDIO_SIZE_MB` | No | `10` | Max audio upload size |
| `MAX_DOCUMENT_SIZE_MB` | No | `20` | Max document upload size |

Frontend build-time variable: `VITE_API_URL` — set to your backend's URL (`frontend/.env.local` for dev, or as a Docker build arg).

---

## Project Structure

```
ringo/
├── backend/
│   ├── main.py              # FastAPI server, rate limiting, all endpoints
│   ├── pipeline.py          # Y-shaped pipeline orchestrator
│   ├── rag.py               # RAG singleton and public API
│   ├── vectorstore.py       # PyMuPDF, OCR, BM25+semantic hybrid retrieval
│   ├── latex_utils.py       # LaTeX/math notation normalization
│   ├── memory.py            # Redis / in-memory conversation history
│   ├── document_store.py    # Local filesystem document storage (upload/delete)
│   ├── rag_logger.py        # Local SQLite analytics logging
│   ├── local_store.py       # SQLite backing store for rag_logger.py / admin.py
│   ├── admin.py             # Admin dashboard read path (stats/logs)
│   ├── vision.py            # Groq vision-model image chat
│   ├── requirements.txt
│   └── documents/           # Knowledge base files (PDF/PPTX/MD)
│
├── frontend/
│   ├── src/
│   │   ├── pages/           # ChatPage, SettingsPage, AdminPage (react-router routes)
│   │   ├── components/      # chat-messages, chat-input, language-selector, documents-panel, ...
│   │   ├── hooks/           # settings, conversations, network status, i18n, theme
│   │   ├── services/api.ts  # API client with SSE streaming + document endpoints
│   │   └── theme.css        # Design tokens as CSS custom properties
│   └── vite.config.ts
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
| `POST` | `/documents/refresh` | Rebuild the vector store from the local documents folder |
| `GET` | `/admin/stats` | Aggregate analytics (requires `x-admin-key` header) |
| `GET` | `/admin/logs` | Recent query logs (requires `x-admin-key` header) |

---

## Deployment

Self-hostable on any server with Docker:

```bash
docker compose up --build -d
```

- **Documents** — stored under `backend/documents/`, bind-mounted as a volume so uploads survive container restarts
- **Vector store** — `backend/chroma_db/`, also volume-mounted
- **Analytics** — local SQLite file (`backend/data/rag_logs.db`), or point `LOCAL_LOGS_DB_PATH` at a mounted volume
- **Sessions** — Redis (bundled in `docker-compose.yml`), or an in-memory fallback if unavailable

For a production deployment behind a real domain, set `ALLOWED_ORIGINS`/`ALLOWED_ORIGIN_REGEX` on the backend to your frontend's origin, and build the frontend with `VITE_API_URL` pointing at your backend (e.g. `docker build --build-arg VITE_API_URL=https://api.yourdomain.com ./frontend`). Put both containers behind a reverse proxy (nginx/Caddy/Traefik) for TLS.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
