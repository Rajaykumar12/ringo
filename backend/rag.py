"""
rag.py — Public API for the RAG system.
Initializes the singleton instance and provides interface methods.
"""
import hashlib
import json
import logging
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional, Tuple
from langchain_core.documents import Document
from vectorstore import LangChainRAG
from response_cache import make_cache_key, get_cached_response, set_cached_response

logger = logging.getLogger("ringo.rag")

# Singleton instance
rag_system = None

_cross_encoder = None
RERANK_MODEL = os.environ.get("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
RERANK_TOP_N = int(os.environ.get("RERANK_TOP_N", "10"))
# ms-marco-MiniLM emits raw logits. Measured on this corpus (chunk-level): clear questions
# have their best chunks at roughly +5 to +8, while off-topic ones ("capital of France")
# top out near -2.4 and the rest sit below -10. Chunks under this floor are dropped rather
# than shown as citations / sent as context. Greetings are handled separately (they score
# deceptively high, ~-1.7, so they skip retrieval outright — see _is_small_talk).
RERANK_MIN_SCORE = float(os.environ.get("RERANK_MIN_SCORE", "-2.0"))


# Double-checked locking: without it, two concurrent cold-start requests can both
# see None and each load the ~90MB model, committing the memory twice before one
# result is discarded.
_cross_encoder_lock = threading.Lock()


def _get_cross_encoder():
    global _cross_encoder
    if _cross_encoder is None:
        with _cross_encoder_lock:
            if _cross_encoder is None:
                from sentence_transformers import CrossEncoder
                _cross_encoder = CrossEncoder(RERANK_MODEL)
                logger.info("Cross-encoder re-ranker loaded: %s", RERANK_MODEL)
    return _cross_encoder


def rerank_documents(query: str, docs: List[Document], top_n: int = RERANK_TOP_N,
                     min_score: float = RERANK_MIN_SCORE) -> List[Document]:
    """Cross-encoder re-rank + cutoff so the merged BM25+semantic hit list doesn't
    balloon the prompt with noisy, low-relevance chunks as the corpus grows.

    Always scores (even when len(docs) <= top_n) so `min_score` can drop chunks that are
    merely the nearest neighbours of an off-topic query like "Hello". Without that floor
    retrieval always "succeeds" and every message gets a full set of unrelated citations."""
    if not docs:
        return docs
    try:
        encoder = _get_cross_encoder()
        pairs = [[query, d.page_content] for d in docs]
        scores = encoder.predict(pairs)
        ranked = sorted(zip(docs, scores), key=lambda pair: pair[1], reverse=True)
        return [d for d, score in ranked[:top_n] if score >= min_score]
    except Exception as e:
        logger.warning("Re-ranking failed (%s) — falling back to first %d retrieved chunks", e, top_n)
        return docs[:top_n]

_STRUCTURAL_KW = frozenset([
    "section", "chapter", "topic", "overview", "outline", "contents",
    "table of contents", "index", "structure", "what is in", "what are",
    "list all", "list the", "slide", "slides", "cover", "about this",
    "this book", "this document", "this presentation",
])


_SMALL_TALK_RE = re.compile(
    r"^\s*(hi|hello|hey|yo|thanks|thank you|ok|okay|bye|good (morning|afternoon|evening))"
    r"(\s+(there|ringo|everyone))?\s*[!.?]*\s*$",
    re.IGNORECASE,
)


def _is_small_talk(query: str) -> bool:
    return bool(_SMALL_TALK_RE.match(query))


def _is_structural_query(query: str) -> bool:
    q = query.lower()
    return any(kw in q for kw in _STRUCTURAL_KW)


ENABLE_QUERY_REWRITE = os.environ.get("ENABLE_QUERY_REWRITE", "true").lower() == "true"
_QUERY_REWRITE_MODEL = "openai/gpt-oss-20b"
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
            f"Rewrite this question into {_QUERY_REWRITE_COUNT} short search queries that "
            "would retrieve the same information from a textbook. Use the technical terms a "
            "textbook would use, and drop request phrasing such as \"give me\", \"show me\" or "
            "\"can you\". One query per line, no numbering, no extra commentary.\n\nQuestion: " + query
        )
        resp = client.chat.completions.create(
            model=_QUERY_REWRITE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            # gpt-oss is a reasoning model: at the default effort its hidden reasoning tokens
            # can consume a small max_tokens budget and leave the answer empty or cut off.
            max_tokens=300,
            reasoning_effort="low",
            temperature=0.3,
        )
        lines = [ln.strip("-•* \t") for ln in (resp.choices[0].message.content or "").strip().splitlines()]
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
# Same scale as RERANK_MIN_SCORE. It used to be 0.0, which sat above genuinely relevant pages
# (a page the query was clearly about scored -0.1 and its figure was dropped).
IMAGE_RELEVANCE_THRESHOLD = float(os.environ.get("IMAGE_RELEVANCE_THRESHOLD", str(RERANK_MIN_SCORE)))


