"""
rag.py — Public API for the RAG system.
Initializes the singleton instance and provides interface methods.
"""
from typing import Dict, Any
from vectorstore import LangChainRAG

# Singleton instance
rag_system = None


def initialize_rag():
    global rag_system
    rag_system = LangChainRAG()
    if not rag_system.vectorstore:
        rag_system.create_vectorstore(rag_system.load_documents())


def refresh_documents():
    """Refresh documents from blob storage and rebuild the vector store."""
    global rag_system
    if rag_system:
        print("🔄 Refreshing documents from blob storage...")
        rag_system.create_vectorstore(rag_system.load_documents())
        print("✓ Documents refreshed successfully")


def get_rag_response(query: str, language: str = "en", session_id: str = "default") -> Dict[str, Any]:
    """
    Returns dict: {"response": str, "sources": list[str]}
    Sources are the document filenames that contributed context to the answer.
    """
    global rag_system
    if not rag_system:
        initialize_rag()

    if not rag_system.vectorstore:
        return {
            "response": "System is running in basic mode (no documents indexed). Please add documents to enable RAG.",
            "sources": [],
        }

    if not rag_system.rag_chain_with_history:
        rag_system._build_rag_chain()

    language_map = {"en": "English", "hi": "Hindi", "ta": "Tamil", "te": "Telugu"}
    language_name = language_map.get(language, "English")

    try:
        # Retrieve relevant docs with score threshold
        retriever = rag_system.get_retriever()
        docs = retriever.invoke(query)

        # Collect unique source filenames
        sources = list(set(d.metadata.get("source", "Unknown") for d in docs))
        context = "\n\n".join(d.page_content for d in docs) if docs else "No relevant context found."

        # Invoke chain with Redis-backed conversation history
        response = rag_system.rag_chain_with_history.invoke(
            {"context": context, "question": query, "language": language_name},
            config={"configurable": {"session_id": session_id}},
        )

        return {"response": response, "sources": sources}

    except Exception as e:
        print(f"RAG Error: {e}")
        return {"response": "Error processing request.", "sources": []}
