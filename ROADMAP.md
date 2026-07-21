# Ringo — Feature Gaps & Optimization Roadmap

Companion to `AUDIT_REPORT.md` (security/correctness). This report covers where the app is falling behind modern AI chat products, what features are worth adding, and what performance/engineering optimizations are available. Research-only — no code changes. Impact/Effort ratings are rough guides for prioritization, not estimates.

---

## 1. Executive summary

Ringo is a working, single-tenant RAG chat prototype with genuinely good core RAG mechanics: hybrid BM25+semantic retrieval, structure-aware chunking (TOC/headings), OCR on embedded images, and metadata-enriched context. It's behind on three fronts:

- **Engineering maturity** — zero tests despite `pytest` being a dependency, CI that only auto-deploys with no lint/test gate, `print()`-only logging, and a full vector-store rebuild on every single document change.
- **Production scalability** — CPU-heavy operations (Whisper, OCR, embeddings) run synchronously inside `async def` route handlers, blocking the event loop; and core state (`rag_system`, `pipeline`) is a per-process singleton that won't survive multiple workers/replicas without rework.
- **Product feature parity** — no persisted chat history, no dark mode (despite the scaffolding already existing), no markdown/code rendering, no message actions (copy/edit/regenerate/stop), no multimodal image input.

None of this is urgent in the way the security findings were — this is a roadmap, not an incident list.

---

## 2. Falling behind — engineering & scalability gaps

| Gap | Impact | Effort | Detail |
|---|---|---|---|
| No tests, no CI | High | Med | `pytest`/`pytest-asyncio`/`httpx` are in `backend/requirements.txt` but zero test files exist anywhere in the repo. The old Azure-generated deploy-only workflows (checkout → Azure login → build & push) were removed as part of the self-hosting migration; there is currently no CI at all. **Fix direction**: add a basic pytest suite (health endpoint, session-id validation, chunking logic) and a CI job (e.g. GitHub Actions running tests/lint on PRs) as a starting gate. |
| Blocking calls inside async handlers | High | Low-Med | `pipeline.process_text`/`process_audio` (`main.py:220, 267`), Whisper transcription (`pipeline.py:47`), Tesseract/PyMuPDF document ingestion (`vectorstore.py`), and HuggingFace embedding inference all run synchronously inside `async def` routes — each blocks the single event loop for the duration of the call, so one slow request (e.g. audio transcription) stalls every other concurrent user. The codebase already knows the right pattern: `run_in_executor` is used correctly for eval scoring (`main.py:213`) and edge-tts (`pipeline.py`). **Caution**: a thread-offloading fix was attempted on 2026-07-12 (commit `56e4f1f`) and reverted 4 minutes later (`e658e27`) the same night — worth checking why it was rolled back before retrying, rather than assuming it's a simple re-apply. |
| Full index rebuild on every document change | High | Med | `create_vectorstore()` in `vectorstore.py` drops the entire ChromaDB collection (`delete_collection()`) and recreates it from scratch (`Chroma.from_documents()`) on every single upload or delete; the BM25 index is fully rebuilt in-memory too. Cost and latency scale with total corpus size, not the size of the change. **Fix direction**: incremental add/delete against the existing collection instead of full rebuild. |
| No structured logging/observability | High | Low (cheap win) | ~94 raw `print()` calls across the backend, zero use of the `logging` module, no request correlation IDs, no metrics/APM. Debugging production issues means reading unstructured stdout. **Fix direction**: swap to `logging` with levels — mechanical, low-risk, easy first PR. |
| Singleton state won't survive horizontal scaling | High (only if scaling out) | High | `rag_system` and `pipeline` are per-process singletons built once in `lifespan()`. Multiple uvicorn workers or container replicas would each get an independent BM25 index and model copies (heavy RAM/CPU duplication), and concurrent writers racing ChromaDB's `delete_collection()`/`from_documents()` risk corruption with no locking. **Fix direction**: not worth addressing until actually scaling beyond one replica — flag as a known constraint for now. |
| No re-ranking / retrieval tuning | Med | Med | BM25(0.4)+semantic(0.6) ensemble retrieves k=30 from each and concatenates everything with no cross-encoder re-rank step and no top-N cutoff after the merge — risks noisy, oversized prompts as the corpus grows. |
| No caching | Med | Med | No embedding cache (unchanged documents get re-embedded on every refresh, compounding the full-rebuild issue above), no LLM/semantic response cache for repeated or near-duplicate queries. |
| No model routing for chat complexity | Low-Med | Med | Every chat query hits `llama-3.3-70b-versatile`. Model routing already exists for the eval judge (`eval.py` uses the cheaper `llama-3.1-8b-instant`) — the same pattern could route simple queries to a faster/cheaper model. |
| Hardcoded Whisper size, limited health check | Low-Med | Low | Whisper model size hardcoded to `"base"` (`pipeline.py:32`) instead of env-configurable. `/health` only checks vectorstore chunk count and Redis ping — no Groq reachability check, no liveness/readiness distinction, no timeout on the Redis ping (could hang under a network partition). |
| Narrow document format support | Low | Med | PDF/PPTX/MD only — no DOCX, XLSX, CSV, or HTML ingestion, a real gap for enterprise document corpora. |

