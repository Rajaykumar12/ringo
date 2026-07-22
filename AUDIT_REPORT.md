# Ringo — End-to-End Security & Feature Audit

Scope: `backend/` (FastAPI + Groq + RAG pipeline) and `frontend/` (Expo/React Native web). Severities: **High** (fix now) / **Medium** (fix before wider/public deployment) / **Low** (cleanup, non-urgent) / **Info**.

> **Status: all findings below have been addressed** (see "Fix applied" note on each row) except where explicitly marked deferred, with the reasoning noted inline.

---

## 1. Executive summary

Overall the codebase shows solid defensive habits for a single-tenant, admin-controlled deployment: secrets are gitignored and never hardcoded, path traversal is blocked, upload types/sizes are capped, rate limiting covers every expensive endpoint, error responses don't leak stack traces, and the frontend has no XSS surface (no `dangerouslySetInnerHTML`, no `WebView`) and no embedded secrets.

The one **live, currently-active gap** was that the admin authentication on document management endpoints was silently disabled because `ADMIN_API_KEY` was not set anywhere in `backend/.env`. All findings below have now been fixed (see §3), except the `expo-av` deprecation and the local-dev Redis port exposure, which are intentionally deferred with reasoning noted inline.

---

## 2. Critical / live issue — RESOLVED (by design decision)

### `ADMIN_API_KEY` unset → admin endpoints were running unauthenticated

`backend/main.py` previously gated `POST /documents/refresh`, `POST /documents/upload`, and `DELETE /documents/{filename}` behind an `X-API-Key` check that silently no-opped whenever `ADMIN_API_KEY` was unset — and it was unset in `backend/.env`, so these endpoints were fully public.

**Decision made with the user**: the frontend's document panel never sent an `X-API-Key` header and has no concept of an admin user — document management is a feature every user of the app can access, not an admin-only operation. Baking an "admin" key into the public frontend bundle wouldn't have been real security anyway (anyone can read it out of the JS). Given that, the fix was to **remove the admin-key gate entirely** rather than fail-closed (which would have broken the feature for all users) or thread a shared key through the client (false sense of security).

