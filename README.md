# Multilingual AI Chat System

A complete AI chat application with text and voice support, powered by Google Gemini and built with Expo (React Native) and FastAPI.

## Features

- **Text Chat** - Send messages and get AI responses  
- **Voice Chat** - Record audio, get transcriptions and spoken responses  
- **Multilingual** - English, Hindi, Tamil, Telugu support  
- **RAG Pipeline** - AI answers only from your uploaded documents (PDF/PPTX)  
- **Cross-platform** - Works on iOS, Android, and Web  

## Quick Start

### 1. Backend Setup

```bash
cd backend

# Install dependencies
pip install google-genai python-dotenv fastapi uvicorn python-multipart pypdf python-pptx

# Create .env file and add your API key
echo "GEMINI_API_KEY=your_api_key_here" > .env
# Get free API key from: https://aistudio.google.com/apikey

# Add documents (optional but recommended)
# Copy PDF or PPTX files to backend/documents/

# Start server
python main.py
```

Server will run on `http://localhost:8000`

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Configure API URL
# Edit frontend/services/api.ts and change:
# export const API_BASE_URL = 'http://YOUR_IP:8000';
# 
# Use:
# - 'http://localhost:8000' for iOS/Web
# - 'http://10.0.2.2:8000' for Android emulator
# - 'http://YOUR_LOCAL_IP:8000' for physical devices

# Start app
npm start

# Then press:
# 'w' for web
# 'i' for iOS simulator
# 'a' for Android emulator
# Or scan QR code with Expo Go app
```

## Project Structure

```
ADK/
├── backend/
│   ├── main.py              # FastAPI server with Google ADK
│   ├── rag_engine.py        # RAG pipeline for documents
│   ├── requirements.txt     # Python dependencies
│   ├── .env                 # API key (create this)
│   └── documents/           # Add your PDF/PPTX files here
│
└── frontend/
    ├── app/
    │   ├── _layout.tsx      # Root layout
    │   └── index.tsx        # Main chat screen
    ├── components/
    │   ├── chat-input.tsx   # Text input and voice button
    │   ├── chat-messages.tsx # Message display
    │   └── language-selector.tsx # Language picker
    ├── services/
    │   └── api.ts           # API client (configure URL here)
    ├── hooks/               # React hooks
    ├── constants/           # Theme constants
    └── package.json
```

## Usage

### Text Chat
1. Type your message
2. AI searches your documents
3. Get response based on document content
4. Response is spoken aloud (TTS)

### Voice Chat
1. Press microphone button to record
2. Speak your question
3. Audio is transcribed
4. AI responds from documents
5. Response is spoken back

### Language Switching
- Tap language button in header
- Select: English, Hindi (हिंदी), Tamil (தமிழ்), or Telugu (తెలుగు)
- All interactions use selected language

## How It Works

### RAG (Retrieval Augmented Generation)
1. Your documents are processed and stored in memory
2. When you ask a question, relevant sections are retrieved
3. AI generates answer ONLY from retrieved content
4. If no relevant content found: "Information not available in internal documents."

### Tech Stack

**Backend:**
- FastAPI - Web framework
- Google Gemini API - AI model
- Custom RAG engine - Document retrieval

**Frontend:**
- Expo SDK 54 - React Native framework
- expo-av - Audio recording
- expo-speech - Text-to-speech
- axios - HTTP client

## Configuration

### Backend (.env)
```
GEMINI_API_KEY=your_gemini_api_key
```

Get your free API key: https://aistudio.google.com/apikey

### Frontend (services/api.ts)
```typescript
export const API_BASE_URL = 'http://YOUR_IP:8000';
```

Find your local IP:
- Mac/Linux: `ifconfig | grep inet`
- Windows: `ipconfig`

## API Endpoints

### GET /
Health check

### POST /chat/text
Text chat with RAG
```bash
curl -X POST http://localhost:8000/chat/text \
  -F "message=What is this about?" \
  -F "language=en"
```

### POST /chat/audio
Audio chat with RAG
```bash
curl -X POST http://localhost:8000/chat/audio \
  -F "file=@audio.wav" \
  -F "language=en"
```

## Troubleshooting

### Backend won't start
- Check `.env` file exists with valid API key
- Install all dependencies: `pip install -r requirements.txt`
- Make sure port 8000 is free

### Frontend errors
- Run `npm install` in frontend folder
- Update API_BASE_URL in `services/api.ts`
- For physical devices, use local IP (not localhost)

### No AI responses
- Add documents to `backend/documents/`
- Restart backend to re-index documents
- Check backend terminal for errors

### Audio not working
- Grant microphone permissions
- iOS: Settings > Privacy > Microphone > Expo Go
- Android: Settings > Apps > Expo Go > Permissions

### Rate limit errors
- Free tier limits: 15 requests/minute, 1500/day
- Wait a minute and try again
- Consider upgrading API plan for higher limits

## Adding Documents

1. Place PDF or PPTX files in `backend/documents/`
2. Restart backend server
3. Server automatically indexes new documents
4. Ask questions about your documents!

## Requirements

- Python 3.10+
- Node.js 18+
- npm 8+
- Gemini API key (free from Google)

## Development

### Backend
```bash
cd backend
python main.py  # Runs on http://0.0.0.0:8000
```

### Frontend
```bash
cd frontend
npm start       # Opens Expo dev server
```

## Deployment

### Backend
Deploy to Railway, Render, or AWS with:
- Environment variable: `GEMINI_API_KEY`
- Port: 8000
- Start command: `python main.py`

### Frontend
Build with Expo EAS:
```bash
npm install -g eas-cli
eas build --platform android
eas build --platform ios
```

## License

MIT License - Free to use and modify

## Support

For issues or questions:
1. Check error messages in terminal
2. Verify API key is correct
3. Ensure backend is running
4. Check API URL in frontend
5. Review troubleshooting section above
# AI-chat
