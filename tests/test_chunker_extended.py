"""Legal-aware chunking: headings, clause IDs, multi-page sections, tables."""

from lexisync.chunking.legal_chunker import (
    chunk_document,
    detect_heading,
    find_clause_markers,
    section_key,
    split_into_sections,
)
from lexisync.schemas.document import Document, Page


def _doc(*page_texts, start=1):
    pages = [Page(page_number=start + i, text=t, character_count=len(t)) for i, t in enumerate(page_texts)]
    return Document(document_id="doc", file_name="doc.pdf", file_path="doc.pdf", total_pages=len(pages), pages=pages)


def test_extended_heading_grammar():
    for heading in [
        "PART II",
        "SCHEDULE 1 - FEES",
        "Annex I",
        "Appendix A",
        "Section 7.2 Limitation of liability",
        "7. LIMITATION OF LIABILITY",
        "7.2 Limitation of liability",
        "§ 5 Kündigung",
        "Article 83",
    ]:
        assert detect_heading(heading), heading

    for sentence in [
        "3.2 Review. The responsible department shall review stored records at least once.",
        "1. The controller shall implement measures.",
        "Schedule 2 sets out the fees payable by the customer under this agreement.",
        "Section 7 of the Agreement is amended as follows and shall apply to all orders placed.",
    ]:
        assert not detect_heading(sentence), sentence


def test_bare_article_heading_absorbs_title_line():
    sections = split_into_sections("Article 83\nGeneral conditions for imposing fines\n1. Each authority shall ensure.")
    assert sections[0][0] == "Article 83 — General conditions for imposing fines"


def test_section_key_normalisation():
    assert section_key("Article 83 — General conditions") == "article 83"
    assert section_key("SECTION 7.2 Liability") == "section 7.2"
    assert section_key("7. LIMITATION OF LIABILITY") == "section 7"
    assert section_key("SCHEDULE 1 - FEES") == "schedule 1"
    assert section_key("General") is None


def test_nested_numbering_produces_clause_ids():
    text = "ARTICLE 3 — RETENTION\n3.1 Period. Records are kept five years.\n3.2 Review. Records are reviewed yearly.\n3.2.1 Detail. Reviews are logged."
    chunks = chunk_document(_doc(text))
    assert chunks[0].section == "ARTICLE 3 — RETENTION"
    assert chunks[0].metadata["clause_ids"] == ["3.1", "3.2", "3.2.1"]
    assert chunks[0].metadata["section_key"] == "article 3"


def test_gdpr_style_paragraph_numbers_become_article_clauses():
    text = "Article 83\nGeneral conditions\n1.\nEach authority shall ensure fines are effective.\n4.\nInfringements shall be subject to fines up to 10 000 000 EUR."
    markers = find_clause_markers(text)
    assert [m[1] for m in markers] == ["1", "4"]
    chunks = chunk_document(_doc(text))
    assert chunks[0].metadata["clause_ids"] == ["83(1)", "83(4)"]


def test_multi_page_section_carries_heading_and_clause():
    page_one = "Article 5 - Principles\n1. Personal data shall be processed lawfully. " + "More text. " * 20
    page_two = "and kept accurate. " * 20
    chunks = chunk_document(_doc(page_one, page_two, start=35))
    second = [c for c in chunks if 36 in c.page_numbers]
    assert second and all(c.section == "Article 5 - Principles" for c in second)
    assert second[0].subsection == "5(1)"


def test_missing_headings_default_to_general():
    chunks = chunk_document(_doc("This page has ordinary prose without any legal heading at all. " * 3))
    assert chunks[0].section == "General"


def test_irregular_formatting_still_splits_on_headings():
    text = "   ARTICLE 1 — DEFINITIONS   \n\n\n  Term means a thing.\n\t\nARTICLE 2 — SCOPE\n   This applies everywhere."
    sections = [c.section for c in chunk_document(_doc(text))]
    assert sections == ["ARTICLE 1 — DEFINITIONS", "ARTICLE 2 — SCOPE"]


def test_large_paragraph_is_split_within_size_and_keeps_section():
    text = "Article 9 - Special categories\n" + "This sentence is part of a very long paragraph. " * 80
    chunks = chunk_document(_doc(text), chunk_size=400, overlap=50)
    assert len(chunks) > 3
    assert all(len(c.text) <= 400 for c in chunks)
    assert all(c.section == "Article 9 - Special categories" for c in chunks)


def test_tables_become_separate_unsplit_chunks():
    table = "[Table 2.1 — page 2]\n| Record | Period |\n|---|---|\n| Payroll | 10 years |\n| Access log | 12 months |\n"
    text = "SCHEDULE 1 - RETENTION SCHEDULE\nIntroductory sentence for the schedule.\n\n" + table + "\nClosing note after the table."
    chunks = chunk_document(_doc(text, start=2))
    tables = [c for c in chunks if c.metadata["chunk_type"] == "table"]
    texts = [c for c in chunks if c.metadata["chunk_type"] == "text"]
    assert len(tables) == 1
    assert tables[0].text.startswith("[Table 2.1")
    assert "| Payroll | 10 years |" in tables[0].text
    assert tables[0].section == "SCHEDULE 1 - RETENTION SCHEDULE"
    assert tables[0].subsection == "Table 2.1"
    assert all("| Payroll" not in c.text for c in texts)


def test_large_table_is_split_by_rows_with_repeated_header():
    rows = "".join(f"| Item {i} | {i} years |\n" for i in range(80))
    text = "[Table 1.1 — page 1]\n| Item | Period |\n|---|---|\n" + rows
    chunks = [c for c in chunk_document(_doc(text), chunk_size=300, overlap=20) if c.metadata["chunk_type"] == "table"]
    assert len(chunks) > 2
    assert all(c.text.startswith("[Table 1.1 — page 1]\n| Item | Period |") for c in chunks)


def test_tiny_page_break_fragment_is_merged_with_next_page():
    # 710 characters, a paragraph break, then a 13-character fragment that the
    # 720-character limit pushes into its own chunk at the end of page 37.
    page_one = "Article 7 - Consent\n" + "Consent must be freely given. " * 23 + "\n\nWithdrawal is"
    page_two = "as easy as giving consent. " * 10
    chunks = chunk_document(_doc(page_one, page_two, start=37), chunk_size=720, overlap=0)
    merged = [c for c in chunks if c.page_numbers == [37, 38]]
    assert merged and merged[0].metadata.get("merged_page_break")
    assert merged[0].text.startswith("Withdrawal is")
    assert not any(c.text == "Withdrawal is" for c in chunks)


def test_file_name_and_extraction_method_are_preserved():
    page = Page(page_number=1, text="Article 1 - Scope\nThis applies.", character_count=30, extraction_method="ocr", ocr_confidence=91.0)
    document = Document(document_id="d", file_name="scan.pdf", file_path="scan.pdf", total_pages=1, pages=[page])
    chunk = chunk_document(document)[0]
    assert chunk.metadata["file_name"] == "scan.pdf"
    assert chunk.metadata["extraction_method"] == "ocr"
    assert chunk.metadata["ocr_confidence"] == 91.0