def _image_captions(meta: Dict[str, Any]) -> Dict[str, str]:
    """{image_id: caption} parsed from a chunk's `image_captions` metadata (a JSON string,
    since Chroma metadata values must be scalars). Missing/corrupt -> {}."""
    raw = meta.get("image_captions")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, str)} if isinstance(data, dict) else {}


_FIGURE_QUERY_RE = re.compile(
    r"\b(diagram|figure|fig|illustration|picture|image|chart|schematic|visual)s?\b", re.IGNORECASE)
FIGURE_CAPTION_TOP_K = 3
FIGURE_CAPTION_MIN_SCORE = float(os.environ.get("FIGURE_CAPTION_MIN_SCORE", "-2.5"))
_caption_index_cache: Tuple[int, List[Tuple[str, Any, str]]] = (-1, [])


def _is_figure_query(query: str) -> bool:
    return bool(_FIGURE_QUERY_RE.search(query))


def _caption_index() -> List[Tuple[str, Any, str]]:
    """(source, page, caption) for every captioned figure in the index, rebuilt only when
    the collection size changes (i.e. after an ingest/delete)."""
    global _caption_index_cache
    collection = rag_system.vectorstore._collection
    count = collection.count()
    if _caption_index_cache[0] != count:
        seen, entries = set(), []
        for meta in collection.get(include=["metadatas"])["metadatas"]:
            for caption in _image_captions(meta or {}).values():
                key = (meta.get("source"), meta.get("page"), caption)
                if key not in seen:
                    seen.add(key)
                    entries.append(key)
        _caption_index_cache = (count, entries)
    return _caption_index_cache[1]


def _figure_caption_docs(queries: List[str]) -> List[Document]:
    """For "show me the diagram of X" questions, page text alone retrieves poorly (the
    query is mostly request phrasing, and a figure's page is often mostly prose about
    something else). Match the query and its rewrites directly against figure captions
    and pull in the chunks of the pages whose captions match."""
    try:
        entries = _caption_index()
        if not entries:
            return []
        encoder = _get_cross_encoder()
        best = [float("-inf")] * len(entries)
        for q in queries:
            for i, score in enumerate(encoder.predict([[q, cap] for _, _, cap in entries])):
                best[i] = max(best[i], float(score))
        top = sorted(range(len(entries)), key=best.__getitem__, reverse=True)[:FIGURE_CAPTION_TOP_K]
        docs: List[Document] = []
        for i in top:
            if best[i] < FIGURE_CAPTION_MIN_SCORE:
                continue
            source, page, caption = entries[i]
            label = caption[:12]  # e.g. "Figure 3-4. "; caption text is in exactly one chunk of the page
            res = rag_system.vectorstore._collection.get(
                where={"$and": [{"source": source}, {"page": page}]}, include=["documents", "metadatas"])
            docs.extend(Document(page_content=t, metadata=m)
                        for t, m in zip(res["documents"], res["metadatas"]) if t and label in t)
        return docs
    except Exception as e:
        logger.warning("Figure caption search failed (non-fatal): %s", e)
        return []


