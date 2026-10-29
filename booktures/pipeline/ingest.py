"""Turn an uploaded book (PDF, EPUB, TXT or Markdown) into a list of pages.

Each page is one illustration's worth of text. PDFs keep their own pages
(scanned pages go through OCR when Tesseract is installed); EPUB and plain
text are split into ~1,800-character pages on paragraph boundaries.
"""

from __future__ import annotations

import html
import importlib.util
import posixpath
import re
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

SUPPORTED = {".pdf": "pdf", ".epub": "epub", ".txt": "txt", ".md": "md", ".markdown": "md"}
TARGET_PAGE_CHARS = 1800


@dataclass
class ParsedBook:
    title: str
    author: str
    format: str
    pages: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class UnsupportedFormat(ValueError):
    pass


def detect_format(filename: str) -> str:
    fmt = SUPPORTED.get(Path(filename).suffix.lower())
    if not fmt:
        raise UnsupportedFormat(
            f"Unsupported file type '{Path(filename).suffix}'. Use PDF, EPUB, TXT or Markdown."
        )
    return fmt


def parse_book(
    path: Path, filename: str | None = None, max_pages: int = 0, page_chars: int = TARGET_PAGE_CHARS
) -> ParsedBook:
    """Read a book into pages. ``page_chars`` sets the page size for EPUB/TXT/MD (PDFs keep their pages)."""
    filename = filename or path.name
    fmt = detect_format(filename)
    if fmt == "pdf":
        book = _parse_pdf(path)
    elif fmt == "epub":
        book = _parse_epub(path, page_chars)
    else:
        book = _parse_text(path, fmt, page_chars)
    book.pages = [p for p in (_tidy(p) for p in book.pages) if len(p) >= 20]
    if max_pages and max_pages > 0:
        book.pages = book.pages[:max_pages]
    if not book.title:
        book.title = _title_from_filename(filename)
    if not book.pages:
        raise ValueError("No readable text found in this file.")
    return book


def _title_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    stem = re.sub(r"[_\-]+", " ", stem).strip()
    return stem[:1].upper() + stem[1:] if stem else "Untitled"


def _tidy(text: str) -> str:
    text = text.replace("\r", "")
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# -- PDF -----------------------------------------------------------------


def _norm_line(line: str) -> str:
    return re.sub(r"\d+", "#", line.strip().lower())


def _parse_pdf(path: Path) -> ParsedBook:
    import pymupdf

    doc = pymupdf.open(path)
    meta = doc.metadata or {}
    warnings: list[str] = []
    ocr_ready = importlib.util.find_spec("pytesseract") is not None
    ocr_used = ocr_missing = 0

    # Pass 1: raw text blocks per page, with their vertical position.
    raw_pages: list[list[tuple[str, float, float, float, float]]] = []
    for page in doc:
        entries = []
        for b in page.get_text("blocks", sort=True):
            if len(b) > 6 and b[6] != 0:  # image block
                continue
            x0, y0, x1, y1, text = b[:5]
            text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # de-hyphenate line breaks
            lines = max(1, text.count("\n") + (0 if text.endswith("\n") else 1))
            text = re.sub(r"\s*\n\s*", " ", text).strip()
            if text:
                entries.append((text, y0, y1, (y1 - y0) / lines, x0))
        if sum(len(e[0]) for e in entries) < 50:
            if ocr_ready:
                ocr_text = _ocr_page(page)
                if ocr_text.strip():
                    paras = [p.replace("\n", " ") for p in re.split(r"\n\s*\n", ocr_text) if p.strip()]
                    entries = [(p, i * 100.0, i * 100.0 + 10, 10.0, 0.0) for i, p in enumerate(paras)]
                    ocr_used += 1
            else:
                ocr_missing += 1
        raw_pages.append(entries)

    # Pass 2: drop running headers/footers — short blocks at the top or bottom of a
    # page that repeat (ignoring digits) across many pages — and bare page numbers.
    edge = Counter()
    for entries in raw_pages:
        for e in entries[:2] + entries[-2:]:
            if len(e[0]) < 90:
                edge[_norm_line(e[0])] += 1
    threshold = max(3, int(len(raw_pages) * 0.3))
    repeated = {k for k, n in edge.items() if n >= threshold}

    pages = []
    for entries in raw_pages:
        kept = []
        for i, e in enumerate(entries):
            at_edge = i < 2 or i >= len(entries) - 2
            if at_edge and (_norm_line(e[0]) in repeated or re.fullmatch(r"(page\s*)?[\divxlc]{1,6}", e[0].lower())):
                continue
            kept.append(e)
        # Pass 3: some PDFs store every line as its own block. Join a block to the previous
        # one when it sits right below it or the previous one stops mid-sentence.
        paras: list[str] = []
        prev_bottom, prev_line_h = None, 0.0
        margin = Counter(round(e[4]) for e in kept).most_common(1)[0][0] if kept else 0
        for text, y0, y1, line_h, x0 in kept:
            if paras and prev_bottom is not None:
                close = (y0 - prev_bottom) < 0.6 * max(line_h, prev_line_h)
                unfinished = not re.search(r"[.!?:;\"”’)\]]$", paras[-1])
                indented = x0 > margin + 6  # a first-line indent starts a new paragraph
                if unfinished or (close and not indented):
                    paras[-1] = paras[-1][:-1] + text if paras[-1].endswith("-") else f"{paras[-1]} {text}"
                    prev_bottom, prev_line_h = y1, line_h
                    continue
            paras.append(text)
            prev_bottom, prev_line_h = y1, line_h
        pages.append("\n\n".join(paras))

    if ocr_used:
        warnings.append(f"{ocr_used} scanned page(s) were read with OCR.")
    if ocr_missing:
        warnings.append(
            f"{ocr_missing} page(s) had no text layer. Install Tesseract and "
            "`pip install pytesseract` to read scanned books."
        )
    return ParsedBook(
        title=(meta.get("title") or "").strip(),
        author=(meta.get("author") or "").strip(),
        format="pdf",
        pages=pages,
        warnings=warnings,
    )