**Fix applied**: `ADMIN_API_KEY` / `require_admin_key` dependency removed from `backend/main.py`; document management now relies on the existing protections that were already in place — file type/size validation and per-endpoint rate limiting (2/min upload, 5/min refresh). If the product later needs true admin-only document management, it will need real user authentication first (see finding #3), not a bolt-on API key.

---

## 3. Findings by severity

| # | Severity | Area | Location | Issue | Status |
|---|----------|------|----------|-------|--------|
| 1 | **High** | Backend auth | `main.py` (was 40-56, 342, 381, 405) | Admin endpoints fail-open with no `ADMIN_API_KEY` set | **Fixed** — admin-key gate removed entirely (see §2); protection is now file validation + rate limiting |
| 2 | Medium | Backend auth | `main.py` (`/documents/list`, `/documents/chunks`) | No auth on read endpoints | **No change needed** — consistent with the §2 decision that document management is a public app feature, not admin-only |
| 3 | Medium | Backend auth | `main.py` (`session_id` handling) | `session_id` had no random component — a guessable, sequential identifier | **Fixed** — frontend now generates `session_${Date.now()}_${random}` (`frontend/app/index.tsx`), no longer a bare timestamp. Full ownership binding still requires real user auth, out of scope here |
| 4 | Medium | Backend supply chain | `backend/requirements.txt` | Every package unpinned | **Fixed** — pinned to the exact versions installed in `venv/` (torch 2.12.1, fastapi 0.138.2, langchain 1.3.11, chromadb 1.5.9, etc.) |
| 5 | Medium | Backend Docker | `backend/Dockerfile` | Container ran as root | **Fixed** — added `groupadd`/`useradd` + `USER appuser` before `CMD` |
| 6 | Medium | Frontend Docker | `frontend/Dockerfile` | Lockfile not used in Docker build | **Fixed** — now `COPY package.json package-lock.json ./` + `RUN npm ci` |
| 7 | Medium | Frontend error handling | `frontend/components/documents-panel.tsx` | Raw backend `error.response.data.detail` shown to users | **Fixed** — added `getErrorMessage()` helper that only surfaces `detail` for 4xx responses (deliberate validation messages); 5xx/network errors show a generic fallback |
| 8 | Low/Medium | Backend CORS | `main.py` | CORS regex trusted any `*.azurecontainerapps.io` subdomain | **Fixed** — regex narrowed to `https://adk-[\w-]+\.azurecontainerapps\.io` (this project's app-naming prefix), now overridable via `ALLOWED_ORIGIN_REGEX` env var |
| 9 | Low-Medium | RAG / prompt injection | `backend/vectorstore.py` | No delimiter/guard around retrieved context in the system prompt | **Fixed** — context now wrapped in `<context>...</context>` with an explicit instruction to treat its contents as data, not commands |
| 10 | Low-Medium | Frontend error handling | `frontend/app/_layout.tsx` | `ErrorBoundary` rendered the raw `error.message` | **Fixed** — now shows a static generic message; full error still goes to `console.error` for debugging |
| 11 | Low | Infra | `docker-compose.yml` | Redis exposed on host port 6379, no password | **Deferred by design** — this compose file is local-dev only (prod uses Azure Cache for Redis per the README); removing the port mapping would only hamper local debugging, so left as-is with this note as the guardrail against reusing it for a public host |
| 12 | Low | Frontend upload UX | `documents-panel.tsx` | No client-side file size check despite UI stating a 20MB limit | **Fixed** — added a pre-upload size check against `MAX_DOCUMENT_SIZE_MB` with an immediate alert instead of a wasted upload |
| 13 | Low | Frontend audio | `app/index.tsx` recording flow | No client-side duration cap on recordings | **Fixed** — added a 2-minute auto-stop timer with a user-facing alert when the limit is hit |
| 14 | Low | Frontend deps | `frontend/package.json` (`expo-av`) | `expo-av` is deprecated upstream | **Deferred** — migrating to `expo-audio`/`expo-video` touches both the recording and TTS-playback code paths; doing that safely needs interactive testing in a running app, which wasn't exercised in this session. Recommend scheduling as its own change, not bundled into an audit fix pass |
| 15 | Info | Backend session ids | related to #3 | `MAX_SESSION_ID_LENGTH = 128` enforced but doesn't address ownership | No action beyond #3 |

---

## 4. What's implemented well (don't touch)

- **Secrets hygiene**: `.env` is gitignored (`!.env.example` only tracked); keys loaded via `os.environ`/`load_dotenv()`; app fails fast at startup if `GROQ_API_KEY` is missing (`main.py:76-77`). No hardcoded secrets anywhere in backend or frontend (confirmed by grep in both audits).
- **Path traversal protection**: `blob_sync.py` sanitizes filenames via `os.path.basename()` before any filesystem/blob operation.
- **Upload validation**: document uploads restricted to `.pdf/.pptx/.md`, size-capped via `MAX_DOCUMENT_SIZE_MB`/`MAX_UPLOAD_BYTES`; audio capped via `MAX_AUDIO_SIZE_MB`; chat messages capped via `MAX_MESSAGE_LENGTH`.
- **Rate limiting**: `slowapi` applied per-endpoint (10/min chat, 20/min TTS, 2/min upload, 5/min refresh, 30/min feedback), keyed by remote address, with OPTIONS preflight correctly exempted (`main.py:80-83`).
- **Error responses**: every `except Exception` path returns a generic `HTTPException(500, "Internal server error")` to the client; details only go to server-side `print()` logs, not the response body.
- **`feedback` endpoint injection guard**: `log_id`/`log_date` are regex-validated before being used as Azure Table Storage keys (`main.py:310-313`).
- **`ENABLE_RAG_EVAL` feature flag**: defaults to `false`, matches `.env.example` docs, and when enabled runs as a non-blocking background task with its own try/except and input truncation (`eval.py`) — safe implementation, only cost impact is extra Groq calls.
- **Frontend**: HTTPS-only (no `http://` fallback anywhere), no XSS vectors (plain RN `<Text>` rendering, no HTML/markdown parsing, no `WebView`), no secrets baked into the client bundle, reasonably current dependency versions (Expo ~54, React 19, RN 0.81).

---

## 5. Feature completeness

**Implemented and working**, matching the README's claims:
- Y-shaped pipeline (text + audio → shared processing)
- Hybrid RAG (BM25 + semantic via `EnsembleRetriever`), structure-chunk injection for TOC/heading queries, metadata-enriched context with source page tags
- SSE streaming toggle for chat responses
- Source preview (inspect retrieved chunks)
- Document management (upload/list/delete) with Azure Blob or local-folder persistence
- Redis-backed conversation memory with in-memory fallback
- On-demand TTS via edge-tts, with playback controls
- Health-check-gated app startup on the frontend

**Gaps / minor incompleteness** (not bugs, just unfinished polish):
- No markdown/LaTeX rendering in the frontend — the backend normalizes LaTeX (`latex_utils.py`) for embedding quality, but AI responses are rendered as plain `<Text>`, so any math notation reaching the user isn't formatted.
- No persisted chat history — `messages` state lives only in React state (`app/index.tsx`), lost on refresh/reload; no multi-session support in the UI.
- No settings screen.
- No retry/backoff logic on failed streaming responses.

---

## 6. Remaining follow-ups

Everything actionable in this pass has been applied directly to the codebase. Two items are intentionally left open:

1. **`expo-av` → `expo-audio`/`expo-video` migration** (#14) — deprecated but functional; deferred to its own change since it touches both recording and TTS playback and deserves interactive testing.
2. **Real user authentication** — if document management or per-user chat history ownership ever need to be locked down again, that requires an actual login/identity system, not another bolt-on API key (see §2 and finding #3). Worth a dedicated design discussion if/when the product needs multi-user isolation.

### Verification performed
- `backend/main.py` and `backend/vectorstore.py` parse cleanly and the FastAPI app builds with all expected routes (`python -c "import main"`).
- `frontend/`: `npx tsc --noEmit` passes with no type errors after the edits.
- Confirmed `frontend/package-lock.json` exists so `npm ci` in the Dockerfile will work.
- Spot-checked every file:line citation against the actual source before editing.
