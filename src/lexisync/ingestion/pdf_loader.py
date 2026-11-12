from pathlib import Path

import pymupdf

from lexisync.schemas.document import Document, Page


def load_pdf(pdf_path: str | Path) -> Document:
    """
    Extract text from a PDF page by page.

    Pages with very little extractable text are flagged as
    potentially scanned pages.

    Returns:
        Document: Structured document containing extracted pages.
    """

    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError("The supplied file must be a PDF.")

    pages = []

    with pymupdf.open(path) as pdf:
        if pdf.is_encrypted:
            raise ValueError(
                "Encrypted PDFs are not currently supported."
            )

        for page_number, pdf_page in enumerate(pdf, start=1):

            text = pdf_page.get_text("text", sort=True).strip()

            # Flag pages with little or no extractable text.
            is_scanned = len(text) < 50

            page = Page(
                page_number=page_number,
                text=text,
                character_count=len(text),
                is_scanned=is_scanned,
                has_images=len(pdf_page.get_images()) > 0,
            )

            pages.append(page)

    return Document(
        document_id=path.stem,
        file_name=path.name,
        file_path=str(path.resolve()),
        total_pages=len(pages),
        pages=pages,
    )