import asyncio
import os
import re
import time
import json
import uuid
from fastapi import BackgroundTasks, Depends, FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.exceptions import RequestValidationError
from typing import Optional
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pipeline import PipelineOrchestrator, QueryRefiner, TranscriptionError
from rag import initialize_rag, refresh_documents, get_rag_response, rag_system as _rag_ref
from rag_logger import log_rag_call, update_eval_scores, log_feedback
from eval import evaluate_rag
from blob_sync import upload_document, delete_document

from contextlib import asynccontextmanager

load_dotenv()


def _eval_and_update(log_id: str, partition_key: str, query: str, context: str, answer: str):
    scores = evaluate_rag(query, context, answer)
    update_eval_scores(log_id, partition_key, scores)

MAX_MESSAGE_LENGTH = int(os.environ.get("MAX_MESSAGE_LENGTH", 1000))
MAX_TTS_LENGTH = int(os.environ.get("MAX_TTS_LENGTH", 5000))
MAX_AUDIO_SIZE_MB = int(os.environ.get("MAX_AUDIO_SIZE_MB", 10))
MAX_SESSION_ID_LENGTH = 128
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "")

pipeline = None
_refresh_lock = asyncio.Lock()


def _validate_session_id(session_id: str) -> None:
    if len(session_id) > MAX_SESSION_ID_LENGTH:
        raise HTTPException(status_code=400, detail=f"session_id too long (max {MAX_SESSION_ID_LENGTH} chars)")


async def require_admin_key(request: Request) -> None:
    """Dependency: require X-API-Key header when ADMIN_API_KEY env var is set."""
    if not ADMIN_API_KEY:
        return
    key = request.headers.get("X-API-Key", "")
    if key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── App lifecycle ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline
    print("=" * 60 + "\nStarting Multilingual AI Chat Server\n" + "=" * 60)
    try:
        initialize_rag()
    except Exception as e:
        print(f"⚠️ RAG initialization failed: {e}")

    pipeline = PipelineOrchestrator()
    print("\n✓ Server ready!\n" + "=" * 60)
    yield
    print("Shutting down...")


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
    print(f"Validation error: {exc.errors()}")
    errors = json.loads(json.dumps(exc.errors(), default=str))
    return JSONResponse(status_code=422, content={"detail": errors})

# CORS configuration — set ALLOWED_ORIGINS env var as comma-separated list.
# Also allows all *.azurecontainerapps.io origins automatically.
_ALLOWED_ORIGINS_ENV = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:8081,http://localhost:8080,http://localhost:19006,http://127.0.0.1:8081,http://127.0.0.1:19006"
).split(",")

ALLOWED_ORIGINS = _ALLOWED_ORIGINS_ENV
print(f"CORS static origins: {ALLOWED_ORIGINS}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://[\w.-]+\.azurecontainerapps\.io",
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
        "endpoints": ["/chat/text", "/chat/audio", "/feedback", "/health", "/documents/refresh"],
    }


@app.get("/health")
async def health():
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
        r = redis_lib.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379"))
        r.ping()
        redis_status = "connected"
    except Exception:
        redis_status = "unavailable (using in-memory fallback)"

    return {
        "status": "healthy",
        "vector_store": vs_status,
        "chunk_count": chunk_count,
        "redis": redis_status,
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
    from rag import rag_system, initialize_rag, _build_context

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
            sources = list(set(d.metadata.get("source", "Unknown") for d in docs))
            context = _build_context([d.page_content for d in docs]) if docs else "No relevant context found."

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
                print(f"[stream_response] LLM streaming error: {type(e).__name__}: {e}")
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
        print(f"Error in text_chat: {e}")
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

    print(f"Audio received: {file.filename}")

    try:
        start = time.time()
        result = pipeline.process_audio(
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
        print(f"Error in audio_chat: {e}")
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
        print(f"TTS Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/documents/refresh", dependencies=[Depends(require_admin_key)])
@limiter.limit("5/minute")
async def refresh_docs(request: Request):
    try:
        async with _refresh_lock:
            await asyncio.to_thread(refresh_documents)
        return JSONResponse(content={"success": True, "message": "Documents refreshed successfully"})
    except HTTPException:
        raise
    except Exception as e:
        print(f"Refresh Error: {e}")
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
        print(f"List documents error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/documents/upload", dependencies=[Depends(require_admin_key)])
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
            await asyncio.to_thread(refresh_documents)
        return JSONResponse(content={"success": True, "filename": file.filename, "message": f"'{file.filename}' uploaded and indexed successfully"})
    except HTTPException:
        raise
    except Exception as e:
        print(f"Upload Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/documents/{filename}", dependencies=[Depends(require_admin_key)])
async def delete_doc(filename: str):
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid filename")
    try:
        delete_document(filename)
        async with _refresh_lock:
            await asyncio.to_thread(refresh_documents)
        return JSONResponse(content={"success": True, "message": f"'{filename}' deleted and index rebuilt"})
    except HTTPException:
        raise
    except Exception as e:
        print(f"Delete Error: {e}")
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
        print(f"Chunks Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("Starting Multilingual AI Chat Server")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
