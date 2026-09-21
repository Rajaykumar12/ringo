# API Reference

The base URL is the backend, `http://localhost:8000` when running it directly, or the
same origin as the web app under `docker compose` (nginx proxies these paths through).

Routes marked `x-admin-key` require that header to match `ADMIN_API_KEY`; they return
`503` if no key is configured on the server and `401` if the key doesn't match.

---

## Endpoints

| Method | Path | Rate limit | Description |
|---|---|---|---|
| `GET` | `/` | none | Basic liveness/info response |
| `GET` | `/health` | none | Vector store status, chunk count, Redis status, Groq reachability |
| `GET` | `/health/live` | none | Minimal liveness probe (no dependency checks) |
| `POST` | `/chat/text` | 10/min | Text chat (supports `stream=true`); auto-routes to vision model on image follow-up references |
| `POST` | `/chat/audio` | 10/min | Audio chat with Whisper transcription |
| `POST` | `/chat/image` | 10/min | Image + question chat via the vision model, bypassing RAG |
| `GET` | `/images/{image_id}` | 120/min | Serve a persisted image (extracted from a RAG document or uploaded via chat). Unauthenticated, since the 128-bit uuid4 id is itself the capability |
| `POST` | `/tts/generate` | 20/min | On-demand TTS generation |
| `GET` | `/documents/list` | 30/min | List indexed documents with chunk counts (requires `x-admin-key` header) |
| `POST` | `/documents/upload` | 2/min | Upload and index a document (requires `x-admin-key` header) |
| `DELETE` | `/documents/{filename}` | none | Delete a document, its linked images, and rebuild the index (requires `x-admin-key` header) |
| `GET` | `/documents/chunks` | 30/min | Fetch chunks for a document, with optional query ranking (requires `x-admin-key` header) |
| `POST` | `/documents/refresh` | 5/min | Rebuild the vector store from the local documents folder (requires `x-admin-key` header) |
| `POST` | `/feedback` | 30/min | Submit feedback on a response |
| `GET` | `/conversations` | 60/min | Recover a session's durable message history from the SQLite write-through store. Takes the session id in an `x-session-id` **header**, not the path |
| `GET` | `/admin/stats` | 20/min | Aggregate analytics (requires `x-admin-key` header) |
| `GET` | `/admin/logs` | 20/min | Recent query logs (requires `x-admin-key` header) |

---

## Session IDs

Every chat route requires a `session_id`, and it must match `session_<uuid4>`:

```
session_3f8a1c92-5d7e-4b21-9f03-6c8e4a1d7b25
```

There is **no default.** Omitting it is a `422`, and any other shape (including the
old `"default"` sentinel) is a `400`. The reason is that `session_id` doubles as the
bearer capability for `GET /conversations`: that route has no separate auth, so the
id has to be unguessable, and a value multiple clients could land on would put
unrelated users on one shared server-side conversation. The web client mints ids
with `crypto.randomUUID()` and re-mints any malformed value it reads back from
`localStorage`.

Because it is a credential, it travels in the `x-session-id` **header** on
`GET /conversations` rather than in the URL path, where proxies and access logs
would record it verbatim.

---

## Response integrity

Model output is sanitized before it reaches the client. Citation markers (`[n]`) not
backed by a real retrieved chunk are stripped, and inline images are allow-listed to
`/images/{32-hex-id}` values that were actually retrieved for that turn. Anything
else, including external URLs, is removed rather than rendered. On streamed responses
this happens incrementally, so a partial marker is held back rather than flashing on
screen before cleanup. The web client re-validates both independently, and the
production CSP restricts `img-src` to the API origin.

---

## Streaming

`POST /chat/text` with `stream=true` returns `text/event-stream`. Each line is
`data: {json}` with a `type` field:

| `type` | Meaning |
|---|---|
| `sources` | The retrieved chunks backing this answer, sent before generation starts |
| `content` | A chunk of answer text, already sanitized |
| `log_id` | Identifier for this turn, used when submitting feedback |
| `images` | Images linked to the retrieved chunks |
| `done` | Final event, repeats the full `sources` and `images` lists |

A cache hit emits the same event sequence, just with the whole answer in a single
`content` event.