def _relevant_image_ids(query: str, docs: List[Document], threshold: float = IMAGE_RELEVANCE_THRESHOLD,
                        alt_queries: Tuple[str, ...] = ()) -> set:
    """Score each image against the query and keep the ones the cross-encoder considers
    relevant. An image with an extracted caption is judged on its own caption, so a
    relevant page doesn't drag along its unrelated figures; an uncaptioned image falls
    back to its page's text. Runs independently of rerank_documents' top_n cutoff."""
    entries = []  # (image_id, text to score against the query)
    for d in docs:
        captions = _image_captions(d.metadata)
        for img_id in d.metadata.get("image_ids", "").split(","):
            if img_id:
                entries.append((img_id, captions.get(img_id) or d.page_content))
    if not entries:
        return set()
    try:
        encoder = _get_cross_encoder()
        # Best score across the original query and its rewrites: a request like "give me the
        # diagram of X" is mostly phrasing, and the rewrite (just "X diagram") matches captions better.
        scores = [max(row) for row in zip(*(
            encoder.predict([[q, text] for _, text in entries]) for q in (query, *alt_queries)))]
    except Exception as e:
        logger.warning("Image relevance scoring failed (%s) — allowing all candidate images", e)
        scores = [threshold] * len(entries)
    ids = set()
    for (img_id, _), score in zip(entries, scores):
        if score >= threshold:
            ids.add(img_id)
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


def _format_chunk(doc: Document, relevant_image_ids: set = frozenset(), index: Optional[int] = None) -> str:
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
    if index is not None:
        header = f"[{index}] {header}"
    lines = [header, doc.page_content]
    raw_ids = meta.get("image_ids", "")
    captions = _image_captions(meta)
    for img_id in raw_ids.split(","):
        if img_id and img_id in relevant_image_ids:
            caption = captions.get(img_id)
            lines.append(f"[Image available: /images/{img_id} | caption: {caption}]" if caption
                         else f"[Image available: /images/{img_id}]")
    return "\n".join(lines)


def _build_source_citations(docs: List[Document]) -> List[Dict[str, Any]]:
    """One entry per retrieved chunk, 1-indexed to match the "[n]" markers embedded in
    the context by _format_chunk and the citation instructions in the system prompt
    (vectorstore.py:_wrap_chain). Replaces the old flat, deduped-by-filename source list —
    citations point at a specific chunk, not just "this file was involved somewhere"."""
    citations = []
    for i, d in enumerate(docs, start=1):
        meta = d.metadata
        citations.append({
            "index": i,
            "filename": meta.get("source", "Unknown"),
            "page": meta.get("page") or None,
            "slide": meta.get("slide") or None,
            "preview": d.page_content[:200].strip(),
        })
    return citations


def _citation_filenames(sources: List[Dict[str, Any]]) -> List[str]:
    """Distinct filenames from a structured citation list, in first-seen order — for
    plain-text logging (rag_logger stores a joined filename string, not structured data)."""
    seen: List[str] = []
    for s in sources:
        fn = s.get("filename")
        if fn and fn not in seen:
            seen.append(fn)
    return seen


_CITATION_RE = re.compile(r"\[(\d+)\]")


def _sanitize_citations(response: str, valid_indices: set) -> str:
    """Strip any [n] citation marker the LLM emitted that doesn't correspond to an
    actual numbered source chunk (hallucination guard — same reasoning as
    _sanitize_and_filter_images for image ids)."""
    def _strip_invalid(m: "re.Match") -> str:
        try:
            n = int(m.group(1))
        except ValueError:
            return m.group(0)
        return m.group(0) if n in valid_indices else ""

    return _CITATION_RE.sub(_strip_invalid, response)


# Matches any markdown image pointing at /images/..., valid hex id or not — the model
# sometimes "prettifies" the id into a fake filename (e.g. figure-9-2.png), which this
# needs to catch and strip too, not just malformed-but-hex-shaped ids.
_IMAGE_MD_RE = re.compile(r"!\[[^\]]*\]\(/images/([^)]+)\)")
# Deliberately matches ANY markdown image target, not just /images/ ones. The
# sanitizer below is an allow-list: anything that isn't an advertised local image
# id gets dropped. Scoping this pattern to /images/ would mean an external target
# (e.g. an attacker-controlled https:// URL emitted via prompt injection in an
# indexed document) never matches at all, and so silently survives sanitization
# and gets auto-loaded by the browser as an exfiltration beacon.
_ANY_IMAGE_MD_RE = re.compile(r"!\[[^\]]*\]\(([^)]*)\)")
_VALID_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _sanitize_and_filter_images(response: str, images: List[str], valid_ids: set) -> Tuple[str, List[str]]:
    """Strip any inline markdown image whose id isn't an exact, actually-advertised
    image id (hallucination guard — catches both invented filenames and wrong/reused
    hex ids), then drop already-inlined ids from the fallback `images` list to avoid dupes."""

    def _strip_invalid(m: "re.Match") -> str:
        target = m.group(1).strip()
        if not target.startswith("/images/"):
            return ""  # external origin, data:, or relative — never renderable here
        img_id = target[len("/images/"):]
        return m.group(0) if _VALID_ID_RE.match(img_id) and img_id in valid_ids else ""

    clean_response = _ANY_IMAGE_MD_RE.sub(_strip_invalid, response)
    used_ids = set(_IMAGE_MD_RE.findall(clean_response))
    filtered_images = [img for img in images if img.rsplit("/", 1)[-1] not in used_ids]
    return clean_response, filtered_images


