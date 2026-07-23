"""
rag.py — Public API for the RAG system.
Initializes the singleton instance and provides interface methods.
"""
import logging
import os
import re
from typing import Dict, Any, List, Tuple
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


ENABLE_QUERY_REWRITE = os.environ.get("ENABLE_QUERY_REWRITE", "true").lower() == "true"
_QUERY_REWRITE_MODEL = "llama-3.1-8b-instant"
_QUERY_REWRITE_MIN_LEN = 15  # below this there's not enough signal to usefully rephrase
_QUERY_REWRITE_COUNT = 2


def rewrite_query(query: str) -> List[str]:
    """Generate alternate phrasings of the query to widen hybrid-retrieval recall on
    vague or multi-part questions. Skipped for structural queries (already routed to
    dedicated structure chunks) and short queries. Never raises — falls back to no
    rewrites so retrieval still runs on the original query alone."""
    if not ENABLE_QUERY_REWRITE:
        return []
    if _is_structural_query(query) or len(query) < _QUERY_REWRITE_MIN_LEN:
        return []
    try:
        from groq import Groq
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        prompt = (
            f"Rewrite this question into {_QUERY_REWRITE_COUNT} alternate phrasings that "
            "would help a search engine retrieve the same information. One phrasing per "
            "line, no numbering, no extra commentary.\n\nQuestion: " + query
        )
        resp = client.chat.completions.create(
            model=_QUERY_REWRITE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
            temperature=0.3,
        )
        lines = [ln.strip("-•* \t") for ln in resp.choices[0].message.content.strip().splitlines()]
        variants = [ln for ln in lines if ln and ln.lower() != query.strip().lower()]
        return variants[:_QUERY_REWRITE_COUNT]
    except Exception as e:
        logger.warning("Query rewrite failed (%s) — retrieving on original query only", e)
        return []


# Conservative thresholds — false negatives (using the big model when the small one
# would've sufficed) are cheap; false positives (routing a genuinely complex question
# to the 8B model) degrade answer quality, so bias toward "default".
_FAST_MAX_QUERY_LEN = 60
_FAST_MAX_DOCS = 3
_FAST_MAX_CONTEXT_LEN = 800
_FAST_MAX_HISTORY_LEN = 2


def pick_model(query: str, docs: List[Document], context: str, history_len: int = 0) -> str:
    """Route short, simple, early-conversation queries to the cheaper/faster model tier."""
    if _is_structural_query(query):
        return "default"
    if len(query) > _FAST_MAX_QUERY_LEN:
        return "default"
    if len(docs) > _FAST_MAX_DOCS or len(context) > _FAST_MAX_CONTEXT_LEN:
        return "default"
    if history_len > _FAST_MAX_HISTORY_LEN:
        return "default"
    return "fast"


MAX_RESPONSE_IMAGES = 4

# Cross-encoder relevance cutoff for whether an image gets advertised/surfaced at all.
# ms-marco-MiniLM scores are raw logits, not probabilities — positive generally means
# the pair is actually relevant, negative means it's just top-k filler (e.g. small talk
# still pulling back document chunks). Prevents unrelated figures from tagging along.
IMAGE_RELEVANCE_THRESHOLD = float(os.environ.get("IMAGE_RELEVANCE_THRESHOLD", "0.0"))


def _relevant_image_ids(query: str, docs: List[Document], threshold: float = IMAGE_RELEVANCE_THRESHOLD) -> set:
    """Score only the chunks that actually carry images against the query, and keep
    just the ones the cross-encoder considers genuinely relevant. Runs independently of
    rerank_documents' top_n cutoff, which is skipped entirely for small doc counts."""
    candidates = [d for d in docs if d.metadata.get("image_ids")]
    if not candidates:
        return set()
    try:
        encoder = _get_cross_encoder()
        pairs = [[query, d.page_content] for d in candidates]
        scores = encoder.predict(pairs)
    except Exception as e:
        logger.warning("Image relevance scoring failed (%s) — allowing all candidate images", e)
        scores = [threshold] * len(candidates)
    ids = set()
    for d, score in zip(candidates, scores):
        if score >= threshold:
            ids.update(i for i in d.metadata.get("image_ids", "").split(",") if i)
    return ids


def _collect_images(docs: List[Document], relevant_image_ids: set, limit: int = MAX_RESPONSE_IMAGES) -> List[str]:
    """Dedup image_ids across retrieved chunks' metadata (restricted to ids the relevance
    gate approved), cap at `limit`, return as /images/{id} URL paths in first-seen order."""
    seen: List[str] = []
    for d in docs:
        raw = d.metadata.get("image_ids", "")
        if not raw:
            continue
        for img_id in raw.split(","):
            if img_id and img_id in relevant_image_ids and img_id not in seen:
                seen.append(img_id)
                if len(seen) >= limit:
                    return [f"/images/{i}" for i in seen]
    return [f"/images/{i}" for i in seen]