def _ocr_page(page) -> str:
    import io

    import pytesseract
    from PIL import Image

    try:
        pix = page.get_pixmap(dpi=200)
        return pytesseract.image_to_string(Image.open(io.BytesIO(pix.tobytes("png"))))
    except Exception:  # noqa: BLE001 - tesseract binary missing, etc.
        return ""


# -- EPUB ----------------------------------------------------------------


class _HTMLText(HTMLParser):
    BLOCK = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "section", "br", "tr"}
    SKIP = {"script", "style", "head", "title", "nav"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCK:
            self.parts.append("\n\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    def text(self) -> str:
        raw = "".join(self.parts)
        paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", raw)]
        return "\n\n".join(p for p in paras if p)


def html_to_text(markup: str) -> str:
    parser = _HTMLText()
    parser.feed(markup)
    return parser.text()


def _parse_epub(path: Path, page_chars: int = TARGET_PAGE_CHARS) -> ParsedBook:
    ns = {
        "c": "urn:oasis:names:tc:opendocument:xmlns:container",
        "opf": "http://www.idpf.org/2007/opf",
        "dc": "http://purl.org/dc/elements/1.1/",
    }
    with zipfile.ZipFile(path) as z:
        container = ElementTree.fromstring(z.read("META-INF/container.xml"))
        rootfile = container.find(".//c:rootfile", ns)
        if rootfile is None:
            raise ValueError("Invalid EPUB: no rootfile")
        opf_path = rootfile.get("full-path")
        opf = ElementTree.fromstring(z.read(opf_path))
        base = posixpath.dirname(opf_path)
        title = opf.findtext(".//dc:title", default="", namespaces=ns).strip()
        author = opf.findtext(".//dc:creator", default="", namespaces=ns).strip()
        manifest = {
            item.get("id"): item.get("href")
            for item in opf.findall(".//opf:manifest/opf:item", ns)
        }
        texts = []
        for ref in opf.findall(".//opf:spine/opf:itemref", ns):
            href = manifest.get(ref.get("idref"))
            if not href:
                continue
            member = posixpath.normpath(posixpath.join(base, html.unescape(href).split("#")[0]))
            try:
                markup = z.read(member).decode("utf-8", errors="replace")
            except KeyError:
                continue
            text = html_to_text(markup)
            if text:
                texts.append(text)
    return ParsedBook(title=title, author=author, format="epub", pages=_chunk("\n\n".join(texts), page_chars))


# -- TXT / Markdown --------------------------------------------------------


def _parse_text(path: Path, fmt: str, page_chars: int = TARGET_PAGE_CHARS) -> ParsedBook:
    raw = path.read_bytes().decode("utf-8", errors="replace")
    title = ""
    if fmt == "md":
        m = re.search(r"^#\s+(.+)$", raw, re.M)
        if m:
            title = m.group(1).strip()
            # The title becomes the book's name, so don't repeat it as the first line of text.
            raw = raw[: m.start()] + raw[m.end() :]
        raw = re.sub(r"^#{1,6}\s*", "", raw, flags=re.M)
        raw = re.sub(r"(\*\*|__|\*|_|`)", "", raw)
        raw = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", raw)
        raw = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", raw)
    # Join hard-wrapped lines inside paragraphs (Project Gutenberg style).
    paras = [re.sub(r"\s*\n\s*", " ", p).strip() for p in re.split(r"\n\s*\n", raw)]
    return ParsedBook(title=title, author="", format=fmt, pages=_chunk("\n\n".join(p for p in paras if p), page_chars))


def _chunk(text: str, target: int = TARGET_PAGE_CHARS) -> list[str]:
    pages, current, size = [], [], 0
    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        # Very long paragraphs are split on sentence boundaries.
        pieces = [para]
        if len(para) > target * 1.5:
            pieces, buf = [], ""
            for sent in re.split(r"(?<=[.!?])\s+", para):
                if len(buf) + len(sent) > target and buf:
                    pieces.append(buf.strip())
                    buf = ""
                buf += sent + " "
            if buf.strip():
                pieces.append(buf.strip())
        for piece in pieces:
            if size + len(piece) > target and current:
                pages.append("\n\n".join(current))
                current, size = [], 0
            current.append(piece)
            size += len(piece)
    if current:
        pages.append("\n\n".join(current))
    return pages
