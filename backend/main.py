import asyncio
import logging
import os
import re
import time
import json
import uuid
from fastapi import BackgroundTasks, Depends, FastAPI, UploadFile, File, Form, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.exceptions import RequestValidationError
from typing import Optional
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pipeline import PipelineOrchestrator, QueryRefiner, TranscriptionError
from rag import initialize_rag, refresh_documents, get_rag_response, index_document, deindex_document, rerank_documents, rag_system as _rag_ref
from rag_logger import log_rag_call, update_eval_scores, log_feedback
from eval import evaluate_rag
from blob_sync import upload_document, delete_document
from vision import describe_image
import admin as admin_logs

from contextlib import asynccontextmanager

load_dotenv()

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ringo")


ENABLE_RAG_EVAL = os.environ.get("ENABLE_RAG_EVAL", "false").lower() == "true"


def _eval_and_update(log_id: str, partition_key: str, query: str, context: str, answer: str):
    if not ENABLE_RAG_EVAL:
        return
    scores = evaluate_rag(query, context, answer)
    update_eval_scores(log_id, partition_key, scores)

MAX_MESSAGE_LENGTH = int(os.environ.get("MAX_MESSAGE_LENGTH", 1000))
MAX_TTS_LENGTH = int(os.environ.get("MAX_TTS_LENGTH", 5000))
MAX_AUDIO_SIZE_MB = int(os.environ.get("MAX_AUDIO_SIZE_MB", 10))
MAX_IMAGE_SIZE_MB = int(os.environ.get("MAX_IMAGE_SIZE_MB", 8))
MAX_SESSION_ID_LENGTH = 128

pipeline = None
_refresh_lock = asyncio.Lock()


def _validate_session_id(session_id: str) -> None:
    if len(session_id) > MAX_SESSION_ID_LENGTH:
        raise HTTPException(status_code=400, detail=f"session_id too long (max {MAX_SESSION_ID_LENGTH} chars)")


def _require_admin_key(x_admin_key: Optional[str] = Header(None)) -> None:
    """Gate for /admin/* routes — logs contain raw query/response text, so this
    is not exposed without an operator-configured key."""
    configured_key = os.environ.get("ADMIN_API_KEY")
    if not configured_key:
        raise HTTPException(status_code=503, detail="Admin dashboard not configured (ADMIN_API_KEY unset)")
    if x_admin_key != configured_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")


# ── App lifecycle ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline
    logger.info("Starting Multilingual AI Chat Server")
    try:
        initialize_rag()
    except Exception as e:
        logger.warning("RAG initialization failed: %s", e)

    pipeline = PipelineOrchestrator()
    logger.info("Server ready")
    yield
    logger.info("Shutting down...")


# Verify API key early
if not os.environ.get("GROQ_API_KEY"):
    raise ValueError("GROQ_API_KEY missing!")

# Initialize rate limiter — skip OPTIONS (CORS preflight) requests
def _rate_limit_key(request: Request) -> str:
    if request.method == "OPTIONS":
        return None  # type: ignore[return-value]  # None exempts the request
    return get_remote_address(request)

limiter = Limiter(key_func=_rate_limit_key)

app = FastAPI(title="Multilingual AI Chat API", version="2.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.info("Validation error: %s", exc.errors())
    errors = json.loads(json.dumps(exc.errors(), default=str))
    return JSONResponse(status_code=422, content={"detail": errors})

# CORS configuration — set ALLOWED_ORIGINS env var as comma-separated list.
# ALLOWED_ORIGIN_REGEX narrows which *.azurecontainerapps.io subdomains are trusted;
# default only matches this project's "adk-*" app naming, not any tenant on the shared domain.
_ALLOWED_ORIGINS_ENV = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:8081,http://localhost:8080,http://localhost:19006,http://127.0.0.1:8081,http://127.0.0.1:19006"
).split(",")

ALLOWED_ORIGINS = _ALLOWED_ORIGINS_ENV
ALLOWED_ORIGIN_REGEX = os.environ.get(
    "ALLOWED_ORIGIN_REGEX",
    r"https://adk-[\w-]+\.azurecontainerapps\.io",
)
logger.info("CORS static origins: %s", ALLOWED_ORIGINS)
logger.info("CORS origin regex: %s", ALLOWED_ORIGIN_REGEX)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=ALLOWED_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "status": "healthy",
        "service": "Multilingual AI Chat API",
        "version": "2.0.0",
        "endpoints": ["/chat/text", "/chat/audio", "/feedback", "/health", "/health/live", "/documents/refresh"],
    }


