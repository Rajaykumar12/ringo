from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv
from langchain_rag import get_rag_response

load_dotenv()

class TextInputProcessor:
    # Stage 1a: Minimal text preprocessing
    @staticmethod
    def process(text: str) -> Dict[str, Any]:
        processed_text = text.strip()
        if not processed_text:
            raise ValueError("Empty text input")
        
        return {
            "text": processed_text,
            "source": "text",
            "original_length": len(text),
            "processed_length": len(processed_text)
        }

class AudioInputProcessor:
    # Stage 1b: Audio transcription with Whisper
    def __init__(self):
        import whisper
        print("Loading Whisper model...")
        self.model = whisper.load_model("base")
        print("✓ Whisper model loaded")
    
    def process(self, audio_bytes: bytes, mime_type: str = "audio/wav") -> Dict[str, Any]:
        if not audio_bytes: raise ValueError("Empty audio input")
        if not mime_type.startswith("audio/"): mime_type = "audio/wav"
        
        try:
            import tempfile, os
            # Save bytes to temp file for Whisper
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
                temp_audio.write(audio_bytes)
                temp_audio_path = temp_audio.name
            
            try:
                result = self.model.transcribe(temp_audio_path)
                transcribed_text = result["text"].strip()
                if not transcribed_text: raise ValueError("Empty transcription")
                
                return {
                    "text": transcribed_text,
                    "source": "audio",
                    "detected_language": result.get("language", "unknown")
                }
            finally:
                if os.path.exists(temp_audio_path): os.remove(temp_audio_path)
        except Exception as e:
            raise RuntimeError(f"Transcription failed: {str(e)}")

class QueryRefiner:
    # Stage 2: Query refinement and language detection
    def detect_language(self, text: str) -> str:
        try:
            from langdetect import detect
            lang_map = {'en': 'en', 'hi': 'hi', 'ta': 'ta', 'te': 'te'}
            return lang_map.get(detect(text), 'en')
        except: return "en"
    
    def refine(self, processed_input: Dict[str, Any], language: Optional[str] = None) -> Dict[str, Any]:
        text, source = processed_input["text"], processed_input["source"]
        if not language or language not in ["en", "hi", "ta", "te"]:
            language = self.detect_language(text)
        
        return {"query": text.strip(), "language": language, "source": source}

class RAGRetriever:
    # Stage 3: Retrieve context using LangChain
    @staticmethod
    def retrieve(refined_query: Dict[str, Any]) -> Dict[str, Any]:
        query, language = refined_query["query"], refined_query["language"]
        return {
            "response": get_rag_response(query, language),
            "query": query,
            "language": language,
            "source": refined_query["source"]
        }

class ResponseGenerator:
    # Stage 4: Format final response
    def generate(self, retrieval_result: Dict[str, Any], stream: bool = False) -> Dict[str, Any]:
        return {
            "success": True,
            "response": retrieval_result["response"],
            "language": retrieval_result["language"],
            "source": retrieval_result["source"],
            "query": retrieval_result["query"]
        }
    
    def generate_audio(self, retrieval_result: Dict[str, Any]) -> Optional[str]:
        """Generate audio from text response using edge-tts and return base64-encoded audio."""
        try:
            import edge_tts
            import asyncio
            import tempfile
            import base64
            from concurrent.futures import ThreadPoolExecutor
            
            text = retrieval_result["response"]
            language = retrieval_result["language"]
            
            # Map language codes to edge-tts voice names (neural voices)
            voice_map = {
                "en": "en-US-ChristopherNeural",      # English (US) - Female
                "hi": "hi-IN-SwaraNeural",     # Hindi (India) - Female
                "ta": "ta-IN-PallaviNeural",   # Tamil (India) - Female
                "te": "te-IN-ShrutiNeural"     # Telugu (India) - Female
            }
            voice = voice_map.get(language, "en-US-AriaNeural")
            
            # Create temporary file for audio
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
                temp_audio_path = temp_audio.name
            
            try:
                # Generate TTS using edge-tts (async)
                async def generate_tts():
                    communicate = edge_tts.Communicate(text, voice)
                    await communicate.save(temp_audio_path)
                
                # Run async function in a separate thread to avoid event loop conflicts
                def run_in_thread():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(generate_tts())
                    finally:
                        loop.close()
                
                with ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_thread)
                    future.result()  # Wait for completion
                
                # Read and encode as base64
                with open(temp_audio_path, "rb") as audio_file:
                    audio_bytes = audio_file.read()
                    audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                
                print(f"✓ Edge-TTS generated for language: {language} (voice: {voice})")
                return audio_base64
            finally:
                # Clean up temp file
                if os.path.exists(temp_audio_path):
                    os.remove(temp_audio_path)
                    
        except Exception as e:
            print(f"⚠️ Edge-TTS generation failed: {e}")
            return None

class PipelineOrchestrator:
    # Main pipeline controller
    def __init__(self):
        self.text_processor = TextInputProcessor()
        self.audio_processor = AudioInputProcessor()
        self.query_refiner = QueryRefiner()
        self.rag_retriever = RAGRetriever()
        self.response_generator = ResponseGenerator()
    
    def process_text(self, text: str, language: Optional[str] = None, return_audio: bool = False) -> Dict[str, Any]:
        """Process text input through the pipeline."""
        stage1 = self.text_processor.process(text)
        stage2 = self.query_refiner.refine(stage1, language)
        stage3 = self.rag_retriever.retrieve(stage2)
        final_output = self.response_generator.generate(stage3)
        
        # No automatic TTS generation - will be done on-demand via /tts/generate endpoint
        
        return final_output
    
    def process_audio(
        self, 
        audio_bytes: bytes, 
        mime_type: str = "audio/wav",
        language: Optional[str] = None,
        return_audio: bool = False
    ) -> Dict[str, Any]:
        """
        Process audio input through the pipeline.
        
        Pipeline: Audio Input → Stage 1b → Stage 2 → Stage 3 → Stage 4
        """
        # Stage 1b: Audio transcription
        stage1_output = self.audio_processor.process(audio_bytes, mime_type)
        
        # Stage 2: Query refinement
        stage2_output = self.query_refiner.refine(stage1_output, language)
        
        # Stage 3: RAG retrieval
        stage3_output = self.rag_retriever.retrieve(stage2_output)
        
        # Stage 4: Response generation
        final_output = self.response_generator.generate(stage3_output)
        
        # Add transcription to output
        final_output["transcription"] = stage1_output["text"]
        
        # No automatic TTS generation - will be done on-demand via /tts/generate endpoint
        
        return final_output