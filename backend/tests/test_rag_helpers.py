from langchain_core.documents import Document

from rag import _is_structural_query, _format_chunk


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
