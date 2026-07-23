# Ringo — Capability Expansion: Implementation Plan

Companion to `ROADMAP.md`/`AUDIT_REPORT.md`. This is a **sequenced build order** across Track A (deepen existing RAG/chat capability, no new UI) and Track B (net-new features), where each step is implemented so that later steps can build on it.

Steps are numbered 1→10 in the order they should be built. The ordering is deliberate:
- A1→A4 harden the retrieval/response core that every later step (including all of Track B) depends on.
- B1 (ingestion) and B3 (citations) are pulled forward because they're self-contained and don't need auth.
- A5/A6 (durable storage, observability) are placed right before B4 (auth) because auth needs a real DB anyway — one migration, not two.
- B2 (agentic tool-use) and B5 (cross-document synthesis) come last because they consume the query-rewriting (A1), citation (B3), and confidence-gating (A2) machinery built earlier.

## Progress

| Step | Status |
|---|---|
| 1 — Query rewriting / multi-query retrieval | **Done** |
| 2 — Confidence / groundedness gating | **Done** |
| 3 — Chunking strategy tuning | **Done** |
| 4 — Retrieval-quality regression gate in CI | **Reverted** (by request — no CI test file or workflow currently in the repo) |
| 5 — Broader document ingestion (DOCX/XLSX/CSV/HTML) | **Done** |
| 6 — Inline grounded citations | **Done** (plus a follow-up fix: citations/image markers are now validated incrementally mid-stream, not just in the final SSE `done` event) |
| 7 — Durable conversation storage | Pending |
| 8 — Real user auth + per-user document libraries | Pending — flagged as a product-scope decision, not just engineering |
| 9 — Agentic / tool-use layer | Pending |
| 10 — Cross-document synthesis mode | Pending |

Each "Done" step's write-up below is left as originally planned, with an added **Actual** note where the real implementation deviated from the plan.

---

## Step 1 (A1) — Query rewriting / multi-query retrieval

**Why first:** every other step re-runs retrieval; improving retrieval quality once benefits all of them, including the eval-gating and citation steps below.

**Where:** `backend/rag.py`, function `get_rag_response()` (`rag.py:204`), specifically the retrieval block at `rag.py:225-227` (`retriever.invoke(query)`).

**Implementation:**
1. Add a new function `rewrite_query(query: str, history_len: int) -> List[str]` in `rag.py`, using the existing fast Groq model tier (same client pattern as `eval.py:16-23`) to generate 2 alternate phrasings of the query. Skip rewriting entirely for structural queries (`_is_structural_query` already exists at `rag.py:55`) and for queries under ~15 chars (not worth the extra LLM round-trip).
2. In `get_rag_response()`, replace the single `retriever.invoke(query)` call with a loop over `[query] + rewrite_query(query, len(history))`, invoking the retriever per variant and merging results before the existing dedup step (`rag.py:229-237`) — the dedup-by-content-hash logic already handles overlap for free.
3. Gate this behind an env var `ENABLE_QUERY_REWRITE` (default `true`) so it can be disabled without a code change if latency becomes a problem — follow the existing pattern of `ENABLE_RAG_EVAL` in `main.py`.
4. Add a fast-path bypass: if the first-turn cache (`rag.py:270-279`) already hits, skip rewriting entirely — no point burning an extra LLM call before checking cache.

**New dependency:** none (reuses existing Groq client + fast model tier).

**Verification:** run `eval.py`'s judge (already returns faithfulness/context_relevance) before/after on a fixed set of ~10 queries against the current corpus; expect context_relevance to improve on vague/multi-part queries without regressing simple ones. This eval harness becomes the regression gate used again in Step 4.

**Actual:** implemented as planned (`rag.py:rewrite_query`), with one deliberate deviation — item 4 (skip rewriting on a first-turn cache hit) wasn't built. The response cache key is derived from `query + context`, and context only exists *after* retrieval runs, so there's no way to check the cache before rewriting without restructuring the cache itself. Not worth it for a minor cost saving.

---

## Step 2 (A2) — Confidence / groundedness gating

**Why second:** depends on Step 1 existing (rewriting reduces false-negative low-confidence flags caused by weak retrieval, not weak generation) and directly reuses `eval.py`, which currently only logs scores — this is the first step that acts on them.

**Where:** `backend/rag.py:204-304` (`get_rag_response`), `backend/eval.py` (`evaluate_rag`), `backend/main.py:41-56` (`_eval_and_update`, already calls eval async post-response for logging).

