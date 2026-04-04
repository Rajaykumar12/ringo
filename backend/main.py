import os
import time
import json
import uuid
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.exceptions import RequestValidationError
from typing import Optional
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pipeline import PipelineOrchestrator, QueryRefiner
from rag import initialize_rag, refresh_documents, get_rag_response, rag_system as _rag_ref
from rag_logger import log_rag_call
from blob_sync import upload_document, delete_document

from contextlib import asynccontextmanager

load_dotenv()

MAX_MESSAGE_LENGTH = int(os.environ.get("MAX_MESSAGE_LENGTH", 1000))
MAX_AUDIO_SIZE_MB = int(os.environ.get("MAX_AUDIO_SIZE_MB", 10))

pipeline = None


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

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Multilingual AI Chat API", version="2.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"Validation error: {exc.errors()}")
    # exc.errors() may contain non-serializable objects (e.g. ValueError in ctx)
    errors = json.loads(json.dumps(exc.errors(), default=str))
    return JSONResponse(status_code=422, content={"detail": errors})

# CORS configuration - configurable via environment variable
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:8081,http://localhost:8080,http://localhost:19006,http://127.0.0.1:8081,http://127.0.0.1:19006").split(",")
print(f"CORS allowed origins: {ALLOWED_ORIGINS}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
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
        "endpoints": ["/chat/text", "/chat/audio", "/health", "/documents/refresh"],
    }


@app.get("/health")
async def health():
    """[Medium #10] Real health endpoint — reports actual vector store state."""
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
    message: str = Form(...),
    language: Optional[str] = Form(None),
    stream: bool = Form(False),
    session_id: str = Form("default"),
):
    from rag import rag_system, initialize_rag
    
    # Input validation
    if len(message) > MAX_MESSAGE_LENGTH:
        raise HTTPException(status_code=413, detail=f"Message too long (max {MAX_MESSAGE_LENGTH} characters)")

    # [High #6] Real SSE streaming
    if stream:
        async def stream_response():
            if not rag_system:
                initialize_rag()

            lang = QueryRefiner().detect_language(message) if not language else language
            lang_map = {"en": "English", "hi": "Hindi", "ta": "Tamil", "te": "Telugu"}
            lang_name = lang_map.get(lang, "English")

            yield f"data: {json.dumps({'type': 'language', 'value': lang})}\n\n"

            if not rag_system.vectorstore:
                yield f"data: {json.dumps({'type': 'content', 'value': 'No documents indexed.'})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'value': ''})}\n\n"
                return

            retriever = rag_system.get_retriever()
            docs = retriever.invoke(message)
            sources = list(set(d.metadata.get("source", "Unknown") for d in docs))
            context = "\n\n".join(d.page_content for d in docs) if docs else "No relevant context found."

            yield f"data: {json.dumps({'type': 'sources', 'value': sources})}\n\n"

            full_response = ""
            async for chunk in rag_system.rag_chain_with_history.astream(
                {"context": context, "question": message, "language": lang_name},
                config={"configurable": {"session_id": session_id}},
            ):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'content', 'value': chunk})}\n\n"

            log_rag_call(message, full_response, sources, lang, 0)
            yield f"data: {json.dumps({'type': 'done', 'value': ''})}\n\n"

        return StreamingResponse(stream_response(), media_type="text/event-stream")

    # Non-streaming
    try:
        start = time.time()
        result = pipeline.process_text(message, language, session_id=session_id)
        latency_ms = int((time.time() - start) * 1000)
        log_rag_call(
            message, result["response"], result.get("sources", []),
            result.get("language", "en"), latency_ms
        )
        return JSONResponse(content=result)
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/audio")
@limiter.limit("10/minute")
async def audio_chat(
    request: Request,
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    stream: bool = Form(False),
    session_id: str = Form("default"),
):
    try:
        print(f"Audio received: {file.filename}")
        audio_bytes = await file.read()
        if not audio_bytes:
            raise HTTPException(400, "Empty file")
        if len(audio_bytes) > MAX_AUDIO_SIZE_MB * 1024 * 1024:
            raise HTTPException(413, f"Audio file too large (max {MAX_AUDIO_SIZE_MB}MB)")
        if file.content_type and not file.content_type.startswith("audio/"):
            raise HTTPException(415, "File must be an audio file")

        start = time.time()
        result = pipeline.process_audio(
            audio_bytes, file.content_type or "audio/wav", language,
            return_audio=False, session_id=session_id
        )
        latency_ms = int((time.time() - start) * 1000)
        log_rag_call(
            result.get("query", ""), result["response"],
            result.get("sources", []), result.get("language", "en"), latency_ms
        )
        return JSONResponse(content=result)
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tts/generate")
async def generate_tts(
    text: str = Form(...),
    language: str = Form("en"),
):
    """Generate TTS audio on-demand when user clicks play button."""
    try:
        retrieval_result = {"response": text, "language": language}
        audio_data = pipeline.response_generator.generate_audio(retrieval_result)
        return JSONResponse(content={
            "success": True,
            "audio_data": audio_data,
            "audio_available": audio_data is not None,
        })
    except Exception as e:
        print(f"TTS Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/documents/refresh")
async def refresh_docs():
    """Refresh documents from Azure Blob Storage and rebuild vector store."""
    try:
        refresh_documents()
        return JSONResponse(content={"success": True, "message": "Documents refreshed successfully"})
    except Exception as e:
        print(f"Refresh Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


SUPPORTED_UPLOAD_EXTENSIONS = {".pdf", ".pptx", ".md"}
MAX_DOCUMENT_SIZE_MB = int(os.environ.get("MAX_DOCUMENT_SIZE_MB", 20))


@app.get("/documents/list")
async def list_documents():
    """List all indexed documents with their chunk counts."""
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/documents/upload")
@limiter.limit("2/minute")
async def upload_doc(request: Request, file: UploadFile = File(...)):
    """Upload a document, persist it (Azure Blob or local), and re-index."""
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
        refresh_documents()
        return JSONResponse(content={"success": True, "filename": file.filename, "message": f"'{file.filename}' uploaded and indexed successfully"})
    except Exception as e:
        print(f"Upload Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/documents/{filename}")
async def delete_doc(filename: str):
    """Delete a document from storage and re-index."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid filename")
    try:
        delete_document(filename)
        refresh_documents()
        return JSONResponse(content={"success": True, "message": f"'{filename}' deleted and index rebuilt"})
    except Exception as e:
        print(f"Delete Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents/chunks")
async def get_document_chunks(source: str, query: str = ""):
    """Return text chunks for a specific source document, ranked by relevance to query."""
    from rag import rag_system
    if not rag_system or not rag_system.vectorstore:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    try:
        if query:
            docs = rag_system.vectorstore.similarity_search(
                query, k=4, filter={"source": source}
            )
        else:
            # No query — fetch raw chunks by metadata filter
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
    except Exception as e:
        print(f"Chunks Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("Starting Multilingual AI Chat Server")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")