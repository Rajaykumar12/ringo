# Configuration

All backend settings are environment variables, read from `backend/.env` (see
`backend/.env.example`). Only `GROQ_API_KEY` is required to start.

Set `ADMIN_API_KEY` too if you want to add documents — the Documents panel and the
Admin dashboard are both gated behind it.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | Yes | — | Groq API key for text and vision models |
| `VISION_MODEL` | No | `qwen/qwen3.8-27b` | Groq model used for image chat and image follow-ups |
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

---

## Frontend build-time variable

`VITE_API_URL` — the backend's URL, baked in at build time
(`frontend/.env.local` for dev, or as a Docker build arg).

**You do not need to set this for `docker compose up.`** The bundled `nginx.conf`
proxies the API paths to the backend container, so the frontend and backend share one
origin and the default same-origin fallback resolves correctly. Set it only when the
frontend is served from a different origin than the API — see
[DEPLOYMENT.md](DEPLOYMENT.md).

---

## Optional system dependency: Tesseract OCR

Only needed when running outside Docker; the image installs nothing extra for it
because OCR is optional and degrades gracefully.

```bash
# Fedora/RHEL
sudo dnf install tesseract tesseract-langpack-eng

# Ubuntu/Debian
sudo apt install tesseract-ocr tesseract-ocr-eng
```

Without Tesseract, documents still index — you just lose text extracted from images
inside them (figures, charts, scanned pages).
