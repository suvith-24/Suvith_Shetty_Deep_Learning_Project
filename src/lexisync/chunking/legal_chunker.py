
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
        r"^\s*CHAPTER\s+[IVXLCDM]+(?:\s*[-–—:]\s*.+)?\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*Article\s+\d+[A-Za-z]?(?:\s*[-–—:]\s*.+)?\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*SECTION\s+\d+[A-Za-z]?(?:\s*[-–—:]\s*.+)?\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*\d{1,2}\.\d{1,2}\.?\s+[A-Z][^\n]{0,100}$"
    ),
]


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

    return any(
        pattern.match(line)
        for pattern in HEADING_PATTERNS
    )


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
    current_lines = []

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

    for line in lines:

        stripped = line.strip()

        if stripped and detect_heading(stripped):

            save_section(
                current_heading,
                current_lines,
                section_start,
            )

            current_heading = stripped
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


def chunk_document(
    document: Document,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Chunk]:
    """
    Convert a structured legal document into searchable chunks.

    Preserves:
        - Document IDs
        - Legal section headings
        - Original PDF page numbers
        - Original extracted-text character offsets
        - Configured maximum chunk size

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

    chunks = []

    current_section = "General"

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

        sections = split_into_sections(cleaned_text)

        for heading, section_text, section_start, _ in sections:

            if heading != "General":
                current_section = heading

            else:
                heading = current_section

            passages = split_large_section(
                text=section_text,
                chunk_size=chunk_size,
                overlap=overlap,
            )

            for passage, start, end in passages:

                chunk = Chunk(
                    chunk_id=str(uuid4()),
                    document_id=document.document_id,
                    text=passage,
                    page_numbers=[page.page_number],
                    section=heading,
                    start_char=section_start + start,
                    end_char=section_start + end,
                )

                chunks.append(chunk)

    logger.info(
        "Completed chunking for '%s': %d chunks generated.",
        document.file_name,
        len(chunks),
    )

    return chunks
