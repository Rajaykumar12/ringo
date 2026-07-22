# AI Chat System

> A fully open-source, cross-platform AI chat application supporting text, voice, and images, built with modern high-performance technologies and a warm, polished UI.

---

## Overview

This project delivers a robust AI chat experience, leveraging:

- **Groq (Llama 3.3-70b / 3.1-8b-instant)** for fast text generation, with automatic model tiering
- **Groq vision model** for image-aware chat
- **HuggingFace** (`all-MiniLM-L6-v2`) for local semantic embeddings
- **ChromaDB** for persistent vector storage
- **PyMuPDF** for high-fidelity PDF parsing with per-page chunking
- **Tesseract OCR** for extracting text from embedded images in documents
- **BM25 + Semantic hybrid search** via `EnsembleRetriever`, refined by a **cross-encoder reranker**
- **OpenAI Whisper** for local audio transcription
- **edge-tts** for high-quality TTS generation
- **Redis** for persistent conversation memory and response caching

Frontend: **Vite + React + TypeScript** (web)  
Backend: **FastAPI**

Fully self-hostable: no cloud vendor lock-in — documents, images, and analytics live on local disk/SQLite, sessions in Redis (or an in-memory fallback).

---

## Features

- **Y-Shaped Pipeline** — Unified processing for text and audio inputs
- **Hybrid RAG with Reranking** — BM25 keyword search (40%) + semantic search (60%) via `EnsembleRetriever` (k=30 per retriever), merged and reranked by a cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) down to the top 10 most relevant chunks
- **Document Structure Indexing** — TOC, chapter headings, and slide titles extracted at ingestion as dedicated structure chunks; injected automatically for structural queries ("what sections are in this book?")
- **Metadata-Enriched Context** — Retrieved chunks carry `[Source: file.pdf, Page N]` headers so the LLM can reason about document layout and location
- **Image-Aware Indexing** — OCR extracts text from figures, charts, and diagrams in PDFs/PPTX; the images themselves are also extracted and persisted, so they can be shown back in the chat UI
- **Image Chat** — Upload an image directly for vision-model Q&A; follow-up text messages that reference "that image/picture/photo" are automatically routed back to the vision model using the session's last upload
- **LaTeX Normalization** — Regex-based math notation conversion before embedding
- **Model Tiering** — Short, simple, or early-conversation queries are automatically routed to a faster Groq model; longer or structural queries use the full model
- **Response Caching** — Exact-match Redis cache for first-turn queries, avoiding redundant LLM calls
- **Streaming Toggle** — Switch between SSE token-by-token streaming and standard responses
- **Source Preview** — Inspect the exact document chunks used to generate each answer
- **Document Management** — Upload, list, and delete documents via API; persisted to a local folder (Docker volume in production)
- **Conversation Memory** — Redis-backed session history with in-memory fallback
- **On-Demand TTS** — Voice generation via `edge-tts` with playback controls
- **Rate Limiting** — Per-endpoint limits via `slowapi` (see [API Endpoints](#api-endpoints))
- **Analytics** — Query, response, sources, latency, and model tier logged to a local SQLite store, readable from the admin dashboard

---

## Architecture

### Backend Pipeline (4-stage Y-shape)

1. **Input Processing** — text preprocessing / Whisper audio transcription / direct image input
2. **Query Refinement** — query formatting, model-tier selection (fast vs. default Groq model)
3. **RAG Retrieval** — Hybrid BM25 + ChromaDB search, cross-encoder reranking, structure-chunk injection for structural queries; deduplication and metadata-enriched context assembly
4. **Response Generation** — Groq LLM (tiered) via LCEL chain with session history, backed by a first-turn exact-match response cache

### RAG Document Pipeline

```
PDF / PPTX / MD
       ↓
  Structure extraction (TOC / headings / slide titles) → structure chunk
       ↓
  PyMuPDF parse (per-page)
       ↓
  Image extraction → Tesseract OCR + persisted to disk (image_ids on chunk metadata)
       ↓
  LaTeX normalization (latex_utils.py)
       ↓
  Per-type chunking (PDF: 800 chars, MD: 600 chars, PPTX: 1 per slide)
       ↓
  ChromaDB (semantic, k=30) + BM25 index (k=30)
       ↓
  EnsembleRetriever (0.4 BM25 / 0.6 semantic)
       ↓
  Cross-encoder rerank → top 10
       ↓
  Deduplication → structural query routing → metadata-enriched context (+ up to 4 linked images)
```

### Image Chat Path

Image chat bypasses the RAG pipeline entirely:

- `POST /chat/image` sends an uploaded image straight to a vision-capable Groq model along with the user's question, persists the image to disk, and links it to the session.
- A later **text-only** message referencing "that image/picture/photo/pic/screenshot" is detected heuristically and automatically re-routed to the vision model using the session's most recently uploaded image, instead of the normal RAG chain.
- Images surfaced from RAG document retrieval (extracted during ingestion) and images uploaded via chat are served through the same `GET /images/{image_id}` endpoint.

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
| `GROQ_API_KEY` | Yes | — | Groq API key for text and vision models |
| `VISION_MODEL` | No | `qwen/qwen3.6-27b` | Groq model used for image chat and image follow-ups |
| `REDIS_URL` | No | `redis://localhost:6379` | Session memory and response cache (falls back to in-memory) |
| `ALLOWED_ORIGINS` | No | `localhost:5173` | Comma-separated CORS origins — set to your frontend's deployed origin(s) |
| `ALLOWED_ORIGIN_REGEX` | No | — | Regex alternative/addition to `ALLOWED_ORIGINS` |
| `ADMIN_API_KEY` | No | — | Enables `/admin/*` routes (`x-admin-key` header); if unset, those routes return `503` rather than failing startup |
| `LOCAL_LOGS_DB_PATH` | No | `backend/data/rag_logs.db` | Where analytics are stored (SQLite) |
| `IMAGES_DIR` | No | `backend/data/images/` | Where persisted images (from RAG documents and chat uploads) are stored |
| `IMAGE_LINKS_DB_PATH` | No | `backend/data/image_links.db` | SQLite DB linking uploaded images to sessions (powers "that image" follow-ups) |
| `RERANK_MODEL` | No | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Cross-encoder used to rerank hybrid retrieval results |
| `RERANK_TOP_N` | No | `10` | Number of chunks kept after reranking |
| `RESPONSE_CACHE_TTL_SECONDS` | No | `3600` | TTL for the first-turn exact-match response cache (Redis) |
| `ENABLE_RAG_EVAL` | No | `false` | Enables LLM-as-judge scoring of RAG responses |
| `MAX_MESSAGE_LENGTH` | No | `1000` | Max chat message characters |
| `MAX_AUDIO_SIZE_MB` | No | `10` | Max audio upload size |
| `MAX_DOCUMENT_SIZE_MB` | No | `20` | Max document upload size |
| `MAX_IMAGE_SIZE_MB` | No | `8` | Max image upload size for `/chat/image` |
| `MAX_TTS_LENGTH` | No | `5000` | Max characters accepted by `/tts/generate` |
| `LOG_LEVEL` | No | `INFO` | Backend log level |

Frontend build-time variable: `VITE_API_URL` — set to your backend's URL (`frontend/.env.local` for dev, or as a Docker build arg).

---

## Project Structure

```
ringo/
├── backend/
│   ├── main.py              # FastAPI server, rate limiting, all endpoints
│   ├── pipeline.py          # Y-shaped pipeline orchestrator
│   ├── rag.py               # RAG singleton, reranking, response cache, model tiering
│   ├── vectorstore.py       # PyMuPDF, OCR, image extraction, BM25+semantic hybrid retrieval
│   ├── latex_utils.py       # LaTeX/math notation normalization
│   ├── memory.py            # Redis / in-memory conversation history
│   ├── document_store.py    # Local filesystem document storage (upload/delete)
│   ├── image_store.py       # Local filesystem image storage (data/images/)
│   ├── image_links.py       # SQLite session→image linking, powers image follow-ups
│   ├── response_cache.py    # Redis-backed first-turn exact-match response cache
│   ├── rag_logger.py        # Local SQLite analytics logging
│   ├── local_store.py       # SQLite backing store for rag_logger.py / admin.py
│   ├── admin.py             # Admin dashboard read path (stats/logs)
│   ├── vision.py            # Groq vision model — backs /chat/image and image follow-ups
│   ├── eval.py               # LLM-as-judge RAG response evaluation (ENABLE_RAG_EVAL)
│   ├── requirements.txt
│   ├── documents/           # Knowledge base files (PDF/PPTX/MD)
│   └── data/                 # SQLite DBs (rag_logs.db, image_links.db) + images/
│
├── frontend/
│   ├── src/
│   │   ├── pages/           # ChatPage, SettingsPage, AdminPage (react-router routes)
│   │   ├── components/      # chat-messages, chat-input, documents-panel, conversations-panel, ...
│   │   ├── hooks/           # settings, conversations, network status, theme
│   │   ├── services/api.ts  # API client with SSE streaming, document, and image endpoints
│   │   └── theme.css        # Design tokens as CSS custom properties
│   └── vite.config.ts
│
└── docker-compose.yml
```

---

## API Endpoints

| Method | Path | Rate limit | Description |
|---|---|---|---|
| `GET` | `/health` | — | Vector store status, chunk count, Redis status, Groq reachability |
| `POST` | `/chat/text` | 10/min | Text chat (supports `stream=true`); auto-routes to vision model on image follow-up references |
| `POST` | `/chat/audio` | 10/min | Audio chat with Whisper transcription |
| `POST` | `/chat/image` | 10/min | Image + question chat via the vision model, bypassing RAG |
| `GET` | `/images/{image_id}` | — | Serve a persisted image (extracted from a RAG document or uploaded via chat) |
| `POST` | `/tts/generate` | 20/min | On-demand TTS generation |
| `GET` | `/documents/list` | — | List indexed documents with chunk counts |
| `POST` | `/documents/upload` | 2/min | Upload and index a document |
| `DELETE` | `/documents/{filename}` | — | Delete a document, its linked images, and rebuild the index |
| `GET` | `/documents/chunks` | — | Fetch chunks for a document (with optional query ranking) |
| `POST` | `/documents/refresh` | 5/min | Rebuild the vector store from the local documents folder |
| `POST` | `/feedback` | 30/min | Submit feedback on a response |
| `GET` | `/admin/stats` | — | Aggregate analytics (requires `x-admin-key` header) |
| `GET` | `/admin/logs` | — | Recent query logs (requires `x-admin-key` header) |

---

## Deployment

Self-hostable on any server with Docker:

```bash
docker compose up --build -d
```

- **Documents** — stored under `backend/documents/`, bind-mounted as a volume so uploads survive container restarts
- **Vector store** — `backend/chroma_db/`, also volume-mounted
- **Analytics & images** — local SQLite files and persisted images under `backend/data/` (`rag_logs.db`, `image_links.db`, `images/`). This directory is **not** currently volume-mounted in `docker-compose.yml`, so it will not survive container recreation as shipped — mount it alongside `documents/` and `chroma_db/` for production use, or point `LOCAL_LOGS_DB_PATH`/`IMAGES_DIR`/`IMAGE_LINKS_DB_PATH` at a mounted volume
- **Sessions** — Redis (bundled in `docker-compose.yml`), or an in-memory fallback if unavailable

For a production deployment behind a real domain, set `ALLOWED_ORIGINS`/`ALLOWED_ORIGIN_REGEX` on the backend to your frontend's origin, and build the frontend with `VITE_API_URL` pointing at your backend (e.g. `docker build --build-arg VITE_API_URL=https://api.yourdomain.com ./frontend`). Put both containers behind a reverse proxy (nginx/Caddy/Traefik) for TLS.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
