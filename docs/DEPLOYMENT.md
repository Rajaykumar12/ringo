# Deployment

Self-hostable on any server with Docker:

```bash
docker compose up --build -d
```

---

## What persists where

- **Documents**: stored under `backend/documents/`, bind-mounted as a volume so uploads survive container restarts
- **Vector store**: `backend/chroma_db/`, also volume-mounted
- **Analytics, conversations & images**: SQLite files and persisted images under `backend/data/` (`rag_logs.db`, `conversations.db`, `image_links.db`, `images/`), volume-mounted alongside the others. Without this mount the write-through conversation store loses its durability the moment the container is recreated
- **Sessions**: Redis (bundled in `docker-compose.yml`), or an in-memory fallback if unavailable

The SQLite stores run in WAL mode with one connection per thread, so concurrent request handlers and background tasks don't serialise into `database is locked`.

---

## Ports and the API proxy

The frontend container serves on **port 8080** (nginx runs unprivileged and cannot
bind `:80`); `docker-compose.yml` maps it to `8081` on the host. The backend is on
`8000`.

`frontend/nginx.conf` proxies the backend's paths (`/chat/`, `/documents/`,
`/images/`, `/tts/`, `/conversations`, `/feedback`, `/health`, `/admin/stats`,
`/admin/logs`) to `backend:8000`. Two consequences worth knowing:

- **The API and the web app share one origin**, so CORS is not involved in the
  default deployment and no `VITE_API_URL` needs setting.
- The proxy sets `proxy_buffering off`, which streaming chat requires. With buffering
  on, nginx holds the whole SSE response and releases it at the end, so answers
  arrive in one block instead of token by token.

Paths are proxied by explicit prefix rather than a catch-all because `/admin` and
`/settings` are react-router pages served by the SPA, while `/admin/stats` and
`/admin/logs` are backend routes. A blanket `/admin` proxy would 404 the dashboard.

nginx also sets `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`
and `Referrer-Policy`, and provides the SPA fallback that react-router deep links need.

---

## Production checklist

1. **Admin key**: set `ADMIN_API_KEY`. All `/documents/*` and `/admin/*` routes return `503` until it is, which means you cannot add documents.
2. **TLS**: put the stack behind nginx/Caddy/Traefik for HTTPS, then **set `TRUSTED_PROXY_IPS`** to that proxy's address. Skipping this silently degrades rate limiting to a single shared bucket for all clients, so one caller can then throttle everyone.
3. **CORS**: only needed if you serve the frontend from a different origin than the API. If so, set `ALLOWED_ORIGINS` (or `ALLOWED_ORIGIN_REGEX`) to the frontend's origin. Note `allow_credentials=True` is on, so an overly broad regex is dangerous; the backend logs a warning if it detects one.
4. **Split-origin frontend build**: again only for a different-origin deployment. Run `docker build --build-arg VITE_API_URL=https://api.yourdomain.com ./frontend`. This value is substituted into the CSP `connect-src`/`img-src` in `frontend/nginx.conf` at build time, so a mismatch will block API calls in the browser.

Steps 3 and 4 go together, so do both or neither. The default same-origin setup needs
neither.

---

## Scaling notes

- **Redis is optional but recommended.** Without it, session memory and the response
  cache fall back to per-process in-memory stores, which means they do not survive a
  restart and are not shared across replicas. Conversation history still persists,
  because SQLite is written through on every turn regardless.
- **Rate limits are stored in Redis** when `REDIS_URL` is reachable, so they hold
  across restarts and are shared by all replicas. Without it they are per-process.
- **The vector store and SQLite files are local disk.** Running more than one backend
  replica against the same bind-mounted volume is not supported as configured.