# Combined pattern for the incremental streaming sanitizer below — image branch first
# since it structurally contains a "[...]" too (the alt-text brackets), so it should
# get first shot at matching before the bare-citation branch is tried at that position.
_STREAM_PATTERN_RE = re.compile(
    r"(?:!\[[^\]]*\]\(/images/(?P<img_id>[^)]+)\))|(?:\[(?P<cite_num>\d+)\])"
)

_STREAM_HOLDBACK_CAP = 200  # generous upper bound on "[n]" / "![](/images/<32 hex>)"


def _find_stream_cut(tail: str) -> int:
    """Position in `tail` (the text after the last fully-resolved pattern) up to which
    it's safe to emit right now — i.e. contains no "[" or "!" that could still resolve
    into a citation/image marker once more streamed text arrives. Scans left to right,
    skipping past any "[" or "!" already provably NOT the start of such a pattern
    (wrong next character), and only holding back when genuinely still-forming or when
    there isn't enough lookahead yet to tell."""
    i, n = 0, len(tail)
    while i < n:
        ch = tail[i]
        if ch == "[":
            j = i + 1
            while j < n and tail[j].isdigit():
                j += 1
            if j == i + 1:
                # "[" not (yet) followed by a digit
                if j == n:
                    return i  # "[" is the last char received so far — still ambiguous
                i = j
                continue
            if j == n:
                return i  # digits accumulating, no terminator yet — hold back
            # A non-digit followed the digit run and it isn't "]" (a real "[n]" would
            # already have been consumed by finditer before this function ever runs) —
            # this can never become a valid citation now; resume scanning past it.
            i = j
            continue
        if ch == "!":
            if i + 1 >= n:
                return i  # could still be followed by "[" once more data arrives
            if tail[i + 1] == "[":
                return i  # "![" forming — hold back for finditer to resolve once complete
            i += 1
            continue
        i += 1
    return n


def _sanitize_stream_buffer(buffer: str, valid_citation_indices: set, valid_image_ids: set) -> Tuple[str, str]:
    """Streaming-safe version of _sanitize_citations + _sanitize_and_filter_images:
    resolves every complete [n]/image marker found so far in `buffer` (stripping
    hallucinated ones, same validity rules as the non-streaming sanitizers) and holds
    back any trailing text that could still be the start of an unfinished marker — e.g.
    a chunk boundary landing between "[1" and "]" — so a hallucinated citation is never
    shown to the client even for one frame. Returns (safe_text_to_emit, unresolved_tail);
    the tail should be prepended to the next chunk before calling this again."""
    parts = []
    last_end = 0
    for m in _STREAM_PATTERN_RE.finditer(buffer):
        parts.append(buffer[last_end:m.start()])
        img_id = m.group("img_id")
        if img_id is not None:
            if _VALID_ID_RE.match(img_id) and img_id in valid_image_ids:
                parts.append(m.group(0))
        else:
            if int(m.group("cite_num")) in valid_citation_indices:
                parts.append(m.group(0))
        last_end = m.end()
    tail = buffer[last_end:]

    cut = _find_stream_cut(tail)
    if len(tail) - cut > _STREAM_HOLDBACK_CAP:
        # Pathological: a held-back fragment that's grown past any real pattern's
        # possible length without resolving (e.g. a stray "!" that never became "!["
        # within a reasonable window). Force-flush rather than swallowing content forever.
        cut = len(tail)

    return "".join(parts) + tail[:cut], tail[cut:]


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


