
from dataclasses import dataclass, field
from pathlib import Path
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
    """Represents a searchable passage from a legal document."""

    chunk_id: str
    document_id: str

    text: str
    page_numbers: list[int]

    section: Optional[str] = None
    subsection: Optional[str] = None

    start_char: int = 0
    end_char: int = 0

    metadata: dict = field(default_factory=dict)