@app.get("/health/live")
async def health_live():
    """Liveness probe — process is up. No dependency checks (Container Apps/k8s should
    restart the container based on this, not on a downstream outage it can't fix)."""
    return {"status": "alive"}


_groq_check_cache: dict = {"ok": None, "checked_at": 0.0}
_GROQ_CHECK_TTL_SECONDS = 30


def _check_groq_reachable() -> bool:
    """Lightweight Groq reachability check (list models, no completion tokens spent),
    cached briefly so frequent readiness probes don't hammer the API."""
    now = time.time()
    if _groq_check_cache["ok"] is not None and now - _groq_check_cache["checked_at"] < _GROQ_CHECK_TTL_SECONDS:
        return _groq_check_cache["ok"]
    try:
        from groq import Groq
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"), timeout=5.0)
        client.models.list()
        _groq_check_cache.update(ok=True, checked_at=now)
    except Exception as e:
        logger.warning("Groq reachability check failed: %s", e)
        _groq_check_cache.update(ok=False, checked_at=now)
    return _groq_check_cache["ok"]


@app.get("/health")
async def health():
    """Readiness probe — checks downstream dependencies (vector store, Redis, Groq)."""
    from rag import rag_system
    chunk_count = 0
    vs_status = "uninitialized"

    if rag_system and rag_system.vectorstore:
        try:
            chunk_count = rag_system.vectorstore._collection.count()
            vs_status = "ready" if chunk_count > 0 else "empty"
        except Exception:
            vs_status = "error"

    redis_status = "unknown"
    try:
        import redis as redis_lib
        r = redis_lib.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379"),
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        r.ping()
        redis_status = "connected"
    except Exception:
        redis_status = "unavailable (using in-memory fallback)"

    groq_status = "reachable" if _check_groq_reachable() else "unreachable"

    return {
        "status": "healthy",
        "vector_store": vs_status,
        "chunk_count": chunk_count,
        "redis": redis_status,
        "groq": groq_status,
    }


