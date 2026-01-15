import os
from typing import List, Optional
from langchain_groq import ChatGroq
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from dotenv import load_dotenv
from pypdf import PdfReader
from pptx import Presentation

load_dotenv()

class LangChainRAG:
    # LangChain-based RAG using Groq (LLM) and HuggingFace (Embeddings)
    def __init__(self, documents_folder: str = "documents"):
        self.documents_folder, self.groq_api_key = documents_folder, os.environ.get("GROQ_API_KEY")
        if not self.groq_api_key: raise ValueError("GROQ_API_KEY missing!")
        
        # Initialize embeddings (HuggingFace, local, free)
        from langchain_community.embeddings import HuggingFaceEmbeddings
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2", model_kwargs={'device': 'cpu'})
        
        # Initialize LLM (Groq Llama 3.3, fast, free tier)
        self.llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=self.groq_api_key, temperature=0.7)
        print("✓ Groq API initialized")
        
        self.vectorstore, self.rag_chain = None, None
        
    def load_documents(self) -> List[Document]:
        documents = []
        if not os.path.exists(self.documents_folder):
            os.makedirs(self.documents_folder)
            print(f"Created {self.documents_folder} folder.")
            return documents
        
        for filename in os.listdir(self.documents_folder):
            filepath = os.path.join(self.documents_folder, filename)
            try:
                text = ""
                # Load PDF
                if filename.endswith(".pdf"):
                    for page in PdfReader(filepath).pages: text += page.extract_text() + "\n"
                    documents.append(Document(page_content=text, metadata={"source": filename, "type": "pdf"}))
                    print(f"Loaded: {filename}")
                # Load PPTX
                elif filename.endswith(".pptx"):
                    for slide in Presentation(filepath).slides:
                        for shape in slide.shapes:
                            if hasattr(shape, "text"): text += shape.text + "\n"
                    documents.append(Document(page_content=text, metadata={"source": filename, "type": "pptx"}))
                    print(f"Loaded: {filename}")
            except Exception as e: print(f"Error loading {filename}: {e}")
        return documents
    
    def create_vectorstore(self, documents: List[Document]):
        if not documents: return
        try:
            # Chunking
            chunks = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200).split_documents(documents)
            print(f"Created {len(chunks)} chunks")
            # Indexing
            self.vectorstore = FAISS.from_documents(chunks, self.embeddings)
            print("Vector store created")
        except Exception as e:
            print(f"⚠️ Vector store creation failed: {e}")
            self.vectorstore = None
        
    def setup_rag_chain(self, language: str = "en"):
        if not self.vectorstore: return
        
        # Map codes to full names for better LLM adherence
        lang_map = {
            'en': 'English',
            'hi': 'Hindi', 
            'ta': 'Tamil',
            'te': 'Telugu'
        }
        full_language = lang_map.get(language, 'English')
        
        retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})
        
        # Multilingual Prompt
        prompt = ChatPromptTemplate.from_template("""You are a helpful AI assistant. Use context to answer.
IMPORTANT:
1. Answer ONLY based on context.
2. If info missing, say: "Information not available in internal documents."
3. Respond in {language}.

Context:
{context}

Question: {question}""")
        
        self.rag_chain = (
            {"context": retriever, "question": RunnablePassthrough(), "language": lambda x: full_language}
            | prompt | self.llm | StrOutputParser()
        )

# Singleton instance
rag_system = None

def initialize_rag():
    global rag_system
    rag_system = LangChainRAG()
    rag_system.create_vectorstore(rag_system.load_documents())

def get_rag_response(query: str, language: str = "en") -> str:
    if not rag_system: initialize_rag()
    
    # Check if RAG is active
    if not rag_system.vectorstore:
        return "System is running in basic mode (no documents indexed). Please add documents to enable RAG."
    
    # Setup chain for current language
    rag_system.setup_rag_chain(language)
    
    try:
        return rag_system.rag_chain.invoke(query)
    except Exception as e:
        print(f"RAG Error: {e}")
        return "Error processing request."