---

## 3. Falling behind — frontend/UX gaps

| Gap | Impact | Effort | Detail |
|---|---|---|---|
| No persisted chat history / multi-conversation support | High | Med | Messages live only in React state (`app/index.tsx`) — lost on reload. No thread list, rename, delete, or search across past conversations. |
| No dark mode despite the scaffolding already existing | Med | Low (cheap win) | `useColorScheme` is already wired into React Navigation's theme wrapper in `_layout.tsx`, but all actual UI (chat bubbles, buttons, backgrounds) pulls static colors from a single light-only `Colors` palette in `constants/theme.ts`. Adding a dark palette and threading it through the existing hook is a contained, well-scoped change since half the plumbing is already there. |
| No rich responses | Med | Med | AI responses render as plain RN `<Text>` only — no markdown, code blocks/syntax highlighting, or tables — despite the backend already normalizing LaTeX for embedding quality (`latex_utils.py`), which never reaches the user formatted. |
| No message actions | Med | Low-Med | No copy-to-clipboard, edit-and-resend, regenerate response, or stop-generation-mid-stream controls anywhere in `chat-messages.tsx`/`chat-input.tsx`. |
| No multimodal input | Med | Med | No image attach/paste directly into chat despite Groq offering vision-capable Llama models; only the separate document-upload panel exists (PDF/PPTX/MD, not images-as-input). |
| No settings screen | Low-Med | Low | No user-exposed toggles anywhere for theme, text size, default language persistence, or streaming on/off (streaming is hardcoded `true` in `app/index.tsx`). |
| No offline resilience | Low-Med | Med | A dropped connection just throws/logs (`services/api.ts`) — no retry-on-reconnect, no offline message queueing, no network-state detection. |
| No i18n for UI chrome | Low | Med | Only the AI's *response* language is selectable (en/hi/ta/te) — all buttons, alerts, and placeholders are hardcoded English strings. |
| No PWA support | Low | Low | The web build (`expo export --platform web`, served by nginx) has no `manifest.json` or service worker — not installable or offline-cacheable despite being a static web app. |
| Minimal accessibility | Low | Med | A handful of `accessibilityLabel`s exist on icon buttons, but no dynamic font scaling, no screen-reader live regions for streaming text, no focus management. |

---

## 4. Feature ideas worth adding

Net-new product ideas, distinct from the gap list above (some directly close a gap, framed here as a feature rather than a deficiency):

