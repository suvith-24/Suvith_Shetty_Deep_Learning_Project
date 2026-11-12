"""Legal structure-aware chunking.

Chunks follow legal structure before size:

1. **Sections** start at detected headings (Chapter, Part, Title, Article,
   Section, §, Schedule, Annex, Appendix, Exhibit, numbered CAPITALISED
   headings and short dotted headings such as ``7.2 Limitation of
   liability``). A bare ``Article 83`` heading absorbs the following title
   line, giving ``Article 83 — General conditions for imposing ...``.
2. **Oversized sections** are split at paragraph boundaries where possible,
   otherwise at whitespace, with a configurable overlap.
3. **Clause identifiers** (GDPR-style ``1.`` paragraphs, dotted ``3.1``
   clauses, ``(a)`` points) inside each chunk are recorded in
   ``chunk.metadata["clause_ids"]``. The clause in force at the chunk start
   becomes ``chunk.subsection``.
4. **Tables** rendered by the loader are kept as separate ``table`` chunks.
   They are never split mid-row; large tables are split by rows and the
   header is repeated.
5. Fragments shorter than ``MIN_CHUNK_SIZE`` that end a page are merged with
   the first chunk of the same section on the next page. A provision broken
   by a page break therefore stays together and cites both pages.

Chunks never cross documents, and page numbers are always preserved.
"""

from __future__ import annotations

import re
from uuid import uuid4

from lexisync.schemas.document import Chunk, Document
from lexisync.utils.logger import get_logger


logger = get_logger(__name__)


# Chunking configuration
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150
MIN_CHUNK_SIZE = 100

PARAGRAPH_BOUNDARY_THRESHOLD = 0.60


# Legal heading patterns
HEADING_PATTERNS = [
    re.compile(
        r"^\s*CHAPTER\s+[IVXLCDM\d]+(?:\s*[-–—:]\s*.+)?\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(?:PART|TITLE)\s+(?:[IVXLCDM]+|\d+)(?:\s*[-–—:]\s*.{1,100})?\s*$",
    ),
    re.compile(
        r"^\s*Article\s+\d+[A-Za-z]?(?:\s*[-–—:]\s*.+)?\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*SECTION\s+\d+[A-Za-z]?(?:\s*[-–—:]\s*.+)?\s*$",
        re.IGNORECASE,
    ),
    # "Section 7.2 Limitation of liability" / "SECTION 7 LIABILITY"
    re.compile(
        r"^\s*Section\s+\d+(?:\.\d+)*[A-Za-z]?\.?\s+[A-Z][A-Za-z ,&'()/-]{2,80}$",
        re.IGNORECASE,
    ),
    re.compile(r"^\s*§+\s*\d+[A-Za-z]?(?:\.\d+)*\.?(?:\s+.{1,90})?$"),
    re.compile(
        r"^\s*(?:SCHEDULE|ANNEX|APPENDIX|EXHIBIT|Schedule|Annex|Appendix|Exhibit)"
        r"(?:\s+[A-Z0-9IVX]{1,6})?(?:\s*[-–—:]\s*.{1,90})?\s*$"
    ),
    # Numbered capitalised heading: "7. LIMITATION OF LIABILITY"
    re.compile(r"^\s*\d{1,2}\.?\s+[A-Z][A-Z0-9 ,&'()/-]{2,80}$"),
    # Short dotted heading without a sentence: "7.2 Limitation of liability"
    re.compile(r"^\s*\d{1,2}\.\d{1,2}\.?\s+[A-Z][^.\n]{0,80}\.?$"),
]

_BARE_ARTICLE = re.compile(r"^\s*Article\s+\d+[A-Za-z]?\s*$", re.IGNORECASE)

# Clause/paragraph markers inside a section.
_CLAUSE_PATTERNS = [
    # GDPR style: paragraph number alone on its line ("1.").
    re.compile(r"(?m)^[ \t]*(\d{1,2})\.[ \t]*$"),
    # Dotted clause at line start: "3.1 ", "7.2.1 "
    re.compile(r"(?m)^[ \t]*(\d{1,2}(?:\.\d{1,2}){1,3})\.?[ \t]+(?=\S)"),
    # Inline numbered paragraph: "1. The controller ..."
    re.compile(r"(?m)^[ \t]*(\d{1,2})\.[ \t]+(?=[A-Z])"),
]

_TABLE_BLOCK = re.compile(
    r"\[Table (?P<id>\d+\.\d+) — page \d+\]\n(?:\|[^\n]*(?:\n|$))+"
)


