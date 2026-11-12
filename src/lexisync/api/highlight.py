"""Locate cited text on a PDF page and return region bounding boxes.

Used for bounding-box citations: the UI overlays the returned rectangles on
the rendered page image. The cited passage is matched against the page's
words with ``difflib.SequenceMatcher`` on normalised tokens, so small
extraction differences (hyphenation, removed running heads, reordered
blocks) do not prevent a match. Matched words are merged into one box per
line.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

import pymupdf


def _norm(token: str) -> str:
    return re.sub(r"[^\w%€$£]", "", token.casefold().replace("­", ""))


def _line_boxes(words: list[tuple]) -> list[list[float]]:
    """Merge word boxes that share a line into a single rectangle."""

    boxes: list[list[float]] = []
    for word in sorted(words, key=lambda w: (round(w[1], 0), w[0])):
        x0, y0, x1, y1 = word[:4]
        if boxes:
            last = boxes[-1]
            same_line = abs(last[1] - y0) < 3 and abs(last[3] - y1) < 3
            if same_line and x0 - last[2] < 40:
                last[2] = max(last[2], x1)
                last[0] = min(last[0], x0)
                continue
        boxes.append([x0, y0, x1, y1])
    return boxes


def locate(page: pymupdf.Page, text: str, min_block: int = 3) -> dict:
    """Find ``text`` on ``page``.

    Returns ``{"rects": [[x0, y0, x1, y1], ...], "coverage": float}``, where
    ``coverage`` is the share of the passage's tokens found on the page.
    """

    target = [t for t in (_norm(x) for x in (text or "").split()) if t]
    if not target:
        return {"rects": [], "coverage": 0.0}

    words = page.get_text("words", sort=True)
    page_tokens = [_norm(w[4]) for w in words]

    matcher = SequenceMatcher(None, page_tokens, target, autojunk=False)
    matched: list[tuple] = []
    matched_tokens = 0
    for block in matcher.get_matching_blocks():
        if block.size >= min_block or (block.size and len(target) < min_block):
            matched.extend(words[block.a: block.a + block.size])
            matched_tokens += block.size

    rects = [[round(v, 2) for v in box] for box in _line_boxes(matched)]
    return {"rects": rects, "coverage": round(matched_tokens / len(target), 3)}


def page_highlights(pdf_path: str, page_number: int, passage: str | None, quote: str | None) -> dict:
    """Highlight geometry for a cited passage and (optionally) its exact quote."""

    with pymupdf.open(pdf_path) as pdf:
        if not 1 <= page_number <= pdf.page_count:
            raise ValueError("Page number out of range.")
        page = pdf[page_number - 1]
        result = {
            "page": page_number,
            "width": page.rect.width,
            "height": page.rect.height,
            "passage": locate(page, passage) if passage else {"rects": [], "coverage": 0.0},
            "quote": locate(page, quote, min_block=2) if quote else {"rects": [], "coverage": 0.0},
        }
    return result


def render_page_png(pdf_path: str, page_number: int, zoom: float = 1.6) -> bytes:
    with pymupdf.open(pdf_path) as pdf:
        if not 1 <= page_number <= pdf.page_count:
            raise ValueError("Page number out of range.")
        pixmap = pdf[page_number - 1].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        return pixmap.tobytes("png")
