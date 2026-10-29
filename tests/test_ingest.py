import pytest

from booktures.pipeline.ingest import UnsupportedFormat, detect_format, parse_book
from tests.conftest import FIXTURES, SAMPLE_MD, SAMPLE_PDF


def test_pdf_pages_and_running_header_removed():
    book = parse_book(SAMPLE_PDF)
    assert book.title == "The Lantern Keeper of Gull Point"
    assert book.format == "pdf"
    assert len(book.pages) == 9
    # The running header (book title) and page numbers are stripped.
    assert book.pages[1].startswith("Her grandfather Tobias kept the light.")
    assert not any(p.strip().endswith(("\n2", "\n3")) for p in book.pages)
    assert "keeping the light." in book.pages[-1]


def test_max_pages_limits_book():
    assert len(parse_book(SAMPLE_PDF, max_pages=3).pages) == 3


def test_markdown_title_and_chunking():
    book = parse_book(SAMPLE_MD)
    assert book.title == "The Lantern Keeper of Gull Point"
    assert book.format == "md"
    assert 2 <= len(book.pages) <= 6
    assert all(len(p) <= 3000 for p in book.pages)
    assert "#" not in book.pages[0][:5]


def test_epub_spine_order_and_metadata():
    book = parse_book(FIXTURES / "tiny.epub")
    assert book.title == "The Tiny Voyage"
    assert book.author == "A. Tester"
    joined = "\n".join(book.pages)
    assert joined.index("Chapter One") < joined.index("Chapter Two")
    assert "green coat" in joined
    assert "p{}" not in joined  # <style> skipped


def test_plain_text_hard_wraps_joined(tmp_path):
    f = tmp_path / "wrapped.txt"
    f.write_text("The ship sailed\nout of the bay at dawn.\n\nA second paragraph that is long enough.\n")
    book = parse_book(f)
    assert "The ship sailed out of the bay at dawn." in book.pages[0]
    assert book.title == "Wrapped"


def test_unsupported_format():
    with pytest.raises(UnsupportedFormat):
        detect_format("novel.docx")


def test_empty_file_rejected(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("   \n\n ")
    with pytest.raises(ValueError):
        parse_book(f)