@app.post("/chat/text")
@limiter.limit("10/minute")
async def text_chat(
    request: Request,
    background_tasks: BackgroundTasks,
    message: str = Form(...),
    language: Optional[str] = Form(None),
    stream: bool = Form(False),
    session_id: str = Form("default"),
):
    from rag import rag_system, initialize_rag

    if len(message) > MAX_MESSAGE_LENGTH:
        raise HTTPException(status_code=413, detail=f"Message too long (max {MAX_MESSAGE_LENGTH} characters)")
    _validate_session_id(session_id)

    if stream:
        async def stream_response():
            if not rag_system:
                await asyncio.to_thread(initialize_rag)

            lang = QueryRefiner().detect_language(message) if not language else language
            lang_map = {"en": "English", "hi": "Hindi", "ta": "Tamil", "te": "Telugu"}
            lang_name = lang_map.get(lang, "English")

            yield f"data: {json.dumps({'type': 'language', 'value': lang})}\n\n"

            if not rag_system.vectorstore:
                yield f"data: {json.dumps({'type': 'content', 'value': 'No documents indexed.'})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'value': '', 'sources': []})}\n\n"
                return

            retriever = rag_system.get_retriever()
            docs = await asyncio.to_thread(retriever.invoke, message)
            docs = await asyncio.to_thread(rerank_documents, message, docs)
            sources = list(set(d.metadata.get("source", "Unknown") for d in docs))
            context = "\n\n".join(d.page_content for d in docs) if docs else "No relevant context found."

            yield f"data: {json.dumps({'type': 'sources', 'value': sources})}\n\n"

            full_response = ""
            try:
                async for chunk in rag_system.rag_chain_with_history.astream(
                    {"context": context, "question": message, "language": lang_name},
                    config={"configurable": {"session_id": session_id}},
                ):
                    if not isinstance(chunk, str):
                        continue
                    full_response += chunk
                    yield f"data: {json.dumps({'type': 'content', 'value': chunk})}\n\n"
            except Exception as e:
                logger.error("[stream_response] LLM streaming error: %s: %s", type(e).__name__, e)
                yield f"data: {json.dumps({'type': 'content', 'value': 'Sorry, an error occurred.'})}\n\n"

            log_id, partition_key = log_rag_call(message, full_response, sources, lang, 0, context)
            asyncio.get_running_loop().run_in_executor(
                None, _eval_and_update, log_id, partition_key, message, context, full_response
            )
            yield f"data: {json.dumps({'type': 'log_id', 'value': log_id, 'log_date': partition_key})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'value': '', 'sources': sources})}\n\n"

        return StreamingResponse(stream_response(), media_type="text/event-stream")

    # Non-streaming
    try:
        start = time.time()
        result = await asyncio.to_thread(pipeline.process_text, message, language, session_id=session_id)
        latency_ms = int((time.time() - start) * 1000)
        context = result.pop("context", "")
        log_id, partition_key = log_rag_call(
            message, result["response"], result.get("sources", []),
            result.get("language", "en"), latency_ms, context
        )
        background_tasks.add_task(
            _eval_and_update, log_id, partition_key, message, context, result["response"]
        )
        result["log_id"] = log_id
        result["log_date"] = partition_key
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in text_chat: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/chat/image")
@limiter.limit("10/minute")
async def image_chat(
    request: Request,
    image: UploadFile = File(...),
    message: str = Form(""),
    session_id: str = Form("default"),
):
    """Multimodal image + optional text question, answered directly by a vision-capable
    Groq model. Bypasses document retrieval — the RAG chain/prompts are plain-text only."""
    _validate_session_id(session_id)

    if len(message) > MAX_MESSAGE_LENGTH:
        raise HTTPException(status_code=413, detail=f"Message too long (max {MAX_MESSAGE_LENGTH} characters)")
    if image.content_type and not image.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="File must be an image")

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(image_bytes) > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Image too large (max {MAX_IMAGE_SIZE_MB}MB)")

    logger.info("Image received: %s", image.filename)

    try:
        response = await asyncio.to_thread(
            describe_image, image_bytes, image.content_type or "image/jpeg", message
        )
        return JSONResponse(content={"response": response, "sources": []})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in image_chat: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/chat/audio")
@limiter.limit("10/minute")
async def audio_chat(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    stream: bool = Form(False),
    session_id: str = Form("default"),
):
    _validate_session_id(session_id)

    # Validate before reading body so client gets a proper 4xx, not 500
    if file.content_type and not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=415, detail="File must be an audio file")

    audio_bytes = await file.read()

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(audio_bytes) > MAX_AUDIO_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Audio file too large (max {MAX_AUDIO_SIZE_MB}MB)")

    logger.info("Audio received: %s", file.filename)

    try:
        start = time.time()
        result = await asyncio.to_thread(
            pipeline.process_audio,
            audio_bytes, file.content_type or "audio/wav", language,
            return_audio=False, session_id=session_id
        )
        latency_ms = int((time.time() - start) * 1000)
        context = result.pop("context", "")
        query = result.get("query", "")
        log_id, partition_key = log_rag_call(
            query, result["response"],
            result.get("sources", []), result.get("language", "en"), latency_ms, context
        )
        background_tasks.add_task(
            _eval_and_update, log_id, partition_key, query, context, result["response"]
        )
        result["log_id"] = log_id
        result["log_date"] = partition_key
        return JSONResponse(content=result)
    except TranscriptionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in audio_chat: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


_LOG_ID_RE = re.compile(r'^[\w\-]{1,256}$')
_LOG_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')

@app.post("/feedback")
@limiter.limit("30/minute")
async def submit_feedback(
    request: Request,
    log_id: str = Form(...),
    log_date: str = Form(...),
    rating: int = Form(...),
):
    if rating not in (0, 1):
        raise HTTPException(status_code=400, detail="rating must be 0 or 1")
    if not _LOG_ID_RE.match(log_id):
        raise HTTPException(status_code=400, detail="Invalid log_id")
    if not _LOG_DATE_RE.match(log_date):
        raise HTTPException(status_code=400, detail="Invalid log_date format (expected YYYY-MM-DD)")
    log_feedback(log_id, log_date, rating)
    return JSONResponse(content={"success": True})