# European Journal publication-header pattern.
# Matches only complete page headers, not legal text
# that merely references the Official Journal.
PUBLICATION_HEADER_PATTERN = re.compile(
    r"""
    ^\s*
    (?:
        \d{1,2}\.\d{1,2}\.\d{4}
        \s+EN
        .*?
        L\s+\d+/\d+
        |
        L\s+\d+/\d+
        \s+EN
        .*?
        \d{1,2}\.\d{1,2}\.\d{4}
    )
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


def detect_heading(line: str) -> bool:
    """Check whether a line looks like a legal heading."""

    stripped = line.strip()
    if not stripped or len(stripped) > 160:
        return False

    return any(
        pattern.match(stripped)
        for pattern in HEADING_PATTERNS
    )


def section_key(heading: str | None) -> str | None:
    """Normalise a heading to a short key, e.g. ``"article 83"`` or ``"section 7.2"``."""

    if not heading:
        return None

    match = re.match(
        r"^\s*(chapter|part|title|article|section|schedule|annex|appendix|exhibit|§)"
        r"\s*([0-9]+(?:\.[0-9]+)*[a-z]?|[ivxlcdm]+|[a-z])?\b",
        heading,
        re.IGNORECASE,
    )
    if match:
        kind = match.group(1).casefold()
        number = (match.group(2) or "").casefold()
        return f"{kind} {number}".strip()

    match = re.match(r"^\s*(\d{1,2}(?:\.\d{1,2})*)\.?\s", heading)
    if match:
        return f"section {match.group(1)}"

    return None


def clean_page_text(text: str) -> str:
    """
    Remove only complete recurring publication headers.

    Replacements preserve the original character count
    and newline positions, keeping character offsets valid.

    Substantive legal references to the Official Journal
    are preserved.
    """

    cleaned_lines = []

    for line in text.splitlines(keepends=True):

        stripped = line.strip()

        is_publication_header = (
            "official journal of the european union"
            in stripped.casefold()
            and PUBLICATION_HEADER_PATTERN.match(stripped)
        )

        if is_publication_header:

            cleaned_line = "".join(
                "\n" if character == "\n"
                else "\r" if character == "\r"
                else " "
                for character in line
            )

            cleaned_lines.append(cleaned_line)

        else:
            cleaned_lines.append(line)

    return "".join(cleaned_lines)


def _is_title_line(line: str) -> bool:
    """A short line that reads like a provision title, not a sentence."""

    stripped = line.strip()
    return (
        3 <= len(stripped) <= 120
        and stripped[0].isupper()
        and not stripped.endswith((".", ";", ":", ","))
        and not re.match(r"^\(?\d", stripped)
        and not detect_heading(stripped)
    )


def split_into_sections(
    text: str,
) -> list[tuple[str, str, int, int]]:
    """
    Split document text into sections using detected headings.

    Returns:
        List of (heading, section_text, start_char, end_char).

    Character offsets refer to the original input text.
    """

    lines = text.splitlines(keepends=True)

    sections = []

    current_heading = "General"
    current_lines: list[str] = []

    position = 0
    section_start = 0

    def save_section(
        heading: str,
        section_lines: list[str],
        raw_start: int,
    ) -> None:
        """Save a section while preserving its original offsets."""

        if not section_lines:
            return

        raw_text = "".join(section_lines)
        section_text = raw_text.strip()

        if not section_text:
            return

        leading_whitespace = (
            len(raw_text) - len(raw_text.lstrip())
        )

        actual_start = raw_start + leading_whitespace
        actual_end = actual_start + len(section_text)

        sections.append(
            (
                heading,
                section_text,
                actual_start,
                actual_end,
            )
        )

    for index, line in enumerate(lines):

        stripped = line.strip()

        if stripped and detect_heading(stripped):

            save_section(
                current_heading,
                current_lines,
                section_start,
            )

            heading = stripped

            # "Article 83" followed by its title line on the next line.
            if _BARE_ARTICLE.match(stripped):
                following = next(
                    (candidate for candidate in lines[index + 1:] if candidate.strip()),
                    None,
                )
                if following is not None and _is_title_line(following):
                    heading = f"{stripped} — {following.strip()}"

            current_heading = heading
            current_lines = [line]
            section_start = position

        else:
            current_lines.append(line)

        position += len(line)

    save_section(
        current_heading,
        current_lines,
        section_start,
    )

    return sections


def split_large_section(
    text: str,
    chunk_size: int,
    overlap: int,
) -> list[tuple[str, int, int]]:
    """
    Split an oversized section into smaller passages.

    Prefer paragraph boundaries when they are reasonably
    close to the target chunk size.

    Otherwise, use the nearest whitespace boundary.

    Returns:
        List of (chunk_text, start_char, end_char).

    Offsets refer to the original section_text.
    """

    chunks = []

    start = 0
    text_length = len(text)

    while start < text_length:

        end = min(
            start + chunk_size,
            text_length,
        )

        if end < text_length:

            minimum_boundary = (
                start
                + int(chunk_size * PARAGRAPH_BOUNDARY_THRESHOLD)
            )

            paragraph_boundary = text.rfind(
                "\n\n",
                start,
                end,
            )

            if paragraph_boundary >= minimum_boundary:

                end = paragraph_boundary

            else:

                whitespace_positions = [
                    text.rfind(" ", start, end),
                    text.rfind("\n", start, end),
                    text.rfind("\t", start, end),
                ]

                boundary = max(whitespace_positions)

                if boundary > start:
                    end = boundary

        raw_chunk = text[start:end]
        chunk_text = raw_chunk.strip()

        if chunk_text:

            leading_whitespace = (
                len(raw_chunk) - len(raw_chunk.lstrip())
            )

            actual_start = start + leading_whitespace
            actual_end = actual_start + len(chunk_text)

            chunks.append(
                (
                    chunk_text,
                    actual_start,
                    actual_end,
                )
            )

        if end >= text_length:
            break

        next_start = max(
            start + 1,
            end - overlap,
        )

        # Avoid starting in the middle of a word.
        while (
            next_start < text_length
            and not text[next_start - 1].isspace()
            and not text[next_start].isspace()
        ):
            next_start += 1

        start = next_start

    return chunks


def find_clause_markers(text: str) -> list[tuple[int, str]]:
    """Return (offset, clause_id) pairs for paragraph/clause markers in text."""

    markers: dict[int, str] = {}
    for pattern in _CLAUSE_PATTERNS:
        for match in pattern.finditer(text):
            markers.setdefault(match.start(1), match.group(1))
    return sorted(markers.items())


def _format_clause(section: str | None, clause: str) -> str:
    """Combine a section key and paragraph number: Article 83 + 4 -> 83(4)."""

    key = section_key(section) or ""
    if "." in clause:
        return clause
    if key.startswith(("article ", "section ", "§")):
        number = key.split(" ", 1)[-1].strip()
        if number:
            return f"{number}({clause})"
    return clause


def _clause_metadata(
    section: str | None,
    section_text: str,
    start: int,
    end: int,
    inherited: str | None,
) -> tuple[str | None, list[str]]:
    """Clause in force at ``start`` and every clause starting inside the chunk."""

    active = inherited
    contained: list[str] = []

    for offset, clause in find_clause_markers(section_text):
        formatted = _format_clause(section, clause)
        if offset <= start:
            active = formatted
        elif offset < end:
            contained.append(formatted)

    ordered = ([active] if active else []) + [c for c in contained if c != active]
    return active, list(dict.fromkeys(ordered))


def _blank_span(text: str, start: int, end: int) -> str:
    """Replace text[start:end] with spaces, keeping newlines (offsets stay valid)."""

    blanked = "".join("\n" if ch == "\n" else " " for ch in text[start:end])
    return text[:start] + blanked + text[end:]


def _table_chunks(
    table_text: str,
    table_id: str,
    chunk_size: int,
) -> list[str]:
    """Split a rendered table by rows, repeating caption and header lines."""

    lines = table_text.rstrip("\n").split("\n")
    if len(table_text) <= chunk_size * 1.5 or len(lines) <= 4:
        return [table_text.rstrip("\n")]

    caption = lines[0]
    has_header = len(lines) > 2 and set(lines[2].replace("|", "")) <= {"-"}
    head = lines[:3] if has_header else lines[:1]
    body = lines[3:] if has_header else lines[1:]

    pieces, current = [], list(head)
    for row in body:
        if len("\n".join(current + [row])) > chunk_size and len(current) > len(head):
            pieces.append("\n".join(current))
            current = list(head)
        current.append(row)
    if len(current) > len(head):
        pieces.append("\n".join(current))
    return pieces or [caption]


def chunk_document(
    document: Document,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Chunk]:
    """
    Convert a structured legal document into searchable chunks.

    Preserves:
        - Document IDs and file names
        - Legal section headings and clause identifiers
        - Original PDF page numbers
        - Original extracted-text character offsets
        - Configured maximum chunk size
        - Extraction method (digital text or OCR) per page

    Carries section headings across consecutive PDF pages.
    """

    if chunk_size <= 0:
        raise ValueError(
            "chunk_size must be greater than zero."
        )

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError(
            "overlap must be non-negative and smaller than chunk_size."
        )

    chunks: list[Chunk] = []

    current_section = "General"
    current_clause: str | None = None

    logger.info(
        "Starting chunking for document '%s'.",
        document.file_name,
    )

    for page in document.pages:

        if not page.text.strip():

            logger.info(
                "Skipping empty page %d.",
                page.page_number,
            )

            continue

        cleaned_text = clean_page_text(page.text)

        base_metadata = {
            "file_name": document.file_name,
            "extraction_method": getattr(page, "extraction_method", "text"),
        }
        if getattr(page, "ocr_confidence", None) is not None:
            base_metadata["ocr_confidence"] = page.ocr_confidence

        # Carve out table blocks so text chunking never cuts through a row.
        table_spans = [
            (match.start(), match.end(), match.group("id"), match.group(0))
            for match in _TABLE_BLOCK.finditer(cleaned_text)
        ]
        for start, end, _, _ in table_spans:
            cleaned_text = _blank_span(cleaned_text, start, end)

        sections = split_into_sections(cleaned_text)
        page_start_section = current_section
        section_ranges: list[tuple[int, int, str]] = []

        for heading, section_text, section_start, section_end in sections:

            if heading != "General":
                current_section = heading
                current_clause = None

            else:
                heading = current_section

            section_ranges.append((section_start, section_end, heading))

            passages = split_large_section(
                text=section_text,
                chunk_size=chunk_size,
                overlap=overlap,
            )

            for passage, start, end in passages:

                if table_spans:
                    # Collapse the blank filler left where a table was carved out.
                    passage = re.sub(r"\n[ \t]*(?:\n[ \t]*)+", "\n\n", passage).strip()
                    if not passage:
                        continue

                active_clause, clause_ids = _clause_metadata(
                    heading,
                    section_text,
                    start,
                    end,
                    current_clause,
                )

                chunk = Chunk(
                    chunk_id=str(uuid4()),
                    document_id=document.document_id,
                    text=passage,
                    page_numbers=[page.page_number],
                    section=heading,
                    subsection=active_clause,
                    start_char=section_start + start,
                    end_char=section_start + end,
                    metadata={
                        **base_metadata,
                        "chunk_type": "text",
                        "section_key": section_key(heading),
                        "clause_ids": clause_ids,
                    },
                )

                chunks.append(chunk)

            # The last clause seen carries over to the next section part/page.
            markers = find_clause_markers(section_text)
            if markers:
                current_clause = _format_clause(heading, markers[-1][1])

        for start, end, table_id, table_text in table_spans:
            heading = next(
                (h for s, e, h in section_ranges if s <= start < e),
                None,
            )
            if heading is None:
                preceding = [h for s, _, h in section_ranges if s <= start]
                heading = preceding[-1] if preceding else page_start_section

            for piece in _table_chunks(table_text, table_id, chunk_size):
                chunks.append(
                    Chunk(
                        chunk_id=str(uuid4()),
                        document_id=document.document_id,
                        text=piece,
                        page_numbers=[page.page_number],
                        section=heading,
                        subsection=f"Table {table_id}",
                        start_char=start,
                        end_char=end,
                        metadata={
                            **base_metadata,
                            "chunk_type": "table",
                            "table_id": table_id,
                            "section_key": section_key(heading),
                            "clause_ids": [],
                        },
                    )
                )

    chunks = _merge_page_break_fragments(chunks)

    logger.info(
        "Completed chunking for '%s': %d chunks generated.",
        document.file_name,
        len(chunks),
    )

    return chunks


def _merge_page_break_fragments(chunks: list[Chunk]) -> list[Chunk]:
    """Merge a tiny text fragment into the next chunk of the same section.

    Only merges when the fragment is the last text chunk on its page and the
    next chunk is the first text chunk of the following page with the same
    section, so unrelated provisions are never combined.
    """

    merged: list[Chunk] = []
    index = 0

    while index < len(chunks):
        chunk = chunks[index]
        following = chunks[index + 1] if index + 1 < len(chunks) else None

        if (
            following is not None
            and chunk.metadata.get("chunk_type") == "text"
            and following.metadata.get("chunk_type") == "text"
            and len(chunk.text) < MIN_CHUNK_SIZE
            and chunk.section == following.section
            and chunk.document_id == following.document_id
            and following.page_numbers
            and chunk.page_numbers
            and following.page_numbers[0] == chunk.page_numbers[-1] + 1
        ):
            following.text = f"{chunk.text}\n\n{following.text}"
            following.page_numbers = sorted(set(chunk.page_numbers + following.page_numbers))
            following.start_char = chunk.start_char
            following.subsection = chunk.subsection or following.subsection
            following.metadata["clause_ids"] = list(
                dict.fromkeys(
                    chunk.metadata.get("clause_ids", [])
                    + following.metadata.get("clause_ids", [])
                )
            )
            following.metadata["merged_page_break"] = True
            index += 1
            continue

        merged.append(chunk)
        index += 1

    return merged
