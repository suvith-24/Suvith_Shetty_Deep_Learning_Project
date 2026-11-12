
import pytest

from lexisync.chunking.legal_chunker import (
    detect_heading,
    split_into_sections,
    split_large_section,
    chunk_document,
)
from lexisync.schemas.document import Document, Page, Chunk


def test_detect_legal_heading():
    assert detect_heading("Article 6 - Lawfulness of processing")
    assert detect_heading("CHAPTER II")
    assert not detect_heading("This is ordinary legal text.")


def test_split_into_sections():
    text = (
        "Introduction text.\n"
        "Article 1 - Subject matter\n"
        "This is article one content.\n"
        "Article 2 - Scope\n"
        "This is article two content."
    )

    sections = split_into_sections(text)

    assert len(sections) == 3
    assert sections[1][0] == "Article 1 - Subject matter"
    assert sections[2][0] == "Article 2 - Scope"


def test_split_large_section():
    text = "This is a legal sentence. " * 100

    chunks = split_large_section(
        text=text,
        chunk_size=200,
        overlap=30,
    )

    assert len(chunks) > 1

    for chunk_text, start, end in chunks:
        assert len(chunk_text) <= 200
        assert start < end


def test_chunk_document():
    text = (
        "Article 1 - Subject matter\n"
        + "This is the legal content of article one. " * 10
    )

    document = Document(
        document_id="doc-001",
        file_name="sample.pdf",
        file_path="sample.pdf",
        total_pages=1,
        pages=[
            Page(
                page_number=1,
                text=text,
                character_count=len(text),
            )
        ],
    )

    chunks = chunk_document(document)

    assert len(chunks) >= 1
    assert isinstance(chunks[0], Chunk)
    assert chunks[0].document_id == "doc-001"
    assert chunks[0].page_numbers == [1]
    assert chunks[0].section == "Article 1 - Subject matter"


def test_empty_pages_are_skipped():
    document = Document(
        document_id="doc-002",
        file_name="empty.pdf",
        file_path="empty.pdf",
        total_pages=1,
        pages=[
            Page(
                page_number=1,
                text="   ",
                character_count=3,
                is_scanned=True,
            )
        ],
    )

    chunks = chunk_document(document)

    assert chunks == []


def test_invalid_chunk_size():
    document = Document(
        document_id="doc-003",
        file_name="sample.pdf",
        file_path="sample.pdf",
        total_pages=0,
    )

    with pytest.raises(ValueError):
        chunk_document(document, chunk_size=0)


def test_invalid_overlap():
    document = Document(
        document_id="doc-004",
        file_name="sample.pdf",
        file_path="sample.pdf",
        total_pages=0,
    )

    with pytest.raises(ValueError):
        chunk_document(document, chunk_size=100, overlap=100)



def test_section_continues_across_pages():
    """A section heading should carry forward to the next page."""

    document = Document(
        document_id="doc-005",
        file_name="legal.pdf",
        file_path="legal.pdf",
        total_pages=2,
        pages=[
            Page(
                page_number=10,
                text=(
                    "Article 6 - Lawfulness of processing\n"
                    + "Processing shall be lawful only if " * 10
                ),
                character_count=300,
            ),
            Page(
                page_number=11,
                text=(
                    "The controller must ensure that "
                    * 10
                ),
                character_count=400,
            ),
        ],
    )

    chunks = chunk_document(document)

    page_11_chunks = [
        chunk for chunk in chunks
        if 11 in chunk.page_numbers
    ]

    assert len(page_11_chunks) > 0

    for chunk in page_11_chunks:
        assert chunk.section == "Article 6 - Lawfulness of processing"
