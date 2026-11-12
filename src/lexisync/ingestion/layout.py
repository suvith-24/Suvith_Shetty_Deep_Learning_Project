"""Page layout heuristics: column detection, block ordering and running heads.

These are geometric heuristics over PyMuPDF word/block coordinates, not a
learned layout model. They are designed to be conservative: a page is only
treated as multi-column when there is clear evidence, so single-column legal
texts keep their original top-to-bottom order.
"""

from __future__ import annotations

import re
from collections import Counter

# A line whose top lies within this fraction of the page height from the top
# (or whose bottom lies within it from the bottom) is a margin candidate.
MARGIN_FRACTION = 0.08

# A margin line must recur on at least this fraction of pages (and on at least
# two pages) before it is treated as a running header or footer.
RECURRENCE_FRACTION = 0.4

_PAGE_NUMBER_PATTERN = re.compile(
    r"^\s*(?:page\s*)?[-–—]?\s*\d{1,4}\s*(?:/\s*\d{1,4}|of\s+\d{1,4})?\s*[-–—]?\s*$",
    re.IGNORECASE,
)


def line_signature(text: str) -> str:
    """Normalise a margin line so page-specific numbers do not matter."""

    signature = re.sub(r"\d+", "#", text.casefold())
    return re.sub(r"\s+", " ", signature).strip()


def is_page_number_line(text: str) -> bool:
    """Return True for bare page-number lines such as "12", "Page 3", "- 4 -"."""

    return bool(_PAGE_NUMBER_PATTERN.match(text))


def margin_lines(
    physical_lines: list[list[tuple]],
    page_height: float,
) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """Return (header, footer) candidate lines as (text, line_index) pairs."""

    top_limit = page_height * MARGIN_FRACTION
    bottom_limit = page_height * (1 - MARGIN_FRACTION)

    headers, footers = [], []
    for index, line in enumerate(physical_lines):
        text = " ".join(word[4] for word in line).strip()
        if not text:
            continue
        top = min(word[1] for word in line)
        bottom = max(word[3] for word in line)
        if top <= top_limit:
            headers.append((text, index))
        elif bottom >= bottom_limit:
            footers.append((text, index))
    return headers, footers


def recurring_signatures(
    per_page_candidates: list[list[str]],
) -> set[str]:
    """Find margin-line signatures that recur across the document."""

    page_count = len(per_page_candidates)
    if page_count < 2:
        return set()

    counts: Counter[str] = Counter()
    for candidates in per_page_candidates:
        counts.update({line_signature(text) for text in candidates})

    threshold = max(2, int(page_count * RECURRENCE_FRACTION + 0.5))
    return {signature for signature, count in counts.items() if count >= threshold}


def detect_columns(
    blocks: list[tuple[float, float, float, float]],
    page_width: float,
) -> int:
    """Estimate whether a page is laid out in two columns.

    ``blocks`` are (x0, y0, x1, y1) boxes of text blocks. A page counts as
    two-column when at least two narrow blocks sit wholly in each half and the
    two halves overlap vertically, which is what a column gutter looks like.
    """

    if not blocks or page_width <= 0:
        return 1

    middle = page_width / 2
    tolerance = page_width * 0.03
    narrow = page_width * 0.55

    left = [b for b in blocks if b[2] <= middle + tolerance and (b[2] - b[0]) < narrow]
    right = [b for b in blocks if b[0] >= middle - tolerance and (b[2] - b[0]) < narrow]

    # Bare paragraph numbers ("1.") on the left margin are narrow too, so
    # require real text width in both halves.
    left = [b for b in left if (b[2] - b[0]) > page_width * 0.18]
    right = [b for b in right if (b[2] - b[0]) > page_width * 0.18]

    if not left or not right:
        return 1

    left_span = (min(b[1] for b in left), max(b[3] for b in left))
    right_span = (min(b[1] for b in right), max(b[3] for b in right))
    overlap = min(left_span[1], right_span[1]) - max(left_span[0], right_span[0])

    # Either several narrow blocks per side, or tall columns side by side
    # (at least ~4 lines of overlap), e.g. one block per column.
    if len(left) >= 2 and len(right) >= 2:
        return 2 if overlap > 0 else 1
    return 2 if overlap > 40 else 1


def split_blocks_at_gutter(
    words: list[tuple],
    page_width: float,
    line_tolerance: float = 2.0,
) -> list[tuple]:
    """Re-assign words to left/right blocks when a column gutter is visible.

    Some PDFs put both columns of a line into one text block. A gutter is
    accepted when at least 40 % of physical lines (and at least four) have a
    horizontal gap wider than 2.5 % of the page width whose centre lies in
    the middle fifth of the page, all at a consistent position. Words right of
    the gutter get a distinct block number, so block-level column detection
    and ordering apply. Returns ``words`` unchanged when there is no gutter.
    """

    if not words or page_width <= 0:
        return words

    lines: list[list[tuple]] = []
    for word in sorted(words, key=lambda w: (w[1], w[0])):
        if lines and abs(word[1] - lines[-1][0][1]) <= line_tolerance:
            lines[-1].append(word)
        else:
            lines.append([word])

    centres = []
    for line in lines:
        line.sort(key=lambda w: w[0])
        for left, right in zip(line, line[1:]):
            gap = right[0] - left[2]
            centre = (left[2] + right[0]) / 2
            if gap > page_width * 0.025 and page_width * 0.4 <= centre <= page_width * 0.6:
                centres.append(centre)
                break

    if len(centres) < 4 or len(centres) < 0.4 * len(lines):
        return words

    centres.sort()
    gutter = centres[len(centres) // 2]
    if centres[-1] - centres[0] > page_width * 0.1:
        return words  # gaps are not aligned: not a column layout

    max_block = max(word[5] for word in words) + 1
    return [
        (*word[:5], word[5] + max_block if word[0] >= gutter else word[5], *word[6:])
        for word in words
    ]


def order_blocks(
    blocks: list[tuple[float, float, float, float, object]],
    page_width: float,
    column_count: int,
) -> list[tuple[float, float, float, float, object]]:
    """Order blocks for reading.

    Single column: top-to-bottom, then left-to-right (the original behaviour).
    Two columns: the page is cut into horizontal bands at every full-width
    block; inside a band the whole left column is read before the right one.
    """

    by_position = sorted(blocks, key=lambda b: (b[1], b[0]))
    if column_count < 2:
        return by_position

    middle = page_width / 2
    tolerance = page_width * 0.03

    def column_of(block) -> int | None:
        if block[2] <= middle + tolerance:
            return 0
        if block[0] >= middle - tolerance:
            return 1
        return None  # spans the gutter

    ordered: list = []
    band: list = []

    def flush() -> None:
        band.sort(key=lambda b: (column_of(b), b[1], b[0]))
        ordered.extend(band)
        band.clear()

    for block in by_position:
        if column_of(block) is None:
            flush()
            ordered.append(block)
        else:
            band.append(block)
    flush()
    return ordered
