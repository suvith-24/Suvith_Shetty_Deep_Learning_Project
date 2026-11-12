"""PDF ingestion: page text in reading order, plus layout and quality metadata.

Pipeline per document:

1. Validate the file (exists, ``.pdf``, ``%PDF`` signature, opens, not
   password-protected, has pages).
2. First pass: collect margin lines on every page to find running headers
   and footers, i.e. lines that recur in the top or bottom margin.
3. Second pass, per page:
   * detect tables and render them as structure-preserving text blocks;
   * drop running heads, bare page numbers and words inside tables;
   * order blocks (column-aware) and rebuild lines from word coordinates;
   * record footnotes (small-font numbered lines at the page bottom);
   * flag scanned pages and, if enabled, OCR them with Tesseract.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf

from lexisync.ingestion import layout
from lexisync.ingestion.ocr import is_ocr_available, ocr_mode, ocr_pdf_page
from lexisync.ingestion.tables import extract_tables
from lexisync.schemas.document import Document, Page
from lexisync.utils.logger import get_logger


logger = get_logger(__name__)


# Words whose vertical coordinates differ by no more than
# this tolerance are considered part of the same physical line.
LINE_Y_TOLERANCE = 2.0

# Pages with fewer extracted characters than this are flagged as scanned.
SCANNED_TEXT_THRESHOLD = 50

# OCR results below this mean word confidence (0-100) are kept but warned about.
LOW_OCR_CONFIDENCE = 60.0


class PDFIngestionError(ValueError):
    """Raised when a PDF cannot be ingested. The message is user-facing."""


def _repair_soft_hyphen_line_breaks(text: str) -> str:
    """
    Remove remaining PDF soft-hyphen characters.

    Soft-hyphenated words split across physical lines are
    reconstructed in _reconstruct_text_from_words().
    """

    text = re.sub(
        r"­[ \t]*\r?\n[ \t]*",
        "",
        text,
    )

    return text.replace("­", "")


def _group_words_into_physical_lines(
    words: list[tuple],
) -> list[list[tuple]]:
    """
    Group PDF words by their physical vertical position.

    PyMuPDF may assign different line identifiers to words
    that visually belong to the same physical line.

    Grouping by vertical coordinates prevents paragraph
    numbers and their corresponding text from being separated.

    Word tuple structure:
        x0, y0, x1, y1, word, block_no, line_no, word_no
    """

    sorted_words = sorted(
        words,
        key=lambda word: (
            word[1],
            word[0],
        ),
    )

    physical_lines = []

    for word in sorted_words:
        word_y = word[1]

        if (
            not physical_lines
            or abs(word_y - physical_lines[-1][0][1])
            > LINE_Y_TOLERANCE
        ):
            physical_lines.append([word])
        else:
            physical_lines[-1].append(word)

    for line in physical_lines:
        line.sort(
            key=lambda word: (
                word[0],
                word[2],
            )
        )

    return physical_lines


def _block_text(block_words: list[tuple]) -> str:
    """Rebuild one block's text from its words, joining soft hyphens."""

    physical_lines = _group_words_into_physical_lines(block_words)
    reconstructed_lines: list[list[str]] = []

    for line in physical_lines:
        tokens = [word[4] for word in line]
        if not tokens:
            continue

        # Join a word split by a PDF soft hyphen, e.g.
        # "authoris­" + "ation from ..." -> "authorisation from ...".
        if (
            reconstructed_lines
            and reconstructed_lines[-1]
            and reconstructed_lines[-1][-1].endswith("­")
        ):
            previous_token = reconstructed_lines[-1][-1]
            reconstructed_lines[-1][-1] = previous_token[:-1] + tokens.pop(0)

        if tokens:
            reconstructed_lines.append(tokens)

    return "\n".join(" ".join(tokens) for tokens in reconstructed_lines)