**Implementation:**
1. `evaluate_rag()` already runs faithfulness/answer_relevance/context_relevance scoring — currently fire-and-forget in `main.py`'s background task. Add a lightweight **inline** pre-check: after generation in `get_rag_response()` (`rag.py:290-293`), if `context` was empty or very short (cheap heuristic, no LLM call), append a caveat to the response rather than waiting on the full async eval.
2. For the full LLM-judge score (already computed async in `_eval_and_update`), extend it to write the faithfulness score onto the stored RAG log (`local_store.py`) and expose it via the existing `/admin/stats` endpoint (`main.py:634`) so low-faithfulness responses are visible in the admin dashboard — this is additive to what's already logged, not new plumbing.
3. Do **not** block the response on the full LLM-judge score synchronously (it already runs async for a reason — latency). Keep the inline gate cheap/heuristic-only; the LLM-judge stays a post-hoc quality signal surfaced in admin, not a runtime gate.

**Verification:** manually check the admin dashboard after a batch of test queries (including a few deliberately out-of-corpus ones) and confirm low-faithfulness responses are flagged/visible.

**Actual:** item 2 (write the async LLM-judge faithfulness score onto the log row, surface via `/admin/stats`) turned out to already exist in the codebase — `local_store.py`'s schema, `rag_logger.update_eval_scores()`, and `admin.py`'s aggregation were already wired end-to-end, just not mentioned as such anywhere. Only item 1 needed building: `rag.py:_append_caveat_if_low_context()` appends a groundedness note to the response whenever retrieval returned zero chunks, applied after the raw response is stored to conversation history (so the caveat itself never becomes part of what the model "remembers" saying).

---

## Step 3 (A3) — Chunking strategy tuning

**Why third:** independent of Steps 1-2, but must land before Step 5 (broader ingestion) — new file-type loaders (DOCX/XLSX/CSV) should use whatever chunking strategy is decided here, not the old fixed-size splitter, to avoid a second migration.

**Where:** `backend/vectorstore.py:455-480` (`_chunk_documents`), which currently uses `RecursiveCharacterTextSplitter` at fixed sizes (800 chars PDF, 600 chars MD).

**Implementation:**
1. Replace fixed `chunk_size` splitting with structure-aware splitting: for PDF, split on paragraph/heading boundaries first (already have page-level granularity and a structure extractor at `vectorstore.py:315`), falling back to `RecursiveCharacterTextSplitter` only for pages that remain oversized after that.
2. Keep the existing "never split structure chunks" rule (`vectorstore.py:463-465`) — that's correct today, don't touch it.
3. This is a **re-indexing** change: after landing, existing users need `POST /documents/refresh` (`main.py:517`) to re-chunk their corpus with the new splitter — call this out in the PR description, it's not automatic.

**Verification:** same eval harness from Step 1, run against a long-form PDF in the corpus; compare context_relevance before/after re-indexing.

**Actual:** implemented as planned — `vectorstore.py:_split_into_paragraphs`/`_looks_like_heading`/`_pack_paragraphs` replace the flat `RecursiveCharacterTextSplitter` for long PDF pages, packing whole paragraphs up to ~800 chars and always starting a new chunk at a detected heading rather than folding a topic shift onto the previous chunk. Step 5 later reused this via a shared `_chunk_prose_document()` helper for DOCX/HTML too. **Action needed**: this re-chunks PDFs, so already-indexed corpora need `POST /documents/refresh` to pick it up — not automatic.

---

## Step 4 (A7) — Retrieval-quality regression gate in CI

**Why fourth:** Steps 1 and 3 just changed retrieval behavior twice; before touching anything else, lock in a regression test so future changes (including Steps 8-10) don't silently degrade quality.

**Where:** new file `backend/tests/test_retrieval_quality.py`, alongside the existing `backend/tests/` directory (pytest already a dependency per `AUDIT_REPORT.md` finding).

**Implementation:**
1. Define a fixed set of ~10-15 query/expected-source pairs against a small fixture corpus (a couple of test PDFs already used in `backend/tests/` if any exist, otherwise add 1-2 minimal fixtures).
2. Run `evaluate_rag()` per query, assert scores don't drop below a floor (e.g. faithfulness ≥ 0.6) — this is a regression floor, not a strict pass/fail on absolute quality.
3. Wire into the existing CI test job (`ROADMAP.md` item 6, already done) as an additional test file — no new CI infrastructure needed, just a new test.

**Verification:** intentionally break something trivial (e.g. drop the reranker) locally and confirm the test fails.