- **Multi-turn conversation threads with persistent history** — closes the biggest frontend gap above.
- **Regenerate / edit-and-resend / copy-to-clipboard** on messages.
- **Markdown + code-block rendering with syntax highlighting** for AI responses.
- **Image input** (paste/attach) leveraging Groq's vision-capable models.
- **Dark mode toggle** — cheap win given existing scaffolding.
- **Settings screen** (theme, text size, default language, streaming toggle).
- **Inline source-chunk highlighting** in the response itself, extending the existing "Source Preview" feature beyond a flat source list.
- **Export/share a conversation** (markdown or PDF).
- **Admin/analytics dashboard** surfacing the RAG logs already being collected locally (`rag_logger.py`/`local_store.py`) — currently write-only; nothing reads this data back today.
- **Cross-encoder re-ranking** for retrieval quality — same item as the backend gap above, framed as a quality feature.

---

## 5. Priority table (quick wins → bigger investments → nice-to-have)

| Priority | Item | Impact | Effort | Category | Status |
|---|---|---|---|---|---|
| 1 | Structured logging (`logging` module instead of `print`) | High | Low | Backend | **Done** |
| 2 | Dark mode (scaffolding already exists) | Med | Low | Frontend | **Done** |
| 3 | `/health` improvements (Groq check, liveness/readiness split, Redis timeout) | Med | Low | Backend | **Done** |
| 4 | Settings screen | Low-Med | Low | Frontend | **Done** |
| 5 | PWA manifest/service worker | Low | Low | Frontend | **Done** |
| 6 | Basic pytest suite + CI test gate | High | Med | Backend | **Done** |
| 7 | Blocking-call offload to threads (retry carefully — see reverted attempt) | High | Low-Med | Backend | **Done** |
| 8 | Incremental vector-store indexing (stop full rebuilds) | High | Med | Backend | **Done** |
| 9 | Message actions (copy/edit/regenerate/stop) | Med | Low-Med | Frontend | **Done** |
| 10 | Persisted chat history / multi-conversation threads | High | Med | Frontend | **Done** |
| 11 | Markdown/code-block rendering | Med | Med | Frontend | **Done** |
| 12 | Cross-encoder re-ranking | Med | Med | Backend | **Done** |
| 13 | Embedding/response caching | Med | Med | Backend | **Done** |
| 14 | Multimodal image input | Med | Med | Frontend | **Done** |
| 15 | Admin/analytics dashboard for existing RAG logs | Med | Med | Full-stack | **Done** |
| 16 | Offline resilience / retry-on-reconnect | Low-Med | Med | Frontend | **Done** (scope: network detection, retry/backoff, offline UI feedback — full offline message queueing explicitly out of scope, see note below) |
| 17 | Model routing by query complexity | Low-Med | Med | Backend | **Done** |
| 18 | i18n for UI chrome | Low | Med | Frontend | **Done** (chat surface + settings; admin dashboard intentionally left English-only as internal/dev-facing) |
| 19 | Accessibility improvements | Low | Med | Frontend | **Done** (accessibilityRole audit, modal focus/labeling, throttled streaming live-region — dynamic font scaling split out as a follow-up, see below) |
| 20 | Broader document format support (DOCX/XLSX/CSV/HTML) | Low | Med | Backend | Pending |
| 21 | Singleton → multi-worker/replica-safe architecture | High* | High | Backend | Pending |

\* High impact only once actual horizontal scaling is needed — not urgent at current single-tenant scale.

**Follow-ups spun out of items 16/19 during implementation:**
- **Offline message queueing** (compose-while-offline, auto-flush-on-reconnect) — deferred from item 16. This is an Expo Router web target with no background sync, so a queue would mostly benefit a future native build; disproportionate effort for the current web-primary target.
- **Dynamic font scaling** — deferred from item 19 (Phase 4). Requires introducing a `FontSizes`/`Typography` token system in `constants/theme.ts` and refactoring inlined `fontSize` literals across most components — the largest surface area of any accessibility sub-item, worth its own pass.
- **hi/ta/te translation review** — item 18's Hindi/Tamil/Telugu UI strings (`frontend/locales/`) are machine-assisted; recommend native-speaker review before considering non-English UI chrome fully "supported."
