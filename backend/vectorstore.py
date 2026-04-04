"""
vectorstore.py — LangChainRAG: ChromaDB vector store + hybrid retriever + LLM chain.
Handles document loading (PDF per-page via PyMuPDF, PPTX per-slide),
OCR on embedded images, LaTeX normalization, and BM25 + semantic hybrid retrieval.
"""
import io
import os
from typing import List, Optional

from langchain_groq import ChatGroq
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever

from blob_sync import sync_documents_from_blob
from memory import get_session_history
from latex_utils import normalize_math

CHROMA_PERSIST_DIR = "./chroma_db"

# Warn once if tesseract is missing rather than crashing
_OCR_AVAILABLE: Optional[bool] = None


def _ocr_image(img_bytes: bytes) -> str:
    """Run Tesseract OCR on raw image bytes. Returns '' if tesseract not installed."""
    global _OCR_AVAILABLE
    if _OCR_AVAILABLE is False:
        return ""
    try:
        import pytesseract
        from PIL import Image
        if _OCR_AVAILABLE is None:
            _OCR_AVAILABLE = True
        img = Image.open(io.BytesIO(img_bytes))
        text = pytesseract.image_to_string(img, config="--psm 6").strip()
        return text if len(text) >= 15 else ""
    except ImportError:
        if _OCR_AVAILABLE is None:
            print("⚠️  pytesseract / Pillow not installed — image OCR disabled")
            _OCR_AVAILABLE = False
        return ""
    except Exception as e:
        if "tesseract is not installed" in str(e).lower() or "tesseract" in str(e).lower():
            if _OCR_AVAILABLE is None:
                print("⚠️  Tesseract binary not found — image OCR disabled. Install with: sudo dnf install tesseract")
                _OCR_AVAILABLE = False
            return ""
        return ""


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
        print("Groq API initialized")

        self.vectorstore = None
        self.bm25_retriever: Optional[BM25Retriever] = None
        self.rag_chain_with_history = None

        self._try_load_existing_vectorstore()

    def _try_load_existing_vectorstore(self):
        """Load existing ChromaDB index; rebuild BM25 from stored chunks."""
        chroma_index = os.path.join(CHROMA_PERSIST_DIR, "chroma.sqlite3")
        if not os.path.exists(chroma_index):
            return

        try:
            self.vectorstore = Chroma(
                persist_directory=CHROMA_PERSIST_DIR,
                embedding_function=self.embeddings,
            )
            count = self.vectorstore._collection.count()
            if count == 0:
                print("ChromaDB index exists but is empty — will re-index on load")
                self.vectorstore = None
                return

            print(f"Loaded existing ChromaDB index ({count} chunks) - skipping re-indexing")

            # Rebuild BM25 from stored Chroma documents (no disk read needed)
            result = self.vectorstore._collection.get(include=["documents", "metadatas"])
            docs = [
                Document(page_content=t, metadata=m)
                for t, m in zip(result["documents"], result["metadatas"])
                if t and t.strip()
            ]
            self.bm25_retriever = BM25Retriever.from_documents(docs, k=5)
            print(f"BM25 index built ({len(docs)} chunks)")

            self._build_rag_chain()
        except Exception as e:
            print(f"Failed to load existing ChromaDB index: {e}. Will rebuild.")
            self.vectorstore = None
            self.bm25_retriever = None

    def _build_rag_chain(self):
        """Build the LCEL chain with conversation history."""
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
        print("RAG chain with conversation history built")

    def _load_pdf(self, filepath: str, filename: str) -> List[Document]:
        """Load PDF per-page using PyMuPDF with OCR on embedded images."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            print("⚠️  pymupdf not installed — skipping PDF loading")
            return []

        documents = []
        try:
            doc = fitz.open(filepath)
            for page_num, page in enumerate(doc):
                text = page.get_text()

                # OCR any images on this page
                ocr_parts = []
                for img in page.get_images(full=True):
                    xref = img[0]
                    try:
                        base_image = doc.extract_image(xref)
                        ocr_text = _ocr_image(base_image["image"])
                        if ocr_text:
                            ocr_parts.append(f"[Image text: {ocr_text}]")
                    except Exception:
                        pass

                full_text = normalize_math(text)
                if ocr_parts:
                    full_text += "\n" + "\n".join(ocr_parts)

                if full_text.strip():
                    documents.append(Document(
                        page_content=full_text.strip(),
                        metadata={"source": filename, "type": "pdf", "page": page_num + 1},
                    ))

            page_count = len(documents)
            print(f"Loaded: {filename} ({page_count} pages)")
        except Exception as e:
            print(f"Error loading PDF {filename}: {e}")

        return documents

    def _load_pptx(self, filepath: str, filename: str) -> List[Document]:
        """Load PPTX per-slide with OCR on picture shapes."""
        from pptx import Presentation
        from pptx.enum.shapes import MSO_SHAPE_TYPE

        documents = []
        try:
            prs = Presentation(filepath)
            slide_count = 0
            for i, slide in enumerate(prs.slides):
                slide_text = "\n".join(
                    shape.text for shape in slide.shapes
                    if hasattr(shape, "text") and shape.text.strip()
                )

                # OCR picture shapes on this slide
                for shape in slide.shapes:
                    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                        try:
                            ocr_text = _ocr_image(shape.image.blob)
                            if ocr_text:
                                slide_text += f"\n[Image text: {ocr_text}]"
                        except Exception:
                            pass

                slide_text = normalize_math(slide_text)
                if slide_text.strip():
                    documents.append(Document(
                        page_content=slide_text.strip(),
                        metadata={"source": filename, "type": "pptx", "slide": i + 1},
                    ))
                    slide_count += 1

            print(f"Loaded: {filename} ({slide_count} slides)")
        except Exception as e:
            print(f"Error loading PPTX {filename}: {e}")

        return documents

    def _load_markdown(self, filepath: str, filename: str) -> List[Document]:
        """Load markdown file as a single document with math normalization."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()
            if text.strip():
                print(f"Loaded: {filename} ({len(text)} chars)")
                return [Document(
                    page_content=normalize_math(text.strip()),
                    metadata={"source": filename, "type": "markdown"},
                )]
            print(f"Skipping {filename}: empty file")
        except Exception as e:
            print(f"Error loading {filename}: {e}")
        return []

    def load_documents(self) -> List[Document]:
        """Load all documents from the folder."""
        sync_documents_from_blob(self.documents_folder)
        documents: List[Document] = []

        if not os.path.exists(self.documents_folder):
            os.makedirs(self.documents_folder)
            print(f"Created {self.documents_folder} folder.")
            return documents

        for filename in os.listdir(self.documents_folder):
            filepath = os.path.join(self.documents_folder, filename)
            ext = os.path.splitext(filename)[1].lower()

            if ext not in self.SUPPORTED_EXTENSIONS:
                print(f"Skipping unsupported file type: {filename}")
                continue

            if ext == ".pdf":
                documents.extend(self._load_pdf(filepath, filename))
            elif ext == ".pptx":
                documents.extend(self._load_pptx(filepath, filename))
            elif ext == ".md":
                documents.extend(self._load_markdown(filepath, filename))

        return documents

    def create_vectorstore(self, documents: List[Document]):
        """Index documents into ChromaDB and build BM25 retriever."""
        if not documents:
            print("No documents to index")
            return

        try:
            # Per-type chunking — PPTX and per-page PDFs are already small,
            # so only split markdown and very long PDF pages further
            pdf_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
            md_splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=100)

            all_chunks: List[Document] = []
            for doc in documents:
                doc_type = doc.metadata.get("type", "")
                if doc_type == "pptx":
                    all_chunks.append(doc)  # Already 1 doc per slide
                elif doc_type == "pdf":
                    # Split long pages; short pages kept as-is
                    if len(doc.page_content) > 900:
                        all_chunks.extend(pdf_splitter.split_documents([doc]))
                    else:
                        all_chunks.append(doc)
                elif doc_type == "markdown":
                    all_chunks.extend(md_splitter.split_documents([doc]))
                else:
                    all_chunks.append(doc)

            all_chunks = [c for c in all_chunks if c.page_content and c.page_content.strip()]

            if not all_chunks:
                print("All chunks were empty after filtering")
                return

            print(f"Created {len(all_chunks)} chunks across {len(documents)} source pages/slides")

            self.vectorstore = Chroma.from_documents(
                all_chunks,
                self.embeddings,
                persist_directory=CHROMA_PERSIST_DIR,
            )
            print(f"ChromaDB vector store created and persisted to '{CHROMA_PERSIST_DIR}'")

            # Build BM25 from the same chunks
            self.bm25_retriever = BM25Retriever.from_documents(all_chunks, k=5)
            print(f"BM25 index built ({len(all_chunks)} chunks)")

            self._build_rag_chain()

        except Exception as e:
            print(f"Vector store creation failed: {e}")
            import traceback
            traceback.print_exc()
            self.vectorstore = None
            self.bm25_retriever = None

    def get_retriever(self):
        """Hybrid retriever: BM25 (0.4) + semantic Chroma (0.6).
        Falls back to semantic-only if BM25 not available."""
        if not self.vectorstore:
            return None

        semantic = self.vectorstore.as_retriever(search_kwargs={"k": 5})

        if self.bm25_retriever:
            return EnsembleRetriever(
                retrievers=[self.bm25_retriever, semantic],
                weights=[0.4, 0.6],
            )
        return semantic
