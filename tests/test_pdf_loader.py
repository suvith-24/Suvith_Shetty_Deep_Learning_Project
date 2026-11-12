
from pathlib import Path

import pytest
import pymupdf

from lexisync.ingestion.pdf_loader import (
    load_pdf,
    _repair_soft_hyphen_line_breaks,
    _reconstruct_text_from_words,
)
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


def test_soft_hyphen_line_break_is_repaired():
    text = "The authoris\u00ad\nation must be obtained."

    result = _repair_soft_hyphen_line_breaks(text)

    assert result == "The authorisation must be obtained."


def test_soft_hyphen_with_indentation_is_repaired():
    text = "The identifi\u00ad\n    cation process."

    result = _repair_soft_hyphen_line_breaks(text)

    assert result == "The identification process."


def test_remaining_soft_hyphens_are_removed():
    text = "inter\u00adnational organisation"

    result = _repair_soft_hyphen_line_breaks(text)

    assert result == "international organisation"


def test_ordinary_hyphens_are_preserved():
    text = "The data-protection\nframework is applicable."

    result = _repair_soft_hyphen_line_breaks(text)

    assert result == text


def test_paragraph_boundaries_are_preserved():
    text = "First paragraph.\n\nSecond paragraph."

    result = _repair_soft_hyphen_line_breaks(text)

    assert result == text


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

    # Verify document metadata.
    assert result.document_id == "gdpr"
    assert result.file_name == "gdpr.pdf"

    # Verify soft-hyphen repair on the Article 46 page.
    article_46_page = result.pages[61]

    assert "authorisation" in article_46_page.text
    assert "\u00ad" not in article_46_page.text
    assert "authoris\n" not in article_46_page.text

    # Verify the paragraph number is not inserted inside the word.
    assert "authoris2.ation" not in article_46_page.text
    assert "2. The appropriate safeguards" in article_46_page.text


def test_word_reconstruction_preserves_spaces_and_structure():
    words = [
        (232.21, 786.04, 268.99, 795.64, "economic", 0, 0, 0),
        (271.84, 786.04, 300.63, 795.64, "activity,", 0, 0, 1),
        (303.47, 786.04, 338.56, 795.64, "including", 0, 0, 2),
        (82.09, 800.00, 104.60, 809.60, "another", 0, 1, 0),
        (107.49, 800.00, 115.16, 809.60, "line", 0, 1, 1),
        (82.09, 820.00, 120.00, 829.60, "New", 1, 0, 0),
        (123.00, 820.00, 160.00, 829.60, "block", 1, 0, 1),
    ]

    result = _reconstruct_text_from_words(words)

    assert result == (
        "economic activity, including\n"
        "another line\n\n"
        "New block"
    )


def test_paragraph_number_and_soft_hyphen_are_reconstructed_together():
    """
    Reproduce the GDPR Article 46 PDF layout.

    The paragraph number has a different PyMuPDF line ID
    from the paragraph text, despite sharing the same
    physical baseline.

    The word 'authorisation' is split across two lines.
    """

    words = [
        (67.35, 246.446, 74.55, 256.042, "2.", 4, 0, 0),
        (88.95, 246.446, 103.06, 256.042, "The", 4, 1, 0),
        (105.90, 246.446, 149.77, 256.042, "appropriate", 4, 1, 1),
        (152.55, 246.446, 191.49, 256.042, "safeguards", 4, 1, 2),
        (194.34, 246.446, 223.58, 256.042, "referred", 4, 1, 3),
        (226.42, 246.446, 234.19, 256.042, "to", 4, 1, 4),
        (236.97, 246.446, 244.33, 256.042, "in", 4, 1, 5),
        (247.06, 246.446, 285.22, 256.042, "paragraph", 4, 1, 6),
        (288.05, 246.446, 293.16, 256.042, "1", 4, 1, 7),
        (296.04, 246.446, 311.94, 256.042, "may", 4, 1, 8),
        (314.75, 246.446, 323.51, 256.042, "be", 4, 1, 9),
        (326.37, 246.446, 359.53, 256.042, "provided", 4, 1, 10),
        (362.37, 246.446, 374.83, 256.042, "for,", 4, 1, 11),
        (377.68, 246.446, 407.16, 256.042, "without", 4, 1, 12),
        (410.00, 246.446, 444.36, 256.042, "requiring", 4, 1, 13),
        (447.13, 246.446, 460.60, 256.042, "any", 4, 1, 14),
        (463.34, 246.446, 491.24, 256.042, "specific", 4, 1, 15),
        (494.07, 246.446, 527.94, 256.042, "authoris\u00ad", 4, 1, 16),
        (67.35, 256.991, 86.55, 266.586, "ation", 4, 2, 0),
        (89.40, 256.991, 107.98, 266.586, "from", 4, 2, 1),
        (110.89, 256.991, 114.96, 266.586, "a", 4, 2, 2),
        (117.86, 256.991, 161.64, 266.586, "supervisory", 4, 2, 3),
        (164.52, 256.991, 200.84, 266.586, "authority,", 4, 2, 4),
        (203.69, 256.991, 214.97, 266.586, "by:", 4, 2, 5),
    ]

    result = _reconstruct_text_from_words(words)
    result = _repair_soft_hyphen_line_breaks(result)

    assert result == (
        "2. The appropriate safeguards referred to in paragraph "
        "1 may be provided for, without requiring any specific "
        "authorisation\n"
        "from a supervisory authority, by:"
    )

    assert "authorisation" in result
    assert "authoris2.ation" not in result
    assert "\u00ad" not in result
