"""
rag.py — Public API for the RAG system.
Initializes the singleton instance and provides interface methods.
"""
import logging
from typing import Dict, Any
from langchain_core.documents import Document
from vectorstore import LangChainRAG

logger = logging.getLogger("ringo.rag")

# Singleton instance
rag_system = None

_STRUCTURAL_KW = frozenset([
    "section", "chapter", "topic", "overview", "outline", "contents",
    "table of contents", "index", "structure", "what is in", "what are",
    "list all", "list the", "slide", "slides", "cover", "about this",
    "this book", "this document", "this presentation",
])


def _is_structural_query(query: str) -> bool:
    q = query.lower()
    return any(kw in q for kw in _STRUCTURAL_KW)


def _format_chunk(doc: Document) -> str:
    meta = doc.metadata
    source = meta.get("source", "Unknown")
    if meta.get("chunk_type") == "structure":
        header = f"[Source: {source}, Document Structure]"
    elif meta.get("page") and meta["page"] != 0:
        header = f"[Source: {source}, Page {meta['page']}]"
    elif meta.get("slide") and meta["slide"] != 0:
        header = f"[Source: {source}, Slide {meta['slide']}]"
    else:
        header = f"[Source: {source}]"
    return header + "\n" + doc.page_content


def initialize_rag():
    global rag_system
    rag_system = LangChainRAG()
    if not rag_system.vectorstore:
        rag_system.create_vectorstore(rag_system.load_documents())


def refresh_documents():
    """Refresh documents from blob storage and rebuild the vector store."""
    global rag_system
    if rag_system:
        logger.info("Refreshing documents from blob storage...")
        rag_system.create_vectorstore(rag_system.load_documents())
        logger.info("Documents refreshed successfully")


def get_rag_response(query: str, language: str = "en", session_id: str = "default") -> Dict[str, Any]:
    """
    Returns dict: {"response": str, "sources": list[str], "context": str}
    Sources are the document filenames that contributed context to the answer.
    """
    global rag_system
    if not rag_system:
        initialize_rag()

    if not rag_system.vectorstore:
        return {
            "response": "System is running in basic mode (no documents indexed). Please add documents to enable RAG.",
            "sources": [],
            "context": "",
        }

    if not rag_system.rag_chain_with_history:
        rag_system._build_rag_chain()

    language_map = {"en": "English", "hi": "Hindi", "ta": "Tamil", "te": "Telugu"}
    language_name = language_map.get(language, "English")

    try:
        # Retrieve relevant docs
        retriever = rag_system.get_retriever()
        docs = retriever.invoke(query)

        # Deduplicate by content hash
        seen: set = set()
        deduped = []
        for d in docs:
            h = hash(d.page_content.strip())
            if h not in seen:
                seen.add(h)
                deduped.append(d)
        docs = deduped

        # For structural queries, prepend dedicated structure chunks
        if _is_structural_query(query) and rag_system.vectorstore:
            try:
                result = rag_system.vectorstore._collection.get(
                    where={"chunk_type": "structure"},
                    include=["documents", "metadatas"],
                )
                struct_docs = [
                    Document(page_content=t, metadata=m)
                    for t, m in zip(result["documents"], result["metadatas"])
                    if t and t.strip()
                ]
                docs = struct_docs + docs
            except Exception as e:
                logger.warning("Structure injection failed (non-fatal): %s", e)

        # Collect unique source filenames
        sources = list(set(d.metadata.get("source", "Unknown") for d in docs))
        context = "\n\n".join(_format_chunk(d) for d in docs) if docs else "No relevant context found."

        # Invoke chain with Redis-backed conversation history
        response = rag_system.rag_chain_with_history.invoke(
            {"context": context, "question": query, "language": language_name},
            config={"configurable": {"session_id": session_id}},
        )

        return {"response": response, "sources": sources, "context": context}

    except Exception as e:
        logger.error("RAG Error: %s", e)
        return {"response": "Error processing request.", "sources": [], "context": ""}