**Actual: reverted by request.** This was implemented once — `backend/tests/test_retrieval_quality.py` (11 query/expected-source cases against a 3-document fixture corpus, using the real hybrid retriever + reranker in an isolated temp ChromaDB dir) plus a new `.github/workflows/backend-tests.yml`, since no CI config existed anywhere in the repo despite `ROADMAP.md` claiming otherwise — then explicitly reverted. Neither the test file nor the workflow exists in the repo currently.

---

## Step 5 (B1) — Broader document ingestion (DOCX, XLSX/CSV, HTML)

**Why fifth:** self-contained, doesn't need auth or storage changes, and now benefits from the improved chunking (Step 3) and gets regression-tested for free (Step 4).

**Where:** `backend/vectorstore.py:74` (`SUPPORTED_EXTENSIONS`), `load_documents()` (`vectorstore.py:419-453`), `add_document()`/`remove_document()` (`vectorstore.py:533-593`), and the equivalent extension allowlist in the frontend's `documents-panel.tsx` upload validation.

**Implementation:**
1. **DOCX and HTML** are straightforward — follow the exact pattern of `_load_pdf`/`_load_markdown` (`vectorstore.py:202`, `299`): add `_load_docx()` and `_load_html()` methods returning `List[Document]`, add `.docx`/`.html` to `SUPPORTED_EXTENSIONS`, wire into the `if ext == ...` branch in `load_documents()` (`vectorstore.py:437-447`) and `add_document()`. Use `python-docx` for DOCX, `beautifulsoup4` (likely already a transitive dep via other libs, otherwise add) for HTML.
2. **XLSX/CSV is a different capability, not just another loader** — tabular data doesn't chunk well as prose. Two options, pick one:
   - **Simple (recommended for this pass):** flatten each row (or a windowed group of rows) into a text chunk with column headers repeated per chunk, so BM25/semantic search can still find it — same `Document` + chunking pipeline as everything else, no new query path.
   - **Structured (defer to Step 9, agentic tool-use):** keep tabular files out of the vector index entirely and instead expose them via a "query this spreadsheet" tool once Step 9 lands. Don't build both — the simple approach ships now; the tool-based approach is the natural follow-up once tool-calling exists.
3. Update frontend's upload allowlist and `MAX_DOCUMENT_SIZE_MB` messaging to mention the new types.
4. Add each new type to the structure-extraction dispatch (`vectorstore.py:439-450`) only if it makes sense — DOCX has headings worth extracting as a structure chunk (same as PDF/PPTX); flattened spreadsheet rows don't.

**Verification:** upload one file of each new type through the existing `/documents/upload` endpoint, confirm it's retrievable via a targeted query, confirm `/documents/list` and delete work unchanged.

**Actual:** implemented as planned, including the "simple" tabular approach (row-windowed chunks, 20 rows/chunk, header repeated per chunk). Two things not called out in the original plan:
- Two *additional* hardcoded extension allowlists existed beyond `vectorstore.py`'s `SUPPORTED_EXTENSIONS` — `document_store.py:ALLOWED_EXTENSIONS` and `main.py:SUPPORTED_UPLOAD_EXTENSIONS` — both gate uploads *before* they ever reach the loader code, so both needed updating too or new file types would be rejected at the API boundary.
- Added `python-docx`, `beautifulsoup4`, `openpyxl` to `requirements.txt` (none were already a dependency, transitive or otherwise).

---

## Step 6 (B3) — Inline grounded citations

**Why sixth:** builds directly on the existing `_format_chunk()` (`rag.py:128`) and `sources` list plumbing (`rag.py:260`, already flows through `pipeline.py:79-86` to the frontend at `ChatPage.tsx:223-227`) — this step is "make what's already tracked visible per-claim," not new retrieval logic.

**Where:** `backend/rag.py:128-166` (`_format_chunk`, `_sanitize_and_filter_images`), `backend/main.py` chat endpoints (`main.py:250-353`), `frontend/src/pages/ChatPage.tsx` (message rendering, `~223-290`).

