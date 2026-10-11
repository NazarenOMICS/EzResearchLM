"""Text of a PDF read with PDFium (pypdfium2), and its document information read with pypdf.

On 68 PDFs of earlier runs (2026-10-11), identity verified 40 against 31 with PyPDF2, losing none,
and reading every page took 13 s against 149 s. Structural validation stays in `pdf.py`;
identity and page location read their text here.
"""
import re
import threading

# PDFium is not thread-safe; EZ reads PDFs from one thread, and this lock keeps it that way.
_LOCK = threading.Lock()


def clean(text):
    """PDFium marks a word broken at the end of a line with U+FFFE; join both halves."""
    return re.sub('￾\r?\n?', '', text or '')


def _document(source):
    import pypdfium2
    return pypdfium2.PdfDocument(bytes(source) if isinstance(source, (bytes, bytearray)) else str(source))


def page_texts(source, limit=None):
    """Text of each page, or of the first `limit` pages; `source` is a path or the PDF's bytes.

    Raises on unreadable PDFs: callers decide what an unreadable PDF means for them.
    """
    with _LOCK:
        document = _document(source)
        try:
            texts = []
            for index in range(len(document) if limit is None else min(limit, len(document))):
                page = document[index]
                textpage = page.get_textpage()
                texts.append(clean(textpage.get_text_range()))
                textpage.close()
                page.close()
            return texts
        finally:
            document.close()


def metadata(source):
    """Complete document information as a dict of strings, read with pypdf.

    PDFium exposes only the standard keys; publishers such as Wiley keep the article's DOI in their
    own keys (`/WPS-ARTICLEDOI`), which identity needs.
    """
    import logging
    from io import BytesIO
    from pypdf import PdfReader
    # pypdf logs every repaired cross-reference ("Ignoring wrong pointing object"); the agent only needs the result.
    logging.getLogger('pypdf').setLevel(logging.ERROR)
    reader = PdfReader(BytesIO(bytes(source)) if isinstance(source, (bytes, bytearray)) else str(source))
    return {str(key).lstrip('/'): str(value) for key, value in (reader.metadata or {}).items() if str(value).strip()}


def header(source, pages=2):
    """Text of the first pages and the document information, as identity checks read them."""
    return ' '.join(page_texts(source, pages)), metadata(source)
