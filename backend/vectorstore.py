"""
vectorstore.py — LangChainRAG: ChromaDB vector store + LLM chain.
Handles document loading, per-type chunking, indexing, and RAG chain construction.
"""
from typing import List
from langchain_groq import ChatGroq
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from pypdf import PdfReader
from pptx import Presentation

from blob_sync import sync_documents_from_blob
from memory import get_session_history

import os

CHROMA_PERSIST_DIR = "./chroma_db"


class LangChainRAG:
    SUPPORTED_EXTENSIONS = {".pdf", ".pptx", ".md"}

    def __init__(self, documents_folder: str = "documents"):
        self.documents_folder = documents_folder
        self.groq_api_key = os.environ.get("GROQ_API_KEY")
        if not self.groq_api_key:
            raise ValueError("GROQ_API_KEY missing!")

        sync_documents_from_blob(self.documents_folder)

        # Embeddings — local HuggingFace, no API cost
        from langchain_community.embeddings import HuggingFaceEmbeddings
        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2", model_kwargs={"device": "cpu"}
        )

        # LLM — Groq Llama 3.3 70B
        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile", api_key=self.groq_api_key, temperature=0.7
        )
        print("✓ Groq API initialized")

        self.vectorstore = None
        self.rag_chain_with_history = None

        # Load existing ChromaDB index if available
        self._try_load_existing_vectorstore()

    def _try_load_existing_vectorstore(self):
        """Load an existing ChromaDB index from disk if available, skipping re-indexing."""
        chroma_index = os.path.join(CHROMA_PERSIST_DIR, "chroma.sqlite3")
        if os.path.exists(chroma_index):
            try:
                self.vectorstore = Chroma(
                    persist_directory=CHROMA_PERSIST_DIR,
                    embedding_function=self.embeddings,
                )
                count = self.vectorstore._collection.count()
                if count > 0:
                    print(f"✓ Loaded existing ChromaDB index ({count} chunks) — skipping re-indexing")
                    self._build_rag_chain()
                else:
                    print("ℹ️  ChromaDB index exists but is empty — will re-index on load")
                    self.vectorstore = None
            except Exception as e:
                print(f"⚠️ Failed to load existing ChromaDB index: {e}. Will rebuild.")
                self.vectorstore = None

    def _build_rag_chain(self):
        """Build the LCEL chain with conversation history (RunnableWithMessageHistory)."""
        if not self.vectorstore:
            return

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful AI assistant. Use the provided context to answer accurately.

Instructions:
1. Prefer information from the context when it is relevant to the question.
2. If the context doesn't fully cover the question, note this briefly and still give a helpful answer.
3. Respond in {language}.

Context:
{context}"""),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{question}"),
        ])

        chain = prompt | self.llm | StrOutputParser()

        self.rag_chain_with_history = RunnableWithMessageHistory(
            chain,
            get_session_history,
            input_messages_key="question",
            history_messages_key="history",
        )
        print("✓ RAG chain with conversation history built")

    def load_documents(self) -> List[Document]:
        """Load documents from the folder. One Document per PPTX slide, full text for PDF/MD."""
        sync_documents_from_blob(self.documents_folder)
        documents = []

        if not os.path.exists(self.documents_folder):
            os.makedirs(self.documents_folder)
            print(f"Created {self.documents_folder} folder.")
            return documents

        for filename in os.listdir(self.documents_folder):
            filepath = os.path.join(self.documents_folder, filename)
            ext = os.path.splitext(filename)[1].lower()

            if ext not in self.SUPPORTED_EXTENSIONS:
                print(f"⚠️ Skipping unsupported file type: {filename} (supported: pdf, pptx, md)")
                continue

            try:
                if filename.endswith(".pdf"):
                    text = ""
                    for page in PdfReader(filepath).pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                    if text.strip():
                        documents.append(Document(
                            page_content=text.strip(),
                            metadata={"source": filename, "type": "pdf"}
                        ))
                        print(f"Loaded: {filename} ({len(text)} chars)")
                    else:
                        print(f"⚠️ Skipping {filename}: no extractable text")

                elif filename.endswith(".pptx"):
                    # One Document per slide for better retrieval granularity
                    prs = Presentation(filepath)
                    slide_count = 0
                    for i, slide in enumerate(prs.slides):
                        slide_text = "\n".join(
                            shape.text for shape in slide.shapes
                            if hasattr(shape, "text") and shape.text.strip()
                        )
                        if slide_text.strip():
                            documents.append(Document(
                                page_content=slide_text.strip(),
                                metadata={"source": filename, "type": "pptx", "slide": i + 1}
                            ))
                            slide_count += 1
                    print(f"Loaded: {filename} ({slide_count} slides as separate chunks)")

                elif filename.endswith(".md"):
                    with open(filepath, "r", encoding="utf-8") as f:
                        text = f.read()
                    if text.strip():
                        documents.append(Document(
                            page_content=text.strip(),
                            metadata={"source": filename, "type": "markdown"}
                        ))
                        print(f"Loaded: {filename} ({len(text)} chars)")
                    else:
                        print(f"⚠️ Skipping {filename}: empty file")

            except Exception as e:
                print(f"Error loading {filename}: {e}")

        return documents

    def create_vectorstore(self, documents: List[Document]):
        """Index documents into ChromaDB using per-type chunk sizes."""
        if not documents:
            print("⚠️ No documents to index")
            return

        try:
            # Per-document-type chunking strategies
            pdf_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
            md_splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=100)
            generic_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

            all_chunks = []
            for doc in documents:
                doc_type = doc.metadata.get("type", "")
                if doc_type == "pptx":
                    all_chunks.append(doc)  # Already 1 doc per slide
                elif doc_type == "pdf":
                    all_chunks.extend(pdf_splitter.split_documents([doc]))
                elif doc_type == "markdown":
                    all_chunks.extend(md_splitter.split_documents([doc]))
                else:
                    all_chunks.extend(generic_splitter.split_documents([doc]))

            all_chunks = [c for c in all_chunks if c.page_content and c.page_content.strip()]

            if not all_chunks:
                print("⚠️ All chunks were empty after filtering")
                return

            print(f"Created {len(all_chunks)} chunks across {len(documents)} document(s)")

            self.vectorstore = Chroma.from_documents(
                all_chunks,
                self.embeddings,
                persist_directory=CHROMA_PERSIST_DIR,
            )
            print(f"✓ ChromaDB vector store created and persisted to '{CHROMA_PERSIST_DIR}'")
            self._build_rag_chain()

        except Exception as e:
            print(f"⚠️ Vector store creation failed: {e}")
            import traceback
            traceback.print_exc()
            self.vectorstore = None

    def get_retriever(self):
        """Score-threshold retriever — only returns relevant chunks (threshold: 0.3)."""
        if not self.vectorstore:
            return None
        try:
            return self.vectorstore.as_retriever(
                search_type="similarity_score_threshold",
                search_kwargs={"k": 5, "score_threshold": 0.3},
            )
        except Exception:
            return self.vectorstore.as_retriever(search_kwargs={"k": 5})