**Implementation:**
1. Backend: number the retrieved chunks (`docs` list in `get_rag_response`, `rag.py:225-263`) and instruct the LLM (via the system prompt built in `_wrap_chain`/`_build_rag_chain` in `vectorstore.py:150-201`) to cite `[n]` inline when using a chunk's content — same pattern already used for image markdown (`_IMAGE_MD_RE` at `rag.py:150` shows the codebase already parses/validates LLM-emitted inline markers, so this follows precedent).
2. Add a `_sanitize_citations()` function mirroring `_sanitize_and_filter_images` (`rag.py:154-166`) — strip any `[n]` that doesn't correspond to an actual numbered source (hallucination guard, same reasoning as the existing image-id validation).
3. Extend the `sources` field in the response payload from `List[str]` (filenames) to a structured list `[{index, filename, page/slide, chunk_preview}]` so the frontend can render `[1]` as a clickable chip linking to the right source entry — this is a payload shape change, update `pipeline.py:79-86` and the frontend types in `services/api.ts` together.
4. Frontend: in `ChatPage.tsx`, parse `[n]` markers in the rendered markdown (already rendering markdown per `ROADMAP.md` item 11 "Done") and link them to the existing source-preview UI, keyed by index instead of a flat list.

**Verification:** ask a question spanning 2+ source chunks, confirm citation numbers in the response match the right source preview entries; ask a question with no good context and confirm no citations are hallucinated (reuse Step 4's regression harness with a citation-accuracy check added).

**Actual:** the plan's framing — "make what's already tracked visible per-claim" — turned out to be wrong: there was no existing source-preview UI to extend. `sources` was captured into `Message` state but never rendered anywhere in the frontend, and `getDocumentChunks()`/`GET /documents/chunks` was dead, uncalled code, despite the README listing "Source Preview" as a shipped feature. This step built the UI from scratch instead of extending one.

Otherwise implemented as planned: `_build_source_citations()` replaces the old deduped-by-filename flat list with one structured `{index, filename, page, slide, preview}` entry per chunk; `_sanitize_citations()` strips hallucinated `[n]` markers; the citation-numbered context + prompt instruction lives in `vectorstore.py:_wrap_chain`. Frontend renders `[n]` as clickable badges (via a markdown-link rewrite trick) linking to an expandable source-chip strip with the chunk preview text. Verified live against the real indexed corpus, not just unit tests — the model correctly cited only the chunks it actually used and never fabricated a citation for an unused one.

**Follow-up fix (same step, done after initial completion):** the streaming chat path originally sent raw LLM output chunk-by-chunk and only sanitized the *aggregate* response in the final SSE `done` event — meaning a hallucinated `[n]` or invalid image marker could flash on screen before cleanup. Fixed with `rag.py:_sanitize_stream_buffer()`/`_find_stream_cut()`: since retrieval (and therefore the valid citation/image-id set) is known before streaming starts, each chunk is now validated incrementally, holding back only the handful of characters that could still be an in-progress `[n]` or `![...]()` marker — everything else (including brackets/`!` that are provably *not* forming a marker) streams immediately with no added latency. Verified against a live stream: reconstructed the actual SSE chunks and confirmed every citation/image marker arrived as a single, complete, pre-validated unit, never split raw across a chunk boundary.

---

## Step 7 (A6) — Durable conversation storage

**Why seventh:** placed here because Step 8 (auth) needs a real relational store for user/session ownership anyway — do the SQLite/Postgres migration once, for both durability and auth, instead of twice.

**Where:** `backend/memory.py` (Redis/in-memory session history), `backend/local_store.py` (existing SQLite table for RAG logs — the DB file/connection pattern to extend, not replace).

**Implementation:**
1. Add a `conversations`/`messages` table to the existing SQLite store in `local_store.py` (it already has a working SQLite connection pattern for `raglogs` — reuse it, don't add a new DB dependency yet).
2. In `memory.py`'s `get_session_history()` (`memory.py:40-65`), keep Redis as the hot-path cache (TTL 1hr, unchanged) but persist each turn to the new SQLite table as well — write-through, not a replacement. On Redis miss/eviction, hydrate from SQLite instead of starting empty.
3. This is the natural point to also add a `GET /conversations/{session_id}` endpoint for history recovery after reload, closing the "lost on Redis eviction" gap noted in the verification findings.

**Verification:** kill Redis locally (`docker compose stop redis` or equivalent), confirm an in-progress conversation's history is still recoverable from SQLite.

---

## Step 8 (B4) — Real user auth + per-user document libraries

**Why eighth:** this is the prerequisite every remaining Track B item (cross-document synthesis scoped per-user, conversation export tied to an owner, "chat with your history" needing to know whose history) implicitly needs. Deliberately sequenced after storage (Step 7) so the user/session tables land in the same migration pass.

**Where:** `backend/main.py` (currently zero auth — `_validate_session_id` at `main.py:57` only checks length, no identity), new `backend/auth.py`, the SQLite/Postgres store extended in Step 7.

**Implementation:**
1. Add a minimal `users` table (email + hashed password, or defer to an OAuth provider if preferred — this needs a product decision, flag it explicitly rather than assuming) to the same store extended in Step 7.
2. Add a lightweight session-token auth (JWT or signed cookie) — `fastapi`'s own `Depends()` pattern is already used for the admin key (`main.py:102-112`, `_require_admin_key`), so a `_require_user` dependency follows the same shape.
3. Bind `session_id` to a real `user_id` instead of the current unauthenticated client-generated string (`main.py:57-59`); scope document uploads (`main.py:555-579`) and conversation history (Step 7's tables) to the owning user.
4. Frontend: add a login/signup flow — this is the first step in this plan that touches frontend auth state, budget it as its own sub-effort.

**Note:** this step is a genuine product decision (single-tenant → multi-tenant is a scope change, not just an engineering task) — confirm direction with the user before starting, don't assume it's wanted just because it unblocks later steps.

**Verification:** two separate logged-in users each upload different documents, confirm neither sees the other's documents/conversations; confirm unauthenticated requests are rejected.

---

## Step 9 (B2) — Agentic / tool-use layer

**Why ninth:** consumes Step 1's query-rewriting infra (a tool-routing decision is a natural extension of "how should this query be handled"), Step 6's citation format (tool results need to be cited the same way retrieved chunks are), and Step 5's deferred structured-tabular-query option.

**Where:** new `backend/tools.py`, `backend/rag.py`'s `get_rag_response()` as the routing point.

**Implementation:**
1. Add Groq function-calling (already supported by the Groq SDK already in use) with an initial tool set: `query_spreadsheet(filename, question)` (closing the Step 5 deferred item for XLSX/CSV), and optionally a calculator tool.
2. Before the retrieval step in `get_rag_response()`, add a routing decision: does this query need a tool, or standard RAG retrieval? Reuse the fast-model-tier pattern from `pick_model()` (`rag.py:69-79`) for this classification to keep it cheap.
3. Tool results get formatted and cited using the same `_format_chunk`/citation numbering from Step 6, so tool-sourced facts are visually indistinguishable from document-sourced ones in terms of traceability.

**Verification:** ask a question that requires the spreadsheet tool vs. a normal document question in the same session, confirm correct routing and that citations still resolve correctly for both paths.

---

## Step 10 (B5) — Cross-document synthesis mode

**Why last:** the highest-level feature, explicitly depends on citations (Step 6) to make a multi-document answer legible, and benefits from tool-use (Step 9) if synthesis needs structured data alongside prose documents.

**Where:** `backend/rag.py` (new retrieval mode), `frontend/src/pages/ChatPage.tsx` (UI entry point — e.g. a "compare documents" affordance instead of inferring intent from free text).

**Implementation:**
1. Add explicit multi-document selection in the frontend (document panel already lists documents via `/documents/list`) — let the user pick 2+ documents and a comparison prompt, rather than relying on the LLM to infer "compare X and Y" from a single free-text query.
2. Backend: a dedicated retrieval path that runs the existing hybrid retriever (`get_retriever()`, `vectorstore.py:645`) scoped `where={"source": {"$in": [selected_filenames]}}` per document, so results aren't accidentally cross-contaminated the way default top-10 retrieval can be.
3. Reuse Step 6's citation format per-document (e.g. `[1a]`/`[2a]` grouping) so the synthesis answer's provenance stays traceable across documents.

**Verification:** compare two documents with a shared topic, confirm the answer draws from both (not just whichever ranked higher by default) and citations correctly attribute claims to the right source document.

---

## Summary dependency chain

```
Step 1 (query rewrite) ──┬──> Step 2 (confidence gate)
                          └──> Step 4 (regression CI) <── Step 3 (chunking)
Step 3 (chunking) ───────────> Step 5 (broader ingestion)
Step 5 ───────────────────┬──> Step 9 (tool-use, spreadsheet tool)
Step 6 (citations) ────────┼──> Step 9 (cited tool results)
                            └──> Step 10 (cross-doc synthesis)
Step 7 (durable storage) ────> Step 8 (auth) ──> (unblocks any future multi-user Track B item)
Step 9 + Step 6 ──────────────> Step 10
```

Steps 1-4 and 5-6 can each be built and shipped independently before starting the 7→8 storage/auth pair; 9 and 10 are the only hard-dependent tail.
