"""Page of the local PDF where a cited passage appears, so a reader can check it quickly."""
import re

from PyPDF2 import PdfReader

from .acquisition import plain_words


def page_text(text):
    """Plain words of one page, joining words split by a hyphen at the end of a line."""
    return ' '.join(plain_words(re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text or '')))


def page_texts(path):
    try:
        return [page_text(page.extract_text()) for page in PdfReader(str(path)).pages]
    except Exception:
        return []


def find_page(passage, pages, width=6):
    """1-based page containing a run of words from the passage (start, middle or end); None when not found.

    NotebookLM's passage and the PDF's extracted text differ in hyphenation and spacing, so the
    match is on plain word sequences, never on the raw text.
    """
    words = plain_words(passage)
    if len(words) < width or not pages:
        return None
    middle = len(words) // 2
    probes = [' '.join(words[i:i + width]) for i in (0, max(0, middle - width // 2), len(words) - width)]
    for number, text in enumerate(pages, 1):
        if any(f' {probe} ' in f' {text} ' for probe in probes):
            return number
    return None
