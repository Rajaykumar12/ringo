from langchain_core.documents import Document

from rag import _is_structural_query, _format_chunk, pick_model


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
