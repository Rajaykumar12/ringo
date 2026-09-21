# AI Chat System

> A fully open-source, cross-platform AI chat application supporting text, voice, and images, built with modern high-performance technologies and a warm, polished UI.

---

## Overview

This project delivers a robust AI chat experience, leveraging:

- **Groq (Llama 3.3-70b / 3.1-8b-instant)** for fast text generation, with automatic model tiering
- **Groq vision model** for image-aware chat
- **HuggingFace** (`all-MiniLM-L6-v2`) for local semantic embeddings
- **ChromaDB** for persistent vector storage
- **PyMuPDF / python-docx / BeautifulSoup / openpyxl** for parsing PDF, PPTX, DOCX, HTML, CSV, and XLSX documents
- **Tesseract OCR** for extracting text from embedded images in documents
- **BM25 + Semantic hybrid search** via `EnsembleRetriever`, with LLM-generated query rewriting to widen recall, refined by a **cross-encoder reranker**
- **OpenAI Whisper** for local audio transcription
- **edge-tts** for high-quality TTS generation
- **Redis** for persistent conversation memory and response caching

Frontend: **Vite + React + TypeScript** (web)  
Backend: **FastAPI**

Fully self-hostable: no cloud vendor lock-in — documents, images, and analytics live on local disk/SQLite, sessions in Redis (or an in-memory fallback).

---

## Features

