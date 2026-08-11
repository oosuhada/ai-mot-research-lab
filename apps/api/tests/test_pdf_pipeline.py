from research_lab.pdf_pipeline import _chunk_text, _infer_section


def test_chunk_text_preserves_offsets_and_overlap() -> None:
    text = "Introduction\n" + ("evidence " * 500)
    chunks = _chunk_text(text, size=300, overlap=40)
    assert len(chunks) > 2
    assert chunks[0][0] == 0
    assert all(chunk for _, chunk in chunks)
    assert chunks[1][0] < 300


def test_section_inference_uses_short_first_line() -> None:
    assert _infer_section("Methods\nWe used a survey.", 3) == "Methods"
    assert _infer_section("word " * 50, 4) == "Page 4"
