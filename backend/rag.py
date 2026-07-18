"""
rag.py — Public API for the RAG system.
Initializes the singleton instance and provides interface methods.
"""
import logging
import os
from typing import Dict, Any, List
from langchain_core.documents import Document
from vectorstore import LangChainRAG
from response_cache import make_cache_key, get_cached_response, set_cached_response

logger = logging.getLogger("ringo.rag")

# Singleton instance
rag_system = None

_cross_encoder = None
RERANK_MODEL = os.environ.get("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
RERANK_TOP_N = int(os.environ.get("RERANK_TOP_N", "10"))


def _get_cross_encoder():
    global _cross_encoder
    if _cross_encoder is None:
        from sentence_transformers import CrossEncoder
        _cross_encoder = CrossEncoder(RERANK_MODEL)
        logger.info("Cross-encoder re-ranker loaded: %s", RERANK_MODEL)
    return _cross_encoder


def rerank_documents(query: str, docs: List[Document], top_n: int = RERANK_TOP_N) -> List[Document]:
    """Cross-encoder re-rank + cutoff so the merged BM25+semantic hit list doesn't
    balloon the prompt with noisy, low-relevance chunks as the corpus grows."""
    if len(docs) <= top_n:
        return docs
    try:
        encoder = _get_cross_encoder()
        pairs = [[query, d.page_content] for d in docs]
        scores = encoder.predict(pairs)
        ranked = sorted(zip(docs, scores), key=lambda pair: pair[1], reverse=True)
        return [d for d, _ in ranked[:top_n]]
    except Exception as e:
        logger.warning("Re-ranking failed (%s) — falling back to first %d retrieved chunks", e, top_n)
        return docs[:top_n]

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


def index_document(filename: str):
    """Incrementally add/update a single document in the index (no full rebuild)."""
    global rag_system
    if not rag_system:
        initialize_rag()
        return
    logger.info("Incrementally indexing '%s'...", filename)
    rag_system.add_document(filename)


def deindex_document(filename: str):
    """Remove a single document's chunks from the index (no full rebuild)."""
    global rag_system
    if not rag_system:
        return
    logger.info("Removing '%s' from index...", filename)
    rag_system.remove_document(filename)


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

        # Cross-encoder re-rank + cutoff — the BM25+semantic ensemble over-retrieves,
        # so this trims to the most relevant chunks before they hit the prompt
        docs = rerank_documents(query, docs)

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

        # Exact-match response cache — only safe on a session's first turn, since a
        # cached answer doesn't reflect any prior conversation context.
        from memory import get_session_history
        history = get_session_history(session_id)
        is_first_turn = len(history.messages) == 0
        cache_key = make_cache_key(query, language, context) if is_first_turn else None

        if cache_key:
            cached = get_cached_response(cache_key)
            if cached is not None:
                logger.info("Response cache hit for first-turn query")
                history.add_user_message(query)
                history.add_ai_message(cached)
                return {"response": cached, "sources": sources, "context": context}

        # Invoke chain with Redis-backed conversation history
        response = rag_system.rag_chain_with_history.invoke(
            {"context": context, "question": query, "language": language_name},
            config={"configurable": {"session_id": session_id}},
        )

        if cache_key:
            set_cached_response(cache_key, response)

        return {"response": response, "sources": sources, "context": context}

    except Exception as e:
        logger.error("RAG Error: %s", e)
        return {"response": "Error processing request.", "sources": [], "context": ""}