def prepare_context(query: str) -> Dict[str, Any]:
    """Single source of truth for the retrieval half of a RAG turn.

    Both chat paths call this — main.py's streaming branch and get_rag_response()
    below. They used to be hand-maintained copies of the same pipeline and had
    drifted: query rewriting and the response cache existed only on the
    non-streaming side, so the default (streaming) UX paid full retrieval + full
    generation for every repeated question and returned different answers from
    the same query.

    Returns everything the generation half needs: docs, citations, the numbered
    context string, and the image allow-list the sanitizers validate against.
    """
    if _is_small_talk(query):
        # "Hello" has no information need: retrieval would only return the nearest
        # unrelated chunks, which then surface as bogus citations.
        return {
            "docs": [], "sources": [], "valid_citation_indices": set(),
            "relevant_image_ids": set(), "candidate_images": [],
            "context": "No relevant context found.", "low_context": False,
        }

    retriever = rag_system.get_retriever()

    # Original query plus any rewritten variants. These retrievals are fully
    # independent, so fan them out — run serially this was rewrite + 3x the cost
    # of a hybrid BM25 + embedding + Chroma round-trip. Reranking below still
    # scores against the original query, so this only widens recall; it doesn't
    # change what "relevant" means.
    variants = [query] + rewrite_query(query)
    if len(variants) == 1:
        results = [retriever.invoke(query)]
    else:
        with ThreadPoolExecutor(max_workers=len(variants)) as pool:
            results = list(pool.map(retriever.invoke, variants))  # order preserved

    # Deduplicate by content hash. sha256, not the builtin hash(): str hashing is
    # salted per process via PYTHONHASHSEED, which makes dedup non-reproducible
    # across restarts.
    seen: set = set()
    docs: List[Document] = []
    for batch in results:
        for d in batch:
            h = hashlib.sha256(d.page_content.strip().encode("utf-8")).digest()
            if h not in seen:
                seen.add(h)
                docs.append(d)

    # Figure-seeking queries also search figure captions directly (adds candidate chunks;
    # the re-rank below still decides what survives).
    figure_docs: List[Document] = _figure_caption_docs(variants) if _is_figure_query(query) else []

    # Cross-encoder re-rank + cutoff — the BM25+semantic ensemble over-retrieves,
    # so this trims to the most relevant chunks before they hit the prompt
    docs = rerank_documents(query, docs)

    # Caption matches already passed their own (caption-level) relevance floor; the
    # page-text floor above, scored against the raw request phrasing, would discard them.
    kept = {hashlib.sha256(d.page_content.strip().encode("utf-8")).digest() for d in docs}
    for d in figure_docs:
        h = hashlib.sha256(d.page_content.strip().encode("utf-8")).digest()
        if h not in kept:
            kept.add(h)
            docs.append(d)

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

    # Structured, 1-indexed source citations (one per chunk) and any images tied to
    # the retrieved chunks. Context chunks are numbered [1], [2], ... to match —
    # the system prompt instructs the LLM to cite that number inline.
    relevant_image_ids = _relevant_image_ids(query, docs, alt_queries=tuple(variants[1:]))
    return {
        "docs": docs,
        "sources": _build_source_citations(docs),
        "valid_citation_indices": set(range(1, len(docs) + 1)),
        "relevant_image_ids": relevant_image_ids,
        "candidate_images": _collect_images(docs, relevant_image_ids),
        "context": (
            "\n\n".join(_format_chunk(d, relevant_image_ids, index=i) for i, d in enumerate(docs, start=1))
            if docs else "No relevant context found."
        ),
        "low_context": len(docs) == 0,
    }


def get_rag_response(query: str, session_id: str = "default") -> Dict[str, Any]:
    """
    Returns dict: {"response": str, "sources": list[dict], "context": str, ...}
    Each source is {"index", "filename", "page", "slide", "preview"} — one per retrieved
    chunk, 1-indexed to match the "[n]" inline citations the response may contain.
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
        prep = prepare_context(query)
        docs = prep["docs"]
        sources = prep["sources"]
        valid_citation_indices = prep["valid_citation_indices"]
        relevant_image_ids = prep["relevant_image_ids"]
        images = prep["candidate_images"]
        context = prep["context"]
        low_context = prep["low_context"]

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
                cached = _sanitize_citations(cached, valid_citation_indices)
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
        response = _sanitize_citations(response, valid_citation_indices)
        response = _append_caveat_if_low_context(response, low_context)

        return {"response": response, "sources": sources, "images": images, "context": context, "model_tier": model_tier}

    except Exception as e:
        logger.error("RAG Error: %s", e)
        return {"response": "Error processing request.", "sources": [], "images": [], "context": ""}