def _reconstruct_text_from_words(
    words: list[tuple],
    page_width: float | None = None,
    extra_blocks: list[tuple[float, float, float, float, str]] | None = None,
    return_columns: bool = False,
):
    """
    Reconstruct page text using coordinate-based word extraction.

    Words are grouped by their original block identifiers. Within each
    block, words are grouped into physical lines using their vertical
    coordinates. Soft-hyphenated words split across physical lines are
    joined without losing paragraph numbers or word boundaries.

    When ``page_width`` is given, two-column layouts are detected and each
    column is read top-to-bottom before the next. ``extra_blocks`` (for
    example rendered tables) are inserted at their vertical position.

    Returns the text, or ``(text, column_count)`` when ``return_columns``.
    """

    if page_width:
        words = layout.split_blocks_at_gutter(words, page_width)

    blocks = defaultdict(list)
    for word in words:
        blocks[word[5]].append(word)

    positioned: list[tuple[float, float, float, float, str]] = []

    for block_words in blocks.values():
        text = _block_text(block_words)
        if not text:
            continue
        positioned.append(
            (
                min(word[0] for word in block_words),
                min(word[1] for word in block_words),
                max(word[2] for word in block_words),
                max(word[3] for word in block_words),
                text,
            )
        )

    for extra in extra_blocks or []:
        positioned.append(extra)

    column_count = 1
    if page_width:
        column_count = layout.detect_columns(
            [block[:4] for block in positioned],
            page_width,
        )

    # Original ordering key was (min y, min x); order_blocks keeps it for
    # single-column pages.
    reordered = layout.order_blocks(
        [(b[0], b[1], b[2], b[3], b[4]) for b in positioned],
        page_width or 0.0,
        column_count,
    )

    text = _join_blocks(reordered, words)
    return (text, column_count) if return_columns else text


