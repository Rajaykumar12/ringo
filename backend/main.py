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
from pipeline import PipelineOrchestrator, QueryRefiner
from rag import initialize_rag, refresh_documents, get_rag_response, rag_system as _rag_ref
from rag_logger import log_rag_call

from contextlib import asynccontextmanager

load_dotenv()

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

app = FastAPI(title="Multilingual AI Chat API", version="2.0.0", lifespan=lifespan)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"Validation error: {exc.errors()}")
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
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
async def text_chat(
    message: str = Form(...),
    language: Optional[str] = Form(None),
    stream: bool = Form(False),
    session_id: str = Form("default"),
):
    # [High #6] Real SSE streaming
    if stream:
        async def stream_response():
            from rag import rag_system, initialize_rag

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
async def audio_chat(
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


if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("Starting Multilingual AI Chat Server")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")