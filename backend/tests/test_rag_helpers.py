from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

from rag import (
    _is_structural_query, _format_chunk, pick_model, rewrite_query, _append_caveat_if_low_context,
    _build_source_citations, _citation_filenames, _sanitize_citations,
    _find_stream_cut, _sanitize_stream_buffer,
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
