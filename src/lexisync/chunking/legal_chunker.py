
import re
from uuid import uuid4

from lexisync.schemas.document import Chunk, Document
from lexisync.utils.logger import get_logger


logger = get_logger(__name__)


# Initial chunking configuration
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150
MIN_CHUNK_SIZE = 100


# Legal heading patterns
HEADING_PATTERNS = [
    re.compile(r"^\s*CHAPTER\s+[IVXLCDM0-9]+.*$", re.IGNORECASE),
    re.compile(r"^\s*Article\s+\d+[A-Za-z]?\b.*$", re.IGNORECASE),
    re.compile(r"^\s*SECTION\s+\d+[A-Za-z]?\b.*$", re.IGNORECASE),
    re.compile(r"^\s*\d+(?:\.\d+)+\.?\s+[A-Z].*$"),
]


def detect_heading(line: str) -> bool:
    """Check whether a line looks like a legal heading."""

    return any(
        pattern.match(line)
        for pattern in HEADING_PATTERNS
    )


def split_into_sections(text: str) -> list[tuple[str, str, int, int]]:
    """
    Split document text into sections using detected headings.

    Returns:
        List of (heading, section_text, start_char, end_char).
    """

    lines = text.splitlines(keepends=True)

    sections = []
    current_heading = "General"
    current_lines = []

    position = 0
    section_start = 0

    for line in lines:
        stripped = line.strip()

        if stripped and detect_heading(stripped):
            if current_lines:
                section_text = "".join(current_lines).strip()

                if section_text:
                    sections.append(
                        (
                            current_heading,
                            section_text,
                            section_start,
                            position,
                        )
                    )

            current_heading = stripped
            current_lines = [line]
            section_start = position

        else:
            current_lines.append(line)

        position += len(line)

    if current_lines:
        section_text = "".join(current_lines).strip()

        if section_text:
            sections.append(
                (
                    current_heading,
                    section_text,
                    section_start,
                    position,
                )
            )

    return sections


def split_large_section(
    text: str,
    chunk_size: int,
    overlap: int,
) -> list[tuple[str, int, int]]:
    """
    Split an oversized section into smaller passages.

    Prefer paragraph boundaries and fall back to whitespace
    boundaries when necessary.

    Returns:
        List of (chunk_text, start_char, end_char).
    """

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)

        if end < text_length:
            # Prefer a paragraph boundary.
            boundary = text.rfind("\n\n", start, end)

            if boundary == -1 or boundary <= start:
                # Fall back to a whitespace boundary.
                boundary = text.rfind(" ", start, end)

            if boundary > start:
                end = boundary

        chunk_text = text[start:end].strip()

        if chunk_text:
            actual_start = start + len(text[start:end]) - len(text[start:end].lstrip())
            actual_end = actual_start + len(chunk_text)

            chunks.append(
                (chunk_text, actual_start, actual_end)
            )

        if end >= text_length:
            break

        next_start = max(start + 1, end - overlap)

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

    Preserves document IDs, section headings and page numbers.
    Carries section headings across consecutive PDF pages.
    """

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero.")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError(
            "overlap must be non-negative and smaller than chunk_size."
        )

    chunks = []

    # Tracks the most recently detected legal section.
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

        sections = split_into_sections(page.text)

        for heading, section_text, section_start, _ in sections:

            # Update the active section when a new heading is found.
            if heading != "General":
                current_section = heading

            # If no new heading exists, inherit the previous section.
            else:
                heading = current_section

            passages = split_large_section(
                text=section_text,
                chunk_size=chunk_size,
                overlap=overlap,
            )

            for passage, start, end in passages:

                if len(passage) < MIN_CHUNK_SIZE:
                    if chunks:
                        previous = chunks[-1]

                        if (
                            previous.section == heading
                            and previous.page_numbers == [page.page_number]
                        ):
                            previous.text += "\n" + passage
                            previous.end_char = section_start + end
                            continue

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