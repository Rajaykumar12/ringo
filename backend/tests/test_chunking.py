from vectorstore import _split_into_paragraphs, _looks_like_heading, _pack_paragraphs


def test_split_into_paragraphs_splits_on_blank_lines():
    text = "First paragraph.\n\nSecond paragraph.\n\n\nThird paragraph."
    assert _split_into_paragraphs(text) == [
        "First paragraph.",
        "Second paragraph.",
        "Third paragraph.",
    ]


def test_split_into_paragraphs_strips_and_drops_empty():
    text = "  Only paragraph.  \n\n   \n\n"
    assert _split_into_paragraphs(text) == ["Only paragraph."]


def test_looks_like_heading_true_for_short_no_punctuation_line():
    assert _looks_like_heading("Chapter 3: Data Pipelines") is True


def test_looks_like_heading_false_for_sentence():
    assert _looks_like_heading("This is a full sentence that ends with a period.") is False


def test_looks_like_heading_false_for_multiline():
    assert _looks_like_heading("Line one\nLine two") is False


def test_looks_like_heading_false_for_long_line():
    assert _looks_like_heading("x" * 81) is False


def test_pack_paragraphs_merges_short_paragraphs_into_one_chunk():
    paragraphs = ["Short one.", "Short two.", "Short three."]
    chunks = _pack_paragraphs(paragraphs, chunk_size=200, chunk_overlap=20)
    assert chunks == ["Short one.\n\nShort two.\n\nShort three."]


def test_pack_paragraphs_starts_new_chunk_at_heading():
    paragraphs = ["Intro paragraph about the topic.", "Section Two", "Body text for section two."]
    chunks = _pack_paragraphs(paragraphs, chunk_size=200, chunk_overlap=20)
    assert chunks == [
        "Intro paragraph about the topic.",
        "Section Two\n\nBody text for section two.",
    ]


def test_pack_paragraphs_splits_when_size_exceeded():
    paragraphs = ["a" * 50, "b" * 50, "c" * 50]
    chunks = _pack_paragraphs(paragraphs, chunk_size=80, chunk_overlap=10)
    assert len(chunks) == 3
    assert chunks[0] == "a" * 50
    assert chunks[1] == "b" * 50
    assert chunks[2] == "c" * 50


def test_pack_paragraphs_falls_back_to_splitter_for_oversized_paragraph():
    huge_paragraph = "word " * 400  # far larger than chunk_size
    chunks = _pack_paragraphs([huge_paragraph], chunk_size=100, chunk_overlap=10)
    assert len(chunks) > 1
    assert all(len(c) <= 100 for c in chunks)
