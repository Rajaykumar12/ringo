
# Multilingual AI Chat System

> A fully open-source, cross-platform AI chat application supporting both text and voice, built with modern, high-performance open-source technologies.

---

## ✨ Overview

This project delivers a robust AI chat experience with multilingual support, leveraging:

- **Groq (Llama 3.3-70b)** for blazing-fast, free text generation
- **HuggingFace** (`all-MiniLM-L6-v2`) for local, unlimited semantic embeddings
- **OpenAI Whisper** for accurate, local audio transcription
- **langdetect** for local language detection

Frontend: **Expo (React Native)**  
Backend: **FastAPI**

---

## 🚀 Features

- **Y-Shaped Pipeline**: Unified processing for both text and audio inputs
- **Retrieval Augmented Generation (RAG)**: Professional-grade RAG using FAISS vector store
- **Multilingual**: Supports English, Hindi, Tamil, and Telugu
- **Cross-Platform**: Works on iOS, Android, and Web
- **Local & Open Source**: No vendor lock-in, unlimited usage
- **Easy Extensibility**: Add new languages or document sources easily

---

## 🏗️ Architecture

The backend implements a modular, 4-stage Y-shaped pipeline:

1. **Input Processing**
    - **Text**: Preprocessing and cleaning
    - **Audio**: Transcription via local Whisper model
2. **Query Refinement**
    - Language detection and unified query formatting
3. **RAG Retrieval**
    - Semantic search using HuggingFace embeddings and FAISS
4. **Response Generation**
    - Final answer generation using Groq API

---

## ⚡ Quick Start

### Backend Setup

```bash
cd backend
# Install dependencies (Python 3.10+)
pip install -r requirements.txt

# Create .env file with your Groq API key
echo "GROQ_API_KEY=your_groq_api_key_here" > .env
# Get a free API key: https://console.groq.com/keys

# (Optional) Add documents for RAG
# Place PDF or PPTX files in backend/documents/

# Start the FastAPI server
python main.py
```

Server runs at: [http://localhost:8000](http://localhost:8000)

---

### Frontend Setup

```bash
cd frontend
# Install dependencies
npm install

# (Optional) Configure API URL for device testing
# Edit frontend/services/api.ts:
# export const API_BASE_URL = 'http://YOUR_LOCAL_IP:8000';

# Start the Expo app
npm start
```

---

## 🗂️ Project Structure

```
ADK/
├── backend/
│   ├── main.py              # FastAPI server (lifespan managed)
│   ├── pipeline.py          # Y-shaped pipeline orchestrator
│   ├── langchain_rag.py     # RAG engine (Groq + HuggingFace)
│   ├── requirements.txt     # Python dependencies
│   └── documents/           # Knowledge base files (PDF/PPTX)
│
└── frontend/
    ├── app/
    │   ├── _layout.tsx      # Root layout
    │   └── index.tsx        # Main chat interface
    ├── components/
    │   ├── chat-input.tsx   # Input & recording logic
    │   ├── chat-messages.tsx # Message list display
    │   └── language-selector.tsx # Language picker
    ├── services/
    │   └── api.ts           # API client
    ├── hooks/               # Custom React hooks
    ├── constants/           # App constants
    └── assets/              # Static assets
```

---

## 📝 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

## 🙌 Acknowledgements

- [Groq](https://groq.com)
- [HuggingFace](https://huggingface.co)
- [OpenAI Whisper](https://github.com/openai/whisper)
- [langdetect](https://pypi.org/project/langdetect/)

---

## 💡 Contributing

Pull requests and issues are welcome! For major changes, please open an issue first to discuss what you would like to change.
