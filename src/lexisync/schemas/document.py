"""Core data structures shared by ingestion, chunking, retrieval and generation.

All fields added after the first release have defaults so that persisted chunk
metadata written by older versions can still be loaded with ``Chunk(**item)``.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Page:
    """Represents one page extracted from a legal PDF."""

    page_number: int
    text: str
    character_count: int
    is_scanned: bool = False

    has_images: bool = False
    has_tables: bool = False

    # How the text was obtained: "text" (digital layer), "ocr", or "none".
    extraction_method: str = "text"
    ocr_confidence: Optional[float] = None
    column_count: int = 1

    # Recurring margin lines removed from ``text`` (kept for transparency).
    header_lines: list[str] = field(default_factory=list)
    footer_lines: list[str] = field(default_factory=list)
    footnotes: list[str] = field(default_factory=list)

    # Extracted tables (see ``lexisync.ingestion.tables.ExtractedTable.to_dict``).
    tables: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class Document:
    """Represents an ingested legal PDF document."""

    document_id: str
    file_name: str
    file_path: str

    total_pages: int
    pages: list[Page] = field(default_factory=list)

    title: Optional[str] = None
    author: Optional[str] = None

    metadata: dict = field(default_factory=dict)


@dataclass
class Chunk:
    """Represents a searchable passage from a legal document.

    ``metadata`` carries optional provenance such as ``clause_id``,
    ``chunk_type`` ("text" or "table"), ``extraction_method`` and
    ``file_name``.
    """

    chunk_id: str
    document_id: str

    text: str
    page_numbers: list[int]

    section: Optional[str] = None
    subsection: Optional[str] = None

    start_char: int = 0
    end_char: int = 0

    metadata: dict = field(default_factory=dict)
