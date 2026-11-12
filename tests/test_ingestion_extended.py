"""Ingestion on synthetic PDFs: layout, running heads, tables, scanned pages, OCR, errors."""

import pymupdf
import pytest

from lexisync.ingestion import layout
from lexisync.ingestion.ocr import find_tesseract, parse_tesseract_tsv
from lexisync.ingestion.pdf_loader import PDFIngestionError, load_pdf
from lexisync.ingestion.tables import normalize_grid
from tests.conftest import legal_lines


def _three_pages_with_heads():
    pages = []
    for n in range(1, 4):
        items = [(56, 30, "ACME Vendor Agreement - Confidential draft", 8)]
        items += legal_lines(120, [f"Section {n} Obligations of the parties number {n}", "The supplier shall deliver the goods."])
        items.append((280, 820, f"Page {n} of 3", 8))
        pages.append(items)
    return pages


def test_running_headers_and_page_numbers_are_removed(pdf_factory):
    document = load_pdf(pdf_factory("heads.pdf", _three_pages_with_heads()))

    for page in document.pages:
        assert "Confidential draft" not in page.text
        assert "of 3" not in page.text
        assert "The supplier shall deliver the goods." in page.text
        assert page.header_lines and page.footer_lines
    assert document.metadata["running_heads_removed"] == 6


def test_running_heads_kept_when_disabled(pdf_factory):
    document = load_pdf(pdf_factory("keep.pdf", _three_pages_with_heads()), remove_running_heads=False)
    assert "Confidential draft" in document.pages[0].text


def test_two_column_page_is_read_column_by_column(pdf_factory):
    left = [(56, 120 + i * 14, f"Left column sentence {i} continues here.", 10) for i in range(8)]
    right = [(320, 120 + i * 14, f"Right column sentence {i} continues here.", 10) for i in range(8)]
    # Separate text blocks per column: insert with a vertical gap between groups.
    document = load_pdf(pdf_factory("columns.pdf", [left + right]))
    text = document.pages[0].text

    assert document.pages[0].column_count == 2
    assert text.index("Left column sentence 7") < text.index("Right column sentence 0")


def test_single_column_page_keeps_top_to_bottom_order(pdf_factory):
    document = load_pdf(pdf_factory("single.pdf", [legal_lines(100, ["First line of the clause.", "Second line of the clause."])]))
    page = document.pages[0]
    assert page.column_count == 1
    assert page.text.index("First line") < page.text.index("Second line")


def test_detect_columns_requires_both_halves():
    width = 600
    blocks = [(50, 100, 280, 140), (50, 150, 280, 190), (320, 100, 560, 140), (320, 150, 560, 190)]
    assert layout.detect_columns(blocks, width) == 2
    assert layout.detect_columns([(50, 100, 560, 140), (50, 150, 560, 190)], width) == 1


def test_page_number_lines_are_recognised():
    assert layout.is_page_number_line("12")
    assert layout.is_page_number_line("Page 3 of 10")
    assert layout.is_page_number_line("- 4 -")
    assert not layout.is_page_number_line("Article 12 applies")


def _ruled_table_pdf(path):
    document = pymupdf.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((56, 90), "SCHEDULE 1 - FEES", fontsize=12)
    rows = [["Service", "Fee", "Fee"], ["", "Annual", "Monthly"], ["Hosting", "EUR 1200", "EUR 100"], ["Support", "EUR 600", "EUR 50"]]
    x = [56, 236, 386, 536]
    top, height = 120, 24
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            if (r == 0 and c == 2) or not value:
                continue
            page.insert_text((x[c] + 6, top + r * height + 16), value, fontsize=10)
    shape = page.new_shape()
    bottom = top + len(rows) * height
    for r in range(len(rows) + 1):
        shape.draw_line((x[1] if r == 1 else x[0], top + r * height), (x[-1], top + r * height))
    for c, xl in enumerate(x):
        shape.draw_line((xl, top + height if c == 2 else top), (xl, bottom))
    shape.finish(width=0.8, color=(0, 0, 0))
    shape.commit()
    document.save(path)
    document.close()
    return path


