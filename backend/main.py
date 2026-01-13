import os
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from google import genai
from google.genai import types
from rag_engine import ingest_documents, retrieve_context
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize App & Gemini
app = FastAPI(title="Multilingual AI Chat API", version="1.0.0")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )
api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables!")

client = genai.Client(api_key=api_key)

# CORS for Expo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load Docs on Startup
@app.on_event("startup")
async def startup_event():
    print("Starting up...")
    ingest_documents()
    print("Server ready!")

# --- LANGUAGE CONFIGS ---
LANGUAGE_PROMPTS = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
}

# --- SYSTEM INSTRUCTION ---
def get_system_prompt(language: str = "en"):
    lang_name = LANGUAGE_PROMPTS.get(language, "English")
    return f"""You are a helpful AI assistant with access to internal documents. Follow these rules STRICTLY:

1. You MUST use the retrieval_tool for EVERY user question to search the internal documents.
2. If the tool returns relevant content:
   - Generate your answer ONLY using that retrieved content
   - Do not add information from outside knowledge
   - You may rephrase or summarize the content
3. If the tool returns no relevant information or None:
   - Respond EXACTLY with: "Information not available in internal documents."
   - Do not try to answer from general knowledge
4. Always respond in {lang_name} language.
5. Be helpful and concise in your responses.
"""

# --- ADK TOOL DEFINITION ---
def retrieval_tool(query: str) -> str:
    """
    Retrieves information from internal documents based on the query.
    
    Args:
        query: The search query to find relevant information
        
    Returns:
        Retrieved context from documents or None if no relevant content found
    """
    context = retrieve_context(query)
    if context:
        return f"Retrieved context:\n{context}"
    return "No relevant information found in documents."


# --- ENDPOINTS ---

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Multilingual AI Chat API",
        "version": "1.0.0",
        "endpoints": ["/chat/text", "/chat/audio"]
    }

@app.post("/chat/text")
async def text_chat(
    message: str = Form(...),
    language: str = Form("en")
):
    """
    Text-to-Text Chat Endpoint with RAG
    
    Args:
        message: User's text message
        language: Language code (en, hi, ta, te)
    
    Returns:
        JSON with AI response
    """
    try:
        # Validate language
        if language not in LANGUAGE_PROMPTS:
            language = "en"
        
        # Create agent configuration with retrieval tool
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=message,
            config=types.GenerateContentConfig(
                system_instruction=get_system_prompt(language),
                tools=[retrieval_tool],
                temperature=0.7,
            )
        )
        
        # Extract text response
        reply_text = ""
        if response.text:
            reply_text = response.text
        else:
            # Check if tool was called but no final response
            reply_text = "Information not available in internal documents."
        
        return JSONResponse(content={
            "success": True,
            "response": reply_text,
            "language": language
        })
        
    except Exception as e:
        print(f"Error in text_chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/audio")
async def audio_chat(
    file: UploadFile = File(...),
    language: str = Form("en")
):
    """
    Audio-to-Audio Chat Endpoint with RAG
    
    Process:
    1. Transcribe audio to text using Gemini
    2. Query RAG agent with transcribed text
    3. Return response text (frontend will handle TTS)
    
    Args:
        file: Audio file (WAV, MP3, etc.)
        language: Language code (en, hi, ta, te)
    
    Returns:
        JSON with transcription and AI response
    """
    try:
        print(f"Received audio file: {file.filename}, content_type: {file.content_type}, language: {language}")
        
        # Validate language
        if language not in LANGUAGE_PROMPTS:
            language = "en"
        
        # Read audio file
        audio_bytes = await file.read()
        print(f"Audio bytes read: {len(audio_bytes)} bytes")
        
        if len(audio_bytes) == 0:
            raise HTTPException(status_code=400, detail="Empty audio file received")
        
        # Determine MIME type
        mime_type = file.content_type or "audio/wav"
        if not mime_type.startswith("audio/"):
            mime_type = "audio/wav"
        
        # Step 1: Transcribe Audio using Gemini
        transcription_response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                f"Transcribe this audio exactly in {LANGUAGE_PROMPTS.get(language, 'English')}. Only output the transcription, nothing else."
            ]
        )
        
        user_text = transcription_response.text.strip()
        
        if not user_text:
            return JSONResponse(content={
                "success": False,
                "error": "Could not transcribe audio"
            }, status_code=400)
        
        # Step 2: Query RAG Agent with Transcribed Text
        rag_response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=user_text,
            config=types.GenerateContentConfig(
                system_instruction=get_system_prompt(language),
                tools=[retrieval_tool],
                temperature=0.7,
            )
        )
        
        # Extract response
        reply_text = ""
        if rag_response.text:
            reply_text = rag_response.text
        else:
            reply_text = "Information not available in internal documents."
        
        # Step 3: Generate audio response using Gemini
        audio_response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=f"Generate audio for: {reply_text}",
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name="Aoede"
                        )
                    )
                )
            )
        )
        
        # Extract audio bytes from response
        audio_data = None
        for part in audio_response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("audio/"):
                audio_data = part.inline_data.data
                break
        
        if not audio_data:
            # Fallback to text response if audio generation fails
            return JSONResponse(content={
                "success": True,
                "user_transcription": user_text,
                "response": reply_text,
                "language": language,
                "audio_available": False
            })
        
        # Return audio response
        return Response(
            content=audio_data,
            media_type="audio/wav",
            headers={
                "X-Transcription": user_text,
                "X-Response-Text": reply_text,
                "X-Language": language
            }
        )
        
    except Exception as e:
        print(f"Error in audio_chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    print("="*50)
    print("Starting Multilingual AI Chat Server")
    print("="*50)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")