- **Y-Shaped Pipeline** — Unified processing for text and audio inputs
- **Query Rewriting** — Vague or multi-part queries are expanded into alternate phrasings (fast-tier Groq model) before retrieval, widening hybrid-search recall; skipped for structural/short queries (`ENABLE_QUERY_REWRITE`)
- **Hybrid RAG with Reranking** — BM25 keyword search (40%) + semantic search (60%) via `EnsembleRetriever` (k=30 per retriever), merged and reranked by a cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) down to the top 10 most relevant chunks
- **Paragraph/Heading-Aware Chunking** — Long PDF, DOCX, and HTML content is split on paragraph and heading boundaries rather than blind character windows, so a topic shift doesn't get folded into the wrong chunk
- **Document Structure Indexing** — TOC, chapter headings, and slide titles extracted at ingestion as dedicated structure chunks; injected automatically for structural queries ("what sections are in this book?")
- **Broader Document Ingestion** — PDF, PPTX, Markdown, DOCX, HTML, CSV, and XLSX; spreadsheet rows are flattened into row-windowed chunks (header repeated per chunk) so they're searchable via the same hybrid retriever
- **Metadata-Enriched Context** — Retrieved chunks carry `[Source: file.pdf, Page N]` headers so the LLM can reason about document layout and location
- **Inline Grounded Citations** — Responses cite `[n]` markers tied to the specific retrieved chunk used; the frontend renders them as clickable badges linking to an expandable source-chip strip (filename, page/slide, chunk preview). Hallucinated citation numbers are stripped server-side — validated incrementally even mid-stream, not just on the final aggregate
- **Groundedness Caveat** — Responses generated with zero matching retrieved context are flagged with an inline note that the answer may not be grounded in your documents
- **Image-Aware Indexing** — OCR extracts text from figures, charts, and diagrams in PDFs/PPTX; the images themselves are also extracted and persisted, so they can be shown back in the chat UI
- **Image Chat** — Upload an image directly for vision-model Q&A; follow-up text messages that reference "that image/picture/photo" are automatically routed back to the vision model using the session's last upload
- **LaTeX Normalization** — Regex-based math notation conversion before embedding
- **Model Tiering** — Short, simple, or early-conversation queries are automatically routed to a faster Groq model; longer or structural queries use the full model
- **Response Caching** — Exact-match Redis cache for first-turn queries, avoiding redundant LLM calls. Applies to both streaming and non-streaming chat, which share one retrieval path (`rag.prepare_context`)
- **Streaming Toggle** — Switch between SSE token-by-token streaming and standard responses
- **Document Management** — Upload, list, and delete documents via API; persisted to a local folder (Docker volume in production). Upload/delete/refresh require the `x-admin-key` header (`ADMIN_API_KEY`) — the Documents panel in the UI prompts for it
- **Conversation Memory** — Redis-backed session history with in-memory fallback, write-through persisted to SQLite (`conversation_store.py`) so a page reload after a Redis TTL expiry or backend restart doesn't lose prior turns; recoverable via `GET /conversations` (session id in the `x-session-id` header)
- **On-Demand TTS** — Voice generation via `edge-tts` with playback controls
- **Rate Limiting** — Per-endpoint limits via `slowapi` (see [API Endpoints](#api-endpoints))
- **Analytics** — Query, response, sources, latency, and model tier logged to a local SQLite store, readable from the admin dashboard

---

## Architecture

### Backend Pipeline (4-stage Y-shape)

1. **Input Processing** — text preprocessing / Whisper audio transcription / direct image input
2. **Query Refinement** — query formatting, LLM-generated query rewriting to widen retrieval recall, model-tier selection (fast vs. default Groq model)
3. **RAG Retrieval** — Hybrid BM25 + ChromaDB search (original query + rewrites, retrieved in parallel), cross-encoder reranking, structure-chunk injection for structural queries; deduplication, citation-numbered metadata-enriched context assembly
4. **Response Generation** — Groq LLM (tiered) via LCEL chain with session history, backed by a first-turn exact-match response cache; response is sanitized to strip hallucinated `[n]` citations/image markers (validated incrementally as it streams) and flagged with a groundedness caveat if no context was retrieved

### RAG Document Pipeline

```
PDF / PPTX / MD / DOCX / HTML / CSV / XLSX
       ↓
  Structure extraction (TOC / headings / slide titles) → structure chunk
       ↓
  Parse: PyMuPDF (PDF, per-page) / python-pptx / python-docx / BeautifulSoup (HTML) / csv+openpyxl (tabular)
       ↓
  Image extraction (PDF/PPTX) → Tesseract OCR + persisted to disk (image_ids on chunk metadata)
       ↓
  LaTeX normalization (latex_utils.py)
       ↓
  Per-type chunking — paragraph/heading-aware packing (PDF/DOCX/HTML, ~800 chars),
  character splitting (MD, 600 chars), 1/slide (PPTX), row-windowed (CSV/XLSX, 20 rows/chunk)
       ↓
  ChromaDB (semantic, k=30) + BM25 index (k=30)
       ↓
  Query rewriting (fast-tier Groq model generates alternate phrasings) → EnsembleRetriever (0.4 BM25 / 0.6 semantic) per query variant
       ↓
  Cross-encoder rerank → top 10
       ↓
  Deduplication → structural query routing → citation-numbered, metadata-enriched context (+ up to 4 linked images)
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
cp backend/.env.example backend/.env   # add your GROQ_API_KEY (and ADMIN_API_KEY, see below)
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

Set `ADMIN_API_KEY` if you want to use the Documents panel or the Admin dashboard — both are gated behind it. This covers **browsing** the corpus as well as mutating it (`/documents/list` and `/documents/chunks` expose indexed document text, so they are gated alongside upload/delete/refresh). Without it, those routes return `503` and the corresponding UI prompts for a key that will never validate.

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
| `ADMIN_API_KEY` | No | — | Enables `/admin/*` and **all** `/documents/*` routes, reads included (`x-admin-key` header); if unset, those routes return `503` rather than failing startup |
| `LOCAL_LOGS_DB_PATH` | No | `backend/data/rag_logs.db` | Where analytics are stored (SQLite) |
| `IMAGES_DIR` | No | `backend/data/images/` | Where persisted images (from RAG documents and chat uploads) are stored |
| `IMAGE_LINKS_DB_PATH` | No | `backend/data/image_links.db` | SQLite DB linking uploaded images to sessions (powers "that image" follow-ups) |
| `CONVERSATIONS_DB_PATH` | No | `backend/data/conversations.db` | SQLite write-through store backing `GET /conversations`, so history survives a Redis TTL expiry or backend restart |
| `RERANK_MODEL` | No | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Cross-encoder used to rerank hybrid retrieval results |
| `RERANK_TOP_N` | No | `10` | Number of chunks kept after reranking |
| `ENABLE_QUERY_REWRITE` | No | `true` | Generates alternate query phrasings before retrieval to widen recall; costs one extra fast-tier Groq call per non-trivial query |
| `RESPONSE_CACHE_TTL_SECONDS` | No | `3600` | TTL for the first-turn exact-match response cache (Redis) |
| `ENABLE_RAG_EVAL` | No | `false` | Enables LLM-as-judge scoring of RAG responses |
| `IMAGE_RELEVANCE_THRESHOLD` | No | `0.0` | Minimum relevance score for a retrieved image to be linked into a RAG response |
| `MAX_MESSAGE_LENGTH` | No | `1000` | Max chat message characters |
| `MAX_AUDIO_SIZE_MB` | No | `10` | Max audio upload size |
| `MAX_DOCUMENT_SIZE_MB` | No | `20` | Max document upload size |
| `MAX_UPLOAD_BYTES` | No | 20MB | Byte-level cap enforced in `document_store.py`, alongside `MAX_DOCUMENT_SIZE_MB` |
| `MAX_IMAGE_SIZE_MB` | No | `8` | Max image upload size for `/chat/image` |
| `MAX_TTS_LENGTH` | No | `1500` | Max characters accepted by `/tts/generate` |
| `TRUSTED_PROXY_IPS` | No | — | Comma-separated IPs of reverse proxies allowed to set `X-Forwarded-For`. **Required behind a proxy** — otherwise rate limiting keys every request on the proxy's own address, so all clients share one bucket and a single caller throttles everyone. Only these peers are trusted, so the header can't be spoofed by direct callers. Also enables uvicorn's `--proxy-headers`/`--forwarded-allow-ips` |
| `LOG_LEVEL` | No | `INFO` | Backend log level |

Frontend build-time variable: `VITE_API_URL` — set to your backend's URL (`frontend/.env.local` for dev, or as a Docker build arg).

---

## Project Structure

```
ringo/
├── backend/
│   ├── main.py              # FastAPI server, rate limiting, all endpoints
│   ├── pipeline.py          # Y-shaped pipeline orchestrator
│   ├── rag.py               # RAG singleton, query rewriting, reranking, citation/image sanitization, response cache, model tiering
│   ├── vectorstore.py       # PDF/PPTX/DOCX/HTML/CSV/XLSX loaders, OCR, image extraction, chunking, BM25+semantic hybrid retrieval
│   ├── latex_utils.py       # LaTeX/math notation normalization
│   ├── memory.py            # Redis / in-memory conversation history
│   ├── conversation_store.py # SQLite write-through store backing GET /conversations
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
│   ├── documents/           # Knowledge base files (PDF/PPTX/MD/DOCX/HTML/CSV/XLSX)
│   └── data/                 # SQLite DBs (rag_logs.db, image_links.db) + images/
│
├── frontend/
│   ├── src/
│   │   ├── pages/           # ChatPage, SettingsPage, AdminPage (react-router routes)
│   │   ├── components/      # chat-messages, chat-input, documents-panel, conversations-panel, ...
│   │   ├── hooks/           # settings, conversations, network status, theme
│   │   ├── services/api.ts  # API client with SSE streaming, document, and image endpoints
│   │   └── theme.css        # Design tokens as CSS custom properties
│   ├── nginx.conf           # Production server: CSP + security headers, SPA fallback
│   └── vite.config.ts
│
├── .github/workflows/ci.yml # Tests, dependency CVE audit, lint, build
└── docker-compose.yml
```

---

## API Endpoints

| Method | Path | Rate limit | Description |
|---|---|---|---|
| `GET` | `/` | — | Basic liveness/info response |
| `GET` | `/health` | — | Vector store status, chunk count, Redis status, Groq reachability |
| `GET` | `/health/live` | — | Minimal liveness probe (no dependency checks) |
| `POST` | `/chat/text` | 10/min | Text chat (supports `stream=true`); auto-routes to vision model on image follow-up references |
| `POST` | `/chat/audio` | 10/min | Audio chat with Whisper transcription |
| `POST` | `/chat/image` | 10/min | Image + question chat via the vision model, bypassing RAG |
| `GET` | `/images/{image_id}` | 120/min | Serve a persisted image (extracted from a RAG document or uploaded via chat). Unauthenticated — the 128-bit uuid4 id is the capability |
| `POST` | `/tts/generate` | 20/min | On-demand TTS generation |
| `GET` | `/documents/list` | 30/min | List indexed documents with chunk counts (requires `x-admin-key` header) |
| `POST` | `/documents/upload` | 2/min | Upload and index a document (requires `x-admin-key` header) |
| `DELETE` | `/documents/{filename}` | — | Delete a document, its linked images, and rebuild the index (requires `x-admin-key` header) |
| `GET` | `/documents/chunks` | 30/min | Fetch chunks for a document, with optional query ranking (requires `x-admin-key` header) |
| `POST` | `/documents/refresh` | 5/min | Rebuild the vector store from the local documents folder (requires `x-admin-key` header) |
| `POST` | `/feedback` | 30/min | Submit feedback on a response |
| `GET` | `/conversations` | 60/min | Recover a session's durable message history from the SQLite write-through store. Takes the session id in an `x-session-id` **header**, not the path |
| `GET` | `/admin/stats` | 20/min | Aggregate analytics (requires `x-admin-key` header) |
| `GET` | `/admin/logs` | 20/min | Recent query logs (requires `x-admin-key` header) |

### Session IDs

Every chat route requires a `session_id`, and it must match `session_<uuid4>`:

```
session_3f8a1c92-5d7e-4b21-9f03-6c8e4a1d7b25
```

There is **no default** — omitting it is a `422`, and any other shape (including the
old `"default"` sentinel) is a `400`. The reason is that `session_id` doubles as the
bearer capability for `GET /conversations`: that route has no separate auth, so the
id has to be unguessable, and a value multiple clients could land on would put
unrelated users on one shared server-side conversation. The web client mints ids
with `crypto.randomUUID()` and re-mints any malformed value it reads back from
`localStorage`.

Because it is a credential, it travels in the `x-session-id` **header** on
`GET /conversations` rather than in the URL path, where proxies and access logs
would record it verbatim.

### Response integrity

Model output is sanitized before it reaches the client. Citation markers (`[n]`) not
backed by a real retrieved chunk are stripped, and inline images are allow-listed to
`/images/{32-hex-id}` values that were actually retrieved for that turn — anything
else, including external URLs, is removed rather than rendered. On streamed responses
this happens incrementally, so a partial marker is held back rather than flashing on
screen before cleanup. The web client re-validates both independently, and the
production CSP restricts `img-src` to the API origin.

---

## Deployment

Self-hostable on any server with Docker:

```bash
docker compose up --build -d
```

- **Documents** — stored under `backend/documents/`, bind-mounted as a volume so uploads survive container restarts
- **Vector store** — `backend/chroma_db/`, also volume-mounted
- **Analytics, conversations & images** — SQLite files and persisted images under `backend/data/` (`rag_logs.db`, `conversations.db`, `image_links.db`, `images/`), volume-mounted alongside the others. Without this mount the write-through conversation store loses its durability the moment the container is recreated
- **Sessions** — Redis (bundled in `docker-compose.yml`), or an in-memory fallback if unavailable

The SQLite stores run in WAL mode with one connection per thread, so concurrent request handlers and background tasks don't serialise into `database is locked`.

### Production checklist

1. **CORS** — set `ALLOWED_ORIGINS` (or `ALLOWED_ORIGIN_REGEX`) to your frontend's origin. Note `allow_credentials=True` is on, so an overly broad regex is dangerous; the backend logs a warning if it detects one.
2. **Frontend build** — `docker build --build-arg VITE_API_URL=https://api.yourdomain.com ./frontend`. This value is also substituted into the CSP `connect-src`/`img-src` in `frontend/nginx.conf` at build time, so a mismatch will block API calls in the browser.
3. **Reverse proxy** — put both containers behind nginx/Caddy/Traefik for TLS, then **set `TRUSTED_PROXY_IPS`** to that proxy's address. Skipping this silently degrades rate limiting to a single shared bucket for all clients.
4. **Admin key** — set `ADMIN_API_KEY`. All `/documents/*` and `/admin/*` routes return `503` until it is.

The frontend container serves on **port 8080** (nginx runs unprivileged and cannot bind `:80`); `docker-compose.yml` maps it to `8081` on the host. `frontend/nginx.conf` also sets `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options` and `Referrer-Policy`, and provides the SPA fallback that react-router deep links need.

---

## Development

```bash
cd backend && pytest          # backend suite
cd frontend && npm run lint   # eslint
cd frontend && npm run build  # tsc -b + vite build
```

`.github/workflows/ci.yml` runs all of the above on push and pull request, plus a
dependency CVE audit (`pip-audit` for Python, `npm audit` for the frontend).

Pillow is pinned ahead of its transitive floor deliberately: it parses attacker-supplied
bytes on the unauthenticated `/chat/image` route and during OCR of images embedded in
uploaded documents, making it the most exposed parser in the stack. `aiohttp`, `anyio`
and `cryptography` carry `>=` security floors for the same reason — they're transitive,
but the versions upstream would otherwise resolve to have open advisories.

### Known audit exceptions

The Python audit carries `--ignore-vuln` entries. Both are **unfixable, not unimportant** —
a step that always fails gets muted, which is worse than a narrow, documented exception:

| Advisory | Package | Why it can't be fixed |
|---|---|---|
| `PYSEC-2026-311`, `-3813`, `-3814`, `-3815` | chromadb | No fixed version published upstream. Re-check on every chromadb bump. |
| `PYSEC-2026-3447` | setuptools | Fixed in 83.0.0, but `torch` pins `setuptools<82`, so no torch-compatible release carries the fix. Build tooling, not request-path code. Drop when torch relaxes the pin. |

`npm audit` gates at `--audit-level=high`, so two **moderate** react-router advisories
are reported without failing the build. Fixing them requires react-router-dom v7, a
breaking major upgrade. Neither is reachable in this app as written: every `navigate()`
call targets a hardcoded literal (no user-controlled redirect target), and the second
advisory applies only to SSR hydration, which a Vite SPA does not use. Worth scheduling
the v7 migration, not worth an emergency.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
