import os
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
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

# --- LANGUAGE DETECTION ---
def detect_language(text: str) -> str:
    """
    Automatically detect the language of the input text.
    
    Args:
        text: The input text to analyze
        
    Returns:
        Language code (en, hi, ta, te) or 'en' as default
    """
    try:
        detection_prompt = f"""Analyze this text and return ONLY the language code from this list:
- en (English)
- hi (Hindi)
- ta (Tamil)
- te (Telugu)

Text: {text}

Return only the 2-letter code, nothing else."""
        
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=detection_prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
            )
        )
        
        detected = response.text.strip().lower()
        
        # Validate the detected language
        if detected in LANGUAGE_PROMPTS:
            return detected
        return "en"
        
    except Exception as e:
        print(f"Language detection error: {e}")
        return "en"

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
    language: Optional[str] = Form(None),
    stream: bool = Form(False)
):
    """
    Text-to-Text Chat Endpoint with RAG (supports streaming)
    
    Args:
        message: User's text message
        language: Language code (en, hi, ta, te) - auto-detected if not provided
        stream: Enable streaming response (default: False)
    
    Returns:
        JSON with AI response or Server-Sent Events stream
    """
    try:
        # Auto-detect language if not provided
        if not language or language not in LANGUAGE_PROMPTS:
            language = detect_language(message)
            print(f"Auto-detected language: {language}")
        
        if stream:
            # Streaming response
            async def generate_stream():
                try:
                    # Send language detection event
                    yield f"data: {{\"type\": \"language\", \"value\": \"{language}\"}}\n\n"
                    
                    # Stream the response
                    response_stream = client.models.generate_content_stream(
                        model="gemini-3-flash-preview",
                        contents=message,
                        config=types.GenerateContentConfig(
                            system_instruction=get_system_prompt(language),
                            tools=[retrieval_tool],
                            temperature=0.7,
                        )
                    )
                    
                    for chunk in response_stream:
                        if chunk.text:
                            # Send text chunk
                            import json
                            yield f"data: {{\"type\": \"content\", \"value\": {json.dumps(chunk.text)}}}\n\n"
                    
                    # Send completion event
                    yield f"data: {{\"type\": \"done\"}}\n\n"
                    
                except Exception as e:
                    yield f"data: {{\"type\": \"error\", \"value\": \"{str(e)}\"}}\n\n"
            
            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
        else:
            # Non-streaming response (original behavior)
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
    language: Optional[str] = Form(None),
    stream: bool = Form(False)
):
    """
    Audio-to-Audio Chat Endpoint with RAG (supports streaming)
    
    Process:
    1. Transcribe audio to text using Gemini
    2. Auto-detect language from transcription (if not provided)
    3. Query RAG agent with transcribed text
    4. Return audio response or stream text response
    
    Args:
        file: Audio file (WAV, MP3, etc.)
        language: Language code (en, hi, ta, te) - auto-detected if not provided
        stream: Enable streaming text response (default: False)
    
    Returns:
        Audio response or streamed text response with transcription
    """
    try:
        print(f"Received audio file: {file.filename}, content_type: {file.content_type}, language: {language}")
        
        # Read audio file
        audio_bytes = await file.read()
        print(f"Audio bytes read: {len(audio_bytes)} bytes")
        
        if len(audio_bytes) == 0:
            raise HTTPException(status_code=400, detail="Empty audio file received")
        
        # Determine MIME type
        mime_type = file.content_type or "audio/wav"
        if not mime_type.startswith("audio/"):
            mime_type = "audio/wav"
        
        # Step 1: Transcribe Audio using Gemini (language-agnostic first)
        transcription_response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                "Transcribe this audio exactly in its original language. Only output the transcription, nothing else."
            ]
        )
        
        user_text = transcription_response.text.strip()
        
        if not user_text:
            return JSONResponse(content={
                "success": False,
                "error": "Could not transcribe audio"
            }, status_code=400)
        
        # Auto-detect language from transcription if not provided
        if not language or language not in LANGUAGE_PROMPTS:
            language = detect_language(user_text)
            print(f"Auto-detected language: {language}")
        
        if stream:
            # Stream text response for audio input
            async def generate_audio_stream():
                try:
                    # Send transcription and language
                    import json
                    yield f"data: {{\"type\": \"transcription\", \"value\": {json.dumps(user_text)}}}\n\n"
                    yield f"data: {{\"type\": \"language\", \"value\": \"{language}\"}}\n\n"
                    
                    # Stream the RAG response
                    response_stream = client.models.generate_content_stream(
                        model="gemini-3-flash-preview",
                        contents=user_text,
                        config=types.GenerateContentConfig(
                            system_instruction=get_system_prompt(language),
                            tools=[retrieval_tool],
                            temperature=0.7,
                        )
                    )
                    
                    for chunk in response_stream:
                        if chunk.text:
                            yield f"data: {{\"type\": \"content\", \"value\": {json.dumps(chunk.text)}}}\n\n"
                    
                    yield f"data: {{\"type\": \"done\"}}\n\n"
                    
                except Exception as e:
                    yield f"data: {{\"type\": \"error\", \"value\": \"{str(e)}\"}}\n\n"
            
            return StreamingResponse(
                generate_audio_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
        
        # Non-streaming: Step 2: Query RAG Agent with Transcribed Text
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