import os
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from typing import Optional
from dotenv import load_dotenv
from pipeline import PipelineOrchestrator
from langchain_rag import initialize_rag

from contextlib import asynccontextmanager

load_dotenv()

pipeline = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global pipeline
    print("="*60 + "\nStarting Multilingual AI Chat Server\n" + "="*60)
    try:
        initialize_rag()
    except Exception as e:
        print(f"⚠️ RAG initialization failed: {e}")
    
    pipeline = PipelineOrchestrator()
    print("\n✓ Server ready!\n" + "="*60)
    
    yield
    
    # Shutdown
    print("Shutting down...")

# Initialize App
app = FastAPI(title="Multilingual AI Chat API", version="2.0.0", lifespan=lifespan)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"Validation error: {exc.errors()}")
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

# Verify API key
if not os.environ.get("GROQ_API_KEY"):
    raise ValueError("GROQ_API_KEY missing!")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ENDPOINTS ---

@app.get("/")
async def root():
    return {
        "status": "healthy",
        "service": "Multilingual AI Chat API",
        "version": "2.0.0",
        "endpoints": ["/chat/text", "/chat/audio"]
    }

@app.post("/chat/text")
async def text_chat(
    message: str = Form(...),
    language: Optional[str] = Form(None),
    stream: bool = Form(False)
):
    try:
        # Processing text through Y-shaped pipeline
        return JSONResponse(content=pipeline.process_text(message, language))
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/audio")
async def audio_chat(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    stream: bool = Form(False),
    return_audio: bool = Form(True)
):
    try:
        print(f"Audio received: {file.filename}")
        audio_bytes = await file.read()
        if not audio_bytes: raise HTTPException(400, "Empty file")
        
        # Processing audio through Y-shaped pipeline
        result = pipeline.process_audio(audio_bytes, file.content_type or "audio/wav", language)
        return JSONResponse(content=result)
        
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("Starting Multilingual AI Chat Server")
    print("Y-Shaped Architecture with LangChain RAG")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")