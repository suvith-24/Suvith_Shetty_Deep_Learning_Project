
import re
from collections import defaultdict
from pathlib import Path

import pymupdf

from lexisync.schemas.document import Document, Page


# Words whose vertical coordinates differ by no more than
# this tolerance are considered part of the same physical line.
LINE_Y_TOLERANCE = 2.0


def _repair_soft_hyphen_line_breaks(text: str) -> str:
    """
    Remove remaining PDF soft-hyphen characters.

    Soft-hyphenated words split across physical lines are
    reconstructed in _reconstruct_text_from_words().
    """

    text = re.sub(
        r"\u00ad[ \t]*\r?\n[ \t]*",
        "",
        text,
    )

    return text.replace("\u00ad", "")


def _group_words_into_physical_lines(
    words: list[tuple],
) -> list[list[tuple]]:
    """
    Group PDF words by their physical vertical position.

    PyMuPDF may assign different line identifiers to words
    that visually belong to the same physical line.

    Grouping by vertical coordinates prevents paragraph
    numbers and their corresponding text from being separated.

    Word tuple structure:
        x0, y0, x1, y1, word, block_no, line_no, word_no
    """

    sorted_words = sorted(
        words,
        key=lambda word: (
            word[1],
            word[0],
        ),
    )

    physical_lines = []

    for word in sorted_words:
        word_y = word[1]

        if (
            not physical_lines
            or abs(word_y - physical_lines[-1][0][1])
            > LINE_Y_TOLERANCE
        ):
            physical_lines.append([word])
        else:
            physical_lines[-1].append(word)

    for line in physical_lines:
        line.sort(
            key=lambda word: (
                word[0],
                word[2],
            )
        )

    return physical_lines


def _reconstruct_text_from_words(words: list[tuple]) -> str:
    """
    Reconstruct page text using coordinate-based word extraction.

    Words are grouped by their original block identifiers.
    Within each block, words are grouped into physical lines
    using their vertical coordinates.

    Soft-hyphenated words split across physical lines are joined
    without losing paragraph numbers or word boundaries.

    Paragraph and block boundaries are preserved.
    """

    blocks = defaultdict(list)

    for word in words:
        block_no = word[5]
        blocks[block_no].append(word)

    ordered_blocks = []

    for block_no, block_words in blocks.items():

        physical_lines = _group_words_into_physical_lines(
            block_words
        )

        reconstructed_lines = []

        for line in physical_lines:

            tokens = [
                word[4] for word in line
            ]

            if not tokens:
                continue

            # Join a word split by a PDF soft hyphen.
            #
            # Example:
            # Previous line: authoris\u00ad
            # Current line:  ation from ...
            #
            # Result: authorisation from ...
            if (
                reconstructed_lines
                and reconstructed_lines[-1]
                and reconstructed_lines[-1][-1].endswith("\u00ad")
            ):
                previous_token = reconstructed_lines[-1][-1]

                reconstructed_lines[-1][-1] = (
                    previous_token[:-1] + tokens.pop(0)
                )

            if tokens:
                reconstructed_lines.append(tokens)

        if not reconstructed_lines:
            continue

        block_text = "\n".join(
            " ".join(tokens)
            for tokens in reconstructed_lines
        )

        block_y = min(
            word[1] for word in block_words
        )

        block_x = min(
            word[0] for word in block_words
        )

        ordered_blocks.append(
            (
                block_y,
                block_x,
                block_no,
                block_text,
            )
        )

    ordered_blocks.sort(
        key=lambda block: (
            block[0],
            block[1],
        )
    )

    return "\n\n".join(
        block[3] for block in ordered_blocks
    )


def load_pdf(pdf_path: str | Path) -> Document:
    """
    Extract text from a PDF page by page.

    Word-level extraction is used to preserve word boundaries.

    Physical-line reconstruction handles:
    - Different PyMuPDF line IDs on the same visual line.
    - Paragraph numbers in hanging layouts.
    - Soft-hyphenated words split across physical lines.
    - Original block and paragraph boundaries.

    Pages with very little extractable text are flagged
    as potentially scanned pages.

    Returns:
        Document: Structured document containing extracted pages.
    """

    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(
            f"PDF file not found: {path}"
        )

    if path.suffix.lower() != ".pdf":
        raise ValueError(
            "The supplied file must be a PDF."
        )

    pages = []

    with pymupdf.open(path) as pdf:

        if pdf.is_encrypted:
            raise ValueError(
                "Encrypted PDFs are not currently supported."
            )

        for page_number, pdf_page in enumerate(
            pdf,
            start=1,
        ):

            words = pdf_page.get_text(
                "words",
                sort=True,
            )

            text = _reconstruct_text_from_words(words)

            text = _repair_soft_hyphen_line_breaks(
                text
            ).strip()

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