def _join_blocks(
    blocks: list[tuple[float, float, float, float, str]],
    words: list[tuple],
) -> str:
    """Join ordered blocks, keeping paragraph breaks only where there is space.

    Some PDFs (e.g. the Official Journal) store every printed line as its own
    block. Two blocks that sit directly on top of each other (vertical gap
    under 35 % of the typical word height) and overlap horizontally are
    continuation lines of one paragraph and are joined with a single newline.
    Everything else stays separated by a blank line.
    """

    if not blocks:
        return ""

    heights = sorted(word[3] - word[1] for word in words if word[3] > word[1])
    line_height = heights[len(heights) // 2] if heights else 0.0
    tight_gap = 0.35 * line_height

    parts = [blocks[0][4]]
    for previous, current in zip(blocks, blocks[1:]):
        gap = current[1] - previous[3]
        overlaps = min(previous[2], current[2]) > max(previous[0], current[0])
        is_table = current[4].startswith("[Table ") or previous[4].startswith("[Table ")
        separator = (
            "\n"
            if line_height and -1.0 <= gap <= tight_gap and overlaps and not is_table
            else "\n\n"
        )
        parts.append(separator + current[4])
    return "".join(parts)


def _validate_path(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError("The supplied file must be a PDF.")

    if path.stat().st_size == 0:
        raise PDFIngestionError(f"{path.name} is empty (0 bytes).")

    with path.open("rb") as handle:
        signature = handle.read(1024)

    if b"%PDF" not in signature:
        raise PDFIngestionError(
            f"{path.name} does not look like a PDF (missing %PDF signature)."
        )


def _open_pdf(path: Path) -> pymupdf.Document:
    try:
        pdf = pymupdf.open(path)
    except Exception as error:  # FileDataError, RuntimeError, ...
        raise PDFIngestionError(
            f"{path.name} could not be opened; the file may be corrupt. ({error})"
        ) from error

    if pdf.is_encrypted and not pdf.authenticate(""):
        pdf.close()
        raise PDFIngestionError(
            f"{path.name} is password-protected. Remove the password and upload it again."
        )

    if pdf.page_count == 0:
        pdf.close()
        raise PDFIngestionError(f"{path.name} contains no pages.")

    return pdf


def _footnotes(pdf_page) -> list[str]:
    """Return small-font numbered lines in the lower part of the page."""

    try:
        data = pdf_page.get_text("dict")
    except Exception:
        return []

    sizes: Counter[float] = Counter()
    lines: list[tuple[float, float, str]] = []

    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = "".join(span.get("text", "") for span in spans).strip()
            if not text or not spans:
                continue
            size = round(min(span.get("size", 0) for span in spans), 1)
            sizes[size] += len(text)
            lines.append((line["bbox"][1], size, text))

    if not sizes:
        return []

    body_size = sizes.most_common(1)[0][0]
    lower_region = pdf_page.rect.height * 0.6

    return [
        text
        for y, size, text in lines
        if y >= lower_region
        and size <= body_size * 0.88
        and re.match(r"^\(?\d{1,3}\)?\s+\S", text)
    ]


def _words_in_rect(word: tuple, rect: tuple[float, float, float, float]) -> bool:
    centre_x = (word[0] + word[2]) / 2
    centre_y = (word[1] + word[3]) / 2
    return rect[0] <= centre_x <= rect[2] and rect[1] <= centre_y <= rect[3]


def file_sha256(path: str | Path) -> str:
    """Return the SHA-256 digest of a file (used for duplicate detection)."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_pdf(
    pdf_path: str | Path,
    *,
    enable_ocr: bool | None = None,
    enable_tables: bool = True,
    remove_running_heads: bool = True,
) -> Document:
    """
    Extract text from a PDF page by page in reading order.

    Args:
        pdf_path: Path to the PDF.
        enable_ocr: Force OCR on/off. ``None`` follows ``LEXISYNC_OCR``.
        enable_tables: Detect tables and render them as structured text.
        remove_running_heads: Remove recurring header/footer lines.

    Returns:
        Document with one ``Page`` per PDF page. ``Document.metadata`` holds
        counts (scanned/OCR/table pages), warnings and the file hash.

    Raises:
        FileNotFoundError, ValueError (including ``PDFIngestionError``).
    """

    path = Path(pdf_path)
    _validate_path(path)

    use_ocr = (ocr_mode() != "off") if enable_ocr is None else enable_ocr
    ocr_available = use_ocr and is_ocr_available()

    document_warnings: list[str] = []
    pages: list[Page] = []

    pdf = _open_pdf(path)

    try:
        # Pass 1: words, physical lines and margin candidates for every page.
        page_words: list[list[tuple]] = []
        page_lines: list[list[list[tuple]]] = []
        header_candidates: list[list[tuple[str, int]]] = []
        footer_candidates: list[list[tuple[str, int]]] = []

        for pdf_page in pdf:
            words = pdf_page.get_text("words", sort=True)
            lines = _group_words_into_physical_lines(words)
            headers, footers = layout.margin_lines(lines, pdf_page.rect.height)
            page_words.append(words)
            page_lines.append(lines)
            header_candidates.append(headers)
            footer_candidates.append(footers)

        recurring = set()
        if remove_running_heads:
            recurring = layout.recurring_signatures(
                [[text for text, _ in h] + [text for text, _ in f]
                 for h, f in zip(header_candidates, footer_candidates)]
            )

        # Pass 2: build each page.
        for page_index, pdf_page in enumerate(pdf):
            page_number = page_index + 1
            page_warnings: list[str] = []
            words = page_words[page_index]
            lines = page_lines[page_index]

            removed_headers: list[str] = []
            removed_footers: list[str] = []
            removed_word_ids: set[int] = set()

            if remove_running_heads:
                for collection, removed in (
                    (header_candidates[page_index], removed_headers),
                    (footer_candidates[page_index], removed_footers),
                ):
                    for text, line_index in collection:
                        if (
                            layout.line_signature(text) in recurring
                            or layout.is_page_number_line(text)
                        ):
                            removed.append(text)
                            removed_word_ids.update(id(w) for w in lines[line_index])

            tables = extract_tables(pdf_page, page_number) if enable_tables else []
            table_blocks = []
            for table in tables:
                table_blocks.append((*table.bbox, table.to_text()))

            kept_words = [
                word
                for word in words
                if id(word) not in removed_word_ids
                and not any(_words_in_rect(word, table.bbox) for table in tables)
            ]

            text, column_count = _reconstruct_text_from_words(
                kept_words,
                page_width=pdf_page.rect.width,
                extra_blocks=table_blocks,
                return_columns=True,
            )
            text = _repair_soft_hyphen_line_breaks(text).strip()

            has_images = len(pdf_page.get_images()) > 0
            is_scanned = len(text) < SCANNED_TEXT_THRESHOLD
            extraction_method = "text" if text else "none"
            ocr_confidence = None

            if is_scanned and has_images:
                if ocr_available:
                    try:
                        result = ocr_pdf_page(pdf_page)
                    except Exception as error:
                        page_warnings.append(f"OCR failed: {error}")
                        logger.warning("OCR failed on page %d: %s", page_number, error)
                    else:
                        if result.text:
                            text = result.text
                            extraction_method = "ocr"
                            ocr_confidence = (
                                round(result.mean_confidence, 1)
                                if result.mean_confidence is not None
                                else None
                            )
                            if ocr_confidence is not None and ocr_confidence < LOW_OCR_CONFIDENCE:
                                page_warnings.append(
                                    f"Low OCR confidence ({ocr_confidence:.0f}/100); verify against the page image."
                                )
                        else:
                            page_warnings.append("OCR produced no text.")
                elif use_ocr:
                    page_warnings.append(
                        "Scanned page detected but Tesseract OCR is not available; page is not searchable."
                    )
                else:
                    page_warnings.append("Scanned page detected; OCR is disabled.")

            pages.append(
                Page(
                    page_number=page_number,
                    text=text,
                    character_count=len(text),
                    is_scanned=is_scanned,
                    has_images=has_images,
                    has_tables=bool(tables),
                    extraction_method=extraction_method,
                    ocr_confidence=ocr_confidence,
                    column_count=column_count,
                    header_lines=removed_headers,
                    footer_lines=removed_footers,
                    footnotes=_footnotes(pdf_page),
                    tables=[table.to_dict() for table in tables],
                    warnings=page_warnings,
                )
            )

        raw_metadata = pdf.metadata or {}
    finally:
        pdf.close()

    scanned_pages = [p.page_number for p in pages if p.is_scanned]
    ocr_pages = [p.page_number for p in pages if p.extraction_method == "ocr"]
    unreadable = [p.page_number for p in pages if p.is_scanned and p.extraction_method != "ocr"]

    if pages and len(unreadable) == len(pages):
        document_warnings.append(
            "No searchable text was extracted from any page."
        )
    elif unreadable:
        document_warnings.append(
            f"{len(unreadable)} page(s) have no searchable text: "
            + ", ".join(map(str, unreadable[:20]))
        )

    title = (raw_metadata.get("title") or "").strip() or None
    author = (raw_metadata.get("author") or "").strip() or None

    return Document(
        document_id=path.stem,
        file_name=path.name,
        file_path=str(path.resolve()),
        total_pages=len(pages),
        pages=pages,
        title=title,
        author=author,
        metadata={
            "sha256": file_sha256(path),
            "file_size_bytes": path.stat().st_size,
            "creation_date": raw_metadata.get("creationDate") or None,
            "producer": raw_metadata.get("producer") or None,
            "scanned_pages": scanned_pages,
            "ocr_pages": ocr_pages,
            "ocr_available": ocr_available,
            "table_count": sum(len(p.tables) for p in pages),
            "multi_column_pages": [p.page_number for p in pages if p.column_count > 1],
            "running_heads_removed": sum(
                len(p.header_lines) + len(p.footer_lines) for p in pages
            ),
            "footnote_count": sum(len(p.footnotes) for p in pages),
            "warnings": document_warnings,
        },
    )
