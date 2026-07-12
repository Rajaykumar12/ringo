# RAG Evaluation + Feedback — Implementation Plan

## Context

Ringo currently logs every RAG call (query, response, sources, latency) to Azure Table Storage via `rag_logger.py`, but has no way to measure response quality or collect user feedback. This plan adds:

1. **LLM-as-judge scoring** — after every response, asynchronously score faithfulness, answer relevance, and context relevance using Groq (already configured).
2. **User feedback endpoint** — `POST /feedback` so the frontend can submit a thumbs-up/down rating tied to a specific response.

No new dependencies. Uses Groq which is already wired in. Scores are logged as extra columns in the existing Azure Table rows. Eval runs as a FastAPI background task so it adds zero latency to the user response.

---

## Files to Change

### 1. New file: `backend/eval.py`

LLM-as-judge scorer using Groq. Three scoring functions, each makes one Groq call with a structured prompt that returns a float 0.0–1.0:

- `score_faithfulness(query, context, answer)` — does the answer only use what's in the context?
- `score_answer_relevance(query, answer)` — does the answer actually address the question?
- `score_context_relevance(query, context)` — were the retrieved chunks useful for this query?

Each prompt asks the judge to respond with only a number (0.0 to 1.0). Parse it, clamp it. Return `None` on any failure — never raise, so a failed eval never breaks a response.

Top-level function:
```python
def evaluate_rag(query: str, context: str, answer: str) -> dict:
    # returns {"faithfulness": float|None, "answer_relevance": float|None, "context_relevance": float|None}
```

Uses `groq` client, model `llama3-8b-8192` (fast, cheap for eval).

---

### 2. `backend/rag_logger.py`

**a) `log_rag_call` returns `(log_id, partition_key)` tuple** and gains optional fields:
```python
def log_rag_call(query, response, sources, language, latency_ms, context="") -> tuple[str, str]:
```
Adds `context` (truncated to 2000 chars) to the Table entity. Returns UUID and partition date even when Azure is not configured.

**b) New `update_eval_scores(log_id, partition_key, scores)`**
Upserts faithfulness, answer_relevance, context_relevance onto an existing row.

**c) New `log_feedback(log_id, partition_key, rating)`**
Upserts `user_rating` (0 or 1) onto an existing row.

---

### 3. `backend/rag.py` — minor

`get_rag_response` adds `context` to its return dict:
```python
return {"response": response, "sources": sources, "context": context}
```

---

### 4. `backend/main.py`

**a)** Thread `context` through to `log_rag_call` in both streaming and non-streaming paths.

**b)** Add `BackgroundTasks` param to `/chat/text` and `/chat/audio`. After logging, fire:
```python
background_tasks.add_task(_run_eval_and_update, log_id, partition_key, query, context, response)
```

**c)** Return `log_id` and `log_date` in all chat responses.

**d)** New endpoint:
```python
@app.post("/feedback")
async def submit_feedback(log_id: str = Form(...), log_date: str = Form(...), rating: int = Form(...)):
    # rating: 1 = helpful, 0 = not helpful
    log_feedback(log_id, log_date, rating)
    return {"success": True}
```

---

## Eval Prompt Design

**Faithfulness:**
```
Given this context: {context}
And this answer: {answer}
Score 0.0 to 1.0: how much does the answer rely only on the context (1.0 = entirely grounded, 0.0 = ignores context).
Respond with only a number.
```

**Answer relevance:**
```
Question: {query}
Answer: {answer}
Score 0.0 to 1.0: how well does the answer address the question.
Respond with only a number.
```

**Context relevance:**
```
Question: {query}
Context: {context}
Score 0.0 to 1.0: how relevant is this context to answering the question.
Respond with only a number.
```

---

## Verification

1. Start backend: `cd backend && uvicorn main:app --reload`
2. POST to `/chat/text` — response should include `log_id` and `log_date`
3. Check Azure Table `raglogs` — row should have `faithfulness`, `answer_relevance`, `context_relevance` after a few seconds
4. POST to `/feedback` with the returned `log_id`, `log_date`, and `rating=1` — returns `{"success": true}`
5. Check same row — should have `user_rating: 1`
6. With no Azure connection string set, everything should work silently with no crash
