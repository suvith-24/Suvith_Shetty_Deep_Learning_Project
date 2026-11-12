
from pathlib import Path

import pytest
import pymupdf

from lexisync.ingestion.pdf_loader import load_pdf
from lexisync.schemas.document import Document, Page


@pytest.fixture
def sample_pdf(tmp_path):
    """Create a small PDF with two pages for testing."""

    pdf_path = tmp_path / "sample.pdf"

    with pymupdf.open() as document:
        page1 = document.new_page()
        page1.insert_text(
            (72, 72),
            "This is a sample legal document for testing PDF extraction."
        )

        document.new_page()

        document.save(pdf_path)

    return pdf_path


def test_load_pdf_success(sample_pdf):
    result = load_pdf(sample_pdf)

    assert isinstance(result, Document)
    assert result.file_name == "sample.pdf"
    assert result.total_pages == 2
    assert len(result.pages) == 2


def test_page_numbers_are_preserved(sample_pdf):
    result = load_pdf(sample_pdf)

    assert isinstance(result.pages[0], Page)
    assert result.pages[0].page_number == 1
    assert result.pages[1].page_number == 2


def test_text_is_extracted(sample_pdf):
    result = load_pdf(sample_pdf)

    assert "sample legal document" in result.pages[0].text
    assert result.pages[0].character_count > 0


def test_empty_page_is_flagged_as_scanned(sample_pdf):
    result = load_pdf(sample_pdf)

    assert result.pages[1].is_scanned is True


def test_missing_pdf_raises_error():
    with pytest.raises(FileNotFoundError):
        load_pdf("data/raw/does_not_exist.pdf")


def test_invalid_extension_raises_error(tmp_path):
    text_file = tmp_path / "not_a_pdf.txt"
    text_file.write_text("This is not a PDF.")

    with pytest.raises(ValueError):
        load_pdf(text_file)


def test_real_gdpr_pdf():
    """Integration test using the downloaded GDPR document."""

    gdpr_path = Path("data/raw/gdpr.pdf")

    if not gdpr_path.exists():
        pytest.skip("GDPR test document is not available.")

    result = load_pdf(gdpr_path)

    assert isinstance(result, Document)
    assert result.total_pages == 88
    assert result.pages[0].character_count > 0
    assert "REGULATION" in result.pages[0].text

    # Verify document metadata
    assert result.document_id == "gdpr"
    assert result.file_name == "gdpr.pdf"