def test_table_extraction_matches_manual_ground_truth(tmp_path):
    document = load_pdf(_ruled_table_pdf(tmp_path / "table.pdf"))
    page = document.pages[0]
    assert page.has_tables and len(page.tables) == 1

    table = page.tables[0]
    extracted = [table["header"]] + table["rows"]
    # Manually written ground truth; the spanning "Fee" header covers both
    # fee columns and the vertically merged "Service" cell repeats.
    truth = [
        ["Service", "Fee", "Fee"],
        ["Service", "Annual", "Monthly"],
        ["Hosting", "EUR 1200", "EUR 100"],
        ["Support", "EUR 600", "EUR 50"],
    ]
    cells = sum(len(row) for row in truth)
    correct = sum(a == b for row_a, row_b in zip(extracted, truth) for a, b in zip(row_a, row_b))
    assert correct / cells == 1.0
    assert "| Hosting | EUR 1200 | EUR 100 |" in page.text
    assert document.metadata["table_count"] == 1


def test_normalize_grid_fills_spans():
    grid = normalize_grid([["Name", "Fee", None], [None, "Annual", "Monthly"], ["A", "1", "2"]])
    assert grid == [["Name", "Fee", "Fee"], ["Name", "Annual", "Monthly"], ["A", "1", "2"]]


def _scanned_pdf(path):
    source = pymupdf.open()
    src = source.new_page()
    src.insert_text((72, 120), "ARTICLE 9 - SCANNED NOTICE", fontsize=16)
    src.insert_text((72, 160), "The licensee must pay the renewal fee within thirty days.", fontsize=14)
    png = src.get_pixmap(matrix=pymupdf.Matrix(2, 2)).tobytes("png")
    document = pymupdf.open()
    document.new_page().insert_image(pymupdf.Rect(0, 0, 595, 842), stream=png)
    document.save(path)
    document.close()
    source.close()
    return path


def test_scanned_page_flagged_without_ocr(tmp_path):
    document = load_pdf(_scanned_pdf(tmp_path / "scan.pdf"), enable_ocr=False)
    page = document.pages[0]
    assert page.is_scanned and page.has_images
    assert page.extraction_method == "none"
    assert any("OCR is disabled" in w for w in page.warnings)
    assert document.metadata["scanned_pages"] == [1]


@pytest.mark.skipif(find_tesseract() is None, reason="Tesseract not installed")
def test_scanned_page_is_ocr_processed(tmp_path):
    document = load_pdf(_scanned_pdf(tmp_path / "scan.pdf"), enable_ocr=True)
    page = document.pages[0]
    assert page.extraction_method == "ocr"
    assert "renewal fee" in page.text
    assert page.ocr_confidence is not None and page.ocr_confidence > 60
    assert document.metadata["ocr_pages"] == [1]


def test_parse_tesseract_tsv_orders_words_and_averages_confidence():
    tsv = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t0\t0\t1\t1\t90\tHello\n"
        "5\t1\t1\t1\t1\t2\t0\t0\t1\t1\t80\tworld\n"
        "5\t1\t2\t1\t1\t1\t0\t0\t1\t1\t70\tNext\n"
    )
    result = parse_tesseract_tsv(tsv)
    assert result.text == "Hello world\n\nNext"
    assert result.mean_confidence == pytest.approx(80.0)


def test_corrupt_pdf_is_rejected(tmp_path):
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF-1.4\nthis is not really a pdf")
    with pytest.raises(PDFIngestionError):
        load_pdf(path)


def test_empty_file_is_rejected(tmp_path):
    path = tmp_path / "empty.pdf"
    path.write_bytes(b"")
    with pytest.raises(PDFIngestionError, match="empty"):
        load_pdf(path)


def test_non_pdf_content_with_pdf_extension_is_rejected(tmp_path):
    path = tmp_path / "fake.pdf"
    path.write_text("hello", encoding="utf-8")
    with pytest.raises(PDFIngestionError, match="signature"):
        load_pdf(path)


def test_password_protected_pdf_is_rejected(tmp_path):
    path = tmp_path / "locked.pdf"
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "Secret clause")
    document.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="user")
    document.close()
    with pytest.raises(PDFIngestionError, match="password"):
        load_pdf(path)


def test_metadata_and_hash_are_recorded(pdf_factory):
    path = pdf_factory("meta.pdf", [legal_lines(100, ["Article 1 - Scope", "This Act applies."])], {"title": "Test Act", "author": "Parliament"})
    document = load_pdf(path)
    assert document.title == "Test Act"
    assert document.author == "Parliament"
    assert len(document.metadata["sha256"]) == 64