def _format_chunk(doc: Document, relevant_image_ids: set = frozenset()) -> str:
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
    lines = [header, doc.page_content]
    raw_ids = meta.get("image_ids", "")
    for img_id in raw_ids.split(","):
        if img_id and img_id in relevant_image_ids:
            lines.append(f"[Image available: /images/{img_id}]")
    return "\n".join(lines)


# Matches any markdown image pointing at /images/..., valid hex id or not — the model
# sometimes "prettifies" the id into a fake filename (e.g. figure-9-2.png), which this
# needs to catch and strip too, not just malformed-but-hex-shaped ids.
_IMAGE_MD_RE = re.compile(r"!\[[^\]]*\]\(/images/([^)]+)\)")
_VALID_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _sanitize_and_filter_images(response: str, images: List[str], valid_ids: set) -> Tuple[str, List[str]]:
    """Strip any inline markdown image whose id isn't an exact, actually-advertised
    image id (hallucination guard — catches both invented filenames and wrong/reused
    hex ids), then drop already-inlined ids from the fallback `images` list to avoid dupes."""

    def _strip_invalid(m: "re.Match") -> str:
        img_id = m.group(1)
        return m.group(0) if _VALID_ID_RE.match(img_id) and img_id in valid_ids else ""

    clean_response = _IMAGE_MD_RE.sub(_strip_invalid, response)
    used_ids = set(_IMAGE_MD_RE.findall(clean_response))
    filtered_images = [img for img in images if img.rsplit("/", 1)[-1] not in used_ids]
    return clean_response, filtered_images


LOW_CONTEXT_CAVEAT = (
    "\n\n_Note: no closely matching content was found in your documents for this "
    "question — this answer may not be well-grounded in your uploaded material._"
)


def _append_caveat_if_low_context(response: str, low_context: bool) -> str:
    """Cheap, non-LLM groundedness signal: flag responses generated with zero retrieved
    chunks. This is a heuristic floor, not the full LLM-judge faithfulness score (that
    still runs async via eval.py/_eval_and_update and is surfaced in the admin dashboard) —
    kept synchronous and free of extra LLM calls so it never adds response latency."""
    if low_context and LOW_CONTEXT_CAVEAT.strip() not in response:
        return response + LOW_CONTEXT_CAVEAT
    return response


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


def get_rag_response(query: str, session_id: str = "default") -> Dict[str, Any]:
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
            "images": [],
            "context": "",
        }

    if not rag_system.rag_chain_with_history:
        rag_system._build_rag_chain()

    try:
        # Retrieve relevant docs — original query plus any rewritten variants, merged.
        # Reranking below still scores against the original query, so this only widens
        # recall; it doesn't change what "relevant" means.
        retriever = rag_system.get_retriever()
        docs: List[Document] = []
        for variant in [query] + rewrite_query(query):
            docs.extend(retriever.invoke(variant))

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

        # Collect unique source filenames and any images tied to the retrieved chunks
        sources = list(set(d.metadata.get("source", "Unknown") for d in docs))
        relevant_image_ids = _relevant_image_ids(query, docs)
        images = _collect_images(docs, relevant_image_ids)
        context = "\n\n".join(_format_chunk(d, relevant_image_ids) for d in docs) if docs else "No relevant context found."
        low_context = len(docs) == 0

        # Exact-match response cache — only safe on a session's first turn, since a
        # cached answer doesn't reflect any prior conversation context.
        from memory import get_session_history
        history = get_session_history(session_id)
        is_first_turn = len(history.messages) == 0
        cache_key = make_cache_key(query, context) if is_first_turn else None

        if cache_key:
            cached = get_cached_response(cache_key)
            if cached is not None:
                logger.info("Response cache hit for first-turn query")
                cached, cache_images = _sanitize_and_filter_images(cached, images, relevant_image_ids)
                history.add_user_message(query)
                history.add_ai_message(cached)
                cached = _append_caveat_if_low_context(cached, low_context)
                return {"response": cached, "sources": sources, "images": cache_images, "context": context, "model_tier": "cache"}

        # Route to the fast/cheap model tier for short, simple, early-conversation queries
        model_tier = pick_model(query, docs, context, len(history.messages))
        chain = (
            rag_system.rag_chain_fast_with_history
            if model_tier == "fast" and rag_system.rag_chain_fast_with_history
            else rag_system.rag_chain_with_history
        )

        # Invoke chain with Redis-backed conversation history
        response = chain.invoke(
            {"context": context, "question": query},
            config={"configurable": {"session_id": session_id}},
        )

        if cache_key:
            set_cached_response(cache_key, response)

        response, images = _sanitize_and_filter_images(response, images, relevant_image_ids)
        response = _append_caveat_if_low_context(response, low_context)

        return {"response": response, "sources": sources, "images": images, "context": context, "model_tier": model_tier}

    except Exception as e:
        logger.error("RAG Error: %s", e)
        return {"response": "Error processing request.", "sources": [], "images": [], "context": ""}
