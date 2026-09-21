# Architecture

How Ringo works internally. For running it, see the [README](../README.md); for
configuration, [CONFIGURATION.md](CONFIGURATION.md); for the HTTP surface,
[API.md](API.md).

---

## Stack

- **Groq (`openai/gpt-oss-120b` / `openai/gpt-oss-20b`)** for fast text generation, with automatic model tiering
- **Groq vision model** (`qwen/qwen3.8-27b`) for image-aware chat
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

Fully self-hostable with no cloud vendor lock-in. Documents, images, and analytics live on local disk/SQLite, and sessions in Redis (or an in-memory fallback).

---

## Features

- **Y-Shaped Pipeline**: Unified processing for text and audio inputs
- **Query Rewriting**: Vague or multi-part queries are expanded into alternate phrasings (fast-tier Groq model) before retrieval, widening hybrid-search recall; skipped for structural/short queries (`ENABLE_QUERY_REWRITE`)
- **Hybrid RAG with Reranking**: BM25 keyword search (40%) + semantic search (60%) via `EnsembleRetriever` (k=30 per retriever), merged and reranked by a cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) down to the top 10 most relevant chunks
- **Paragraph/Heading-Aware Chunking**: Long PDF, DOCX, and HTML content is split on paragraph and heading boundaries rather than blind character windows, so a topic shift doesn't get folded into the wrong chunk
- **Document Structure Indexing**: TOC, chapter headings, and slide titles extracted at ingestion as dedicated structure chunks; injected automatically for structural queries ("what sections are in this book?")
- **Broader Document Ingestion**: PDF, PPTX, Markdown, DOCX, HTML, CSV, and XLSX; spreadsheet rows are flattened into row-windowed chunks (header repeated per chunk) so they're searchable via the same hybrid retriever
- **Metadata-Enriched Context**: Retrieved chunks carry `[Source: file.pdf, Page N]` headers so the LLM can reason about document layout and location
- **Inline Grounded Citations**: Responses cite `[n]` markers tied to the specific retrieved chunk used; the frontend renders them as clickable badges linking to an expandable source-chip strip (filename, page/slide, chunk preview). Hallucinated citation numbers are stripped server-side. They are validated incrementally even mid-stream, not just on the final aggregate
- **Groundedness Caveat**: Responses generated with zero matching retrieved context are flagged with an inline note that the answer may not be grounded in your documents
- **Image-Aware Indexing**: OCR extracts text from figures, charts, and diagrams in PDFs/PPTX; the images themselves are also extracted and persisted, so they can be shown back in the chat UI
- **Image Chat**: Upload an image directly for vision-model Q&A; follow-up text messages that reference "that image/picture/photo" are automatically routed back to the vision model using the session's last upload
- **LaTeX Normalization**: Regex-based math notation conversion before embedding
- **Model Tiering**: Short, simple, or early-conversation queries are automatically routed to a faster Groq model; longer or structural queries use the full model
- **Response Caching**: Exact-match Redis cache for first-turn queries, avoiding redundant LLM calls. Applies to both streaming and non-streaming chat, which share one retrieval path (`rag.prepare_context`)
- **Streaming Toggle**: Switch between SSE token-by-token streaming and standard responses
- **Document Management**: Upload, list, and delete documents via API; persisted to a local folder (Docker volume in production). Upload/delete/refresh require the `x-admin-key` header (`ADMIN_API_KEY`), which the Documents panel in the UI prompts for
- **Conversation Memory**: Redis-backed session history with in-memory fallback, write-through persisted to SQLite (`conversation_store.py`) so a page reload after a Redis TTL expiry or backend restart doesn't lose prior turns; recoverable via `GET /conversations` (session id in the `x-session-id` header)
- **On-Demand TTS**: Voice generation via `edge-tts` with playback controls
- **Rate Limiting**: Per-endpoint limits via `slowapi` (see [API.md](API.md))
- **Analytics**: Query, response, sources, latency, and model tier logged to a local SQLite store, readable from the admin dashboard

---

## Backend Pipeline (4-stage Y-shape)

1. **Input Processing**: text preprocessing / Whisper audio transcription / direct image input
2. **Query Refinement**: query formatting, LLM-generated query rewriting to widen retrieval recall, model-tier selection (fast vs. default Groq model)
3. **RAG Retrieval**: Hybrid BM25 + ChromaDB search (original query + rewrites, retrieved in parallel), cross-encoder reranking, structure-chunk injection for structural queries; deduplication, citation-numbered metadata-enriched context assembly
4. **Response Generation**: Groq LLM (tiered) via LCEL chain with session history, backed by a first-turn exact-match response cache; response is sanitized to strip hallucinated `[n]` citations/image markers (validated incrementally as it streams) and flagged with a groundedness caveat if no context was retrieved

Both chat modes, streaming and non-streaming, share a single retrieval path
(`rag.prepare_context`), so they cannot drift apart in what they retrieve, cache, or cite.

---

## RAG Document Pipeline

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
  Per-type chunking: paragraph/heading-aware packing (PDF/DOCX/HTML, ~800 chars),
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

---

## Image Chat Path

Image chat bypasses the RAG pipeline entirely:

- `POST /chat/image` sends an uploaded image straight to a vision-capable Groq model along with the user's question, persists the image to disk, and links it to the session.
- A later **text-only** message referencing "that image/picture/photo/pic/screenshot" is detected heuristically and automatically re-routed to the vision model using the session's most recently uploaded image, instead of the normal RAG chain.
- Images surfaced from RAG document retrieval (extracted during ingestion) and images uploaded via chat are served through the same `GET /images/{image_id}` endpoint.

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
│   ├── vision.py            # Groq vision model, backs /chat/image and image follow-ups
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
│   ├── nginx.conf           # Production server: API proxy, CSP + security headers, SPA fallback
│   └── vite.config.ts
│
├── docs/                    # This directory
├── .github/workflows/ci.yml # Tests, dependency CVE audit, lint, build
└── docker-compose.yml
```