@app.post("/tts/generate")
@limiter.limit("20/minute")
async def generate_tts(
    request: Request,
    text: str = Form(...),
    language: str = Form("en"),
):
    if len(text) > MAX_TTS_LENGTH:
        raise HTTPException(status_code=413, detail=f"Text too long (max {MAX_TTS_LENGTH} characters)")
    try:
        retrieval_result = {"response": text, "language": language}
        audio_data = pipeline.response_generator.generate_audio(retrieval_result)
        return JSONResponse(content={
            "success": True,
            "audio_data": audio_data,
            "audio_available": audio_data is not None,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error("TTS Error: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/documents/refresh")
@limiter.limit("5/minute")
async def refresh_docs(request: Request):
    try:
        async with _refresh_lock:
            await asyncio.to_thread(refresh_documents)
        return JSONResponse(content={"success": True, "message": "Documents refreshed successfully"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Refresh Error: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


SUPPORTED_UPLOAD_EXTENSIONS = {".pdf", ".pptx", ".md"}
MAX_DOCUMENT_SIZE_MB = int(os.environ.get("MAX_DOCUMENT_SIZE_MB", 20))


@app.get("/documents/list")
async def list_documents():
    from rag import rag_system
    if not rag_system or not rag_system.vectorstore:
        return JSONResponse(content={"documents": []})
    try:
        result = rag_system.vectorstore._collection.get(include=["metadatas"])
        counts: dict = {}
        for meta in result["metadatas"]:
            src = meta.get("source", "Unknown")
            doc_type = meta.get("type", "unknown")
            if src not in counts:
                counts[src] = {"filename": src, "chunks": 0, "type": doc_type}
            counts[src]["chunks"] += 1
        return JSONResponse(content={"documents": list(counts.values())})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("List documents error: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/documents/upload")
@limiter.limit("2/minute")
async def upload_doc(request: Request, file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in SUPPORTED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(SUPPORTED_UPLOAD_EXTENSIONS)}")

    data = await file.read()
    if len(data) > MAX_DOCUMENT_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large (max {MAX_DOCUMENT_SIZE_MB}MB)")
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        upload_document(file.filename, data)
        async with _refresh_lock:
            await asyncio.to_thread(index_document, file.filename)
        return JSONResponse(content={"success": True, "filename": file.filename, "message": f"'{file.filename}' uploaded and indexed successfully"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Upload Error: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/documents/{filename}")
async def delete_doc(filename: str):
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid filename")
    try:
        delete_document(filename)
        async with _refresh_lock:
            await asyncio.to_thread(deindex_document, filename)
        return JSONResponse(content={"success": True, "message": f"'{filename}' deleted and index rebuilt"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Delete Error: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/documents/chunks")
async def get_document_chunks(source: str, query: str = ""):
    if len(source) > 256:
        raise HTTPException(status_code=400, detail="source parameter too long")
    from rag import rag_system
    if not rag_system or not rag_system.vectorstore:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    try:
        if query:
            docs = rag_system.vectorstore.similarity_search(
                query, k=4, filter={"source": source}
            )
        else:
            result = rag_system.vectorstore._collection.get(
                where={"source": source}, limit=4
            )
            from langchain_core.documents import Document as LCDoc
            docs = [
                LCDoc(page_content=text, metadata=meta)
                for text, meta in zip(result["documents"], result["metadatas"])
            ]

        chunks = [
            {"text": doc.page_content, "metadata": doc.metadata}
            for doc in docs
            if doc.page_content.strip()
        ]
        return {"source": source, "chunks": chunks}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Chunks Error: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/admin/stats")
async def admin_stats(days: int = 7, _: None = Depends(_require_admin_key)):
    if days < 1 or days > 90:
        raise HTTPException(status_code=400, detail="days must be between 1 and 90")
    try:
        return await asyncio.to_thread(admin_logs.get_stats, days)
    except Exception as e:
        logger.error("Admin stats error: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/admin/logs")
async def admin_logs_list(days: int = 1, limit: int = 100, _: None = Depends(_require_admin_key)):
    if days < 1 or days > 90:
        raise HTTPException(status_code=400, detail="days must be between 1 and 90")
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
    try:
        logs = await asyncio.to_thread(admin_logs.list_logs, days, limit)
        return {"logs": logs}
    except Exception as e:
        logger.error("Admin logs error: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
