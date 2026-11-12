"""Table detection and conversion into searchable, structure-preserving text.

PyMuPDF's ``Page.find_tables`` detects ruled and aligned tables. Spanning
(merged) cells are reported as ``None`` in every position the span covers
except the first, so they are forward-filled. A header spanning three
columns therefore labels all three. Each table is rendered as a pipe table
whose rows keep their column relationships.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from lexisync.utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class ExtractedTable:
    """A table found on a page."""

    table_id: str
    page_number: int
    bbox: tuple[float, float, float, float]
    header: list[str]
    rows: list[list[str]]

    @property
    def n_rows(self) -> int:
        return len(self.rows)

    @property
    def n_cols(self) -> int:
        return len(self.header) if self.header else max((len(r) for r in self.rows), default=0)

    def to_text(self) -> str:
        """Render as a pipe-delimited table preceded by a caption line."""

        lines = [f"[Table {self.table_id} — page {self.page_number}]"]
        if self.header:
            lines.append("| " + " | ".join(self.header) + " |")
            lines.append("|" + "---|" * len(self.header))
        for row in self.rows:
            lines.append("| " + " | ".join(row) + " |")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["bbox"] = list(self.bbox)
        data["n_rows"] = self.n_rows
        data["n_cols"] = self.n_cols
        data["text"] = self.to_text()
        return data


def _clean_cell(value) -> str | None:
    if value is None:
        return None
    return " ".join(str(value).split())


def normalize_grid(raw_rows: list[list]) -> list[list[str]]:
    """Forward-fill horizontally merged cells and blank vertical spans.

    * ``None`` to the right of a filled cell in the same row: horizontal span,
      copy the value from the left.
    * ``None`` in the first column: vertical span, copy from the cell above.
    * Remaining ``None`` values become empty strings.
    """

    grid: list[list[str]] = []

    for row_index, raw_row in enumerate(raw_rows):
        row: list[str] = []
        for column_index, raw_value in enumerate(raw_row):
            value = _clean_cell(raw_value)
            if value is None:
                if column_index > 0 and row and row[-1]:
                    value = row[-1]
                elif column_index == 0 and row_index > 0 and grid:
                    value = grid[-1][0] if grid[-1] else ""
                else:
                    value = ""
            row.append(value)
        grid.append(row)

    return grid


def _cell_texts(pdf_page, table, fallback: list[list]) -> list[list]:
    """Text of every cell taken from the page inside the cell's bounding box.

    Merged (spanned) positions stay ``None`` so ``normalize_grid`` can fill
    them. Falls back to ``Table.extract`` output on any failure.
    """

    try:
        rows = []
        for row in table.rows:
            values = []
            for cell in row.cells:
                if cell is None:
                    values.append(None)
                    continue
                text = pdf_page.get_text("text", clip=cell).strip()
                values.append(" ".join(text.split()))
            rows.append(values)
        if len(rows) == len(fallback):
            return rows
    except Exception:
        pass
    return fallback


def _is_meaningful(grid: list[list[str]]) -> bool:
    """Reject 1×N / N×1 "tables" that are really ruled paragraphs."""

    if len(grid) < 2:
        return False
    if max((len(row) for row in grid), default=0) < 2:
        return False
    filled = sum(1 for row in grid for cell in row if cell)
    return filled >= 4


MIN_RULING_SEGMENTS = 4


def has_ruling_lines(pdf_page) -> bool:
    """Cheap prefilter: does the page draw enough lines/rectangles to hold a table?

    ``find_tables`` uses the "lines" strategy (vector rulings). Skipping pages
    without rulings gives identical detections at a fraction of the cost:
    the 88-page GDPR PDF drops from about 27 s to under 1 s.
    """

    try:
        drawings = pdf_page.get_drawings()
    except Exception:
        return True  # be safe: let find_tables decide

    # Rulings in the top/bottom margins belong to running headers
    # (e.g. the Official Journal "EN" box), not to body tables.
    height = pdf_page.rect.height
    top, bottom = height * 0.09, height * 0.93

    segments = 0
    for drawing in drawings:
        rect = drawing.get("rect")
        if rect is not None and (rect.y1 <= top or rect.y0 >= bottom):
            continue
        for item in drawing.get("items", []):
            if item and item[0] in {"l", "re"}:
                segments += 1
                if segments >= MIN_RULING_SEGMENTS:
                    return True
    return False


def extract_tables(pdf_page, page_number: int) -> list[ExtractedTable]:
    """Detect tables on a PyMuPDF page. Failures produce an empty list."""

    if not has_ruling_lines(pdf_page):
        return []

    try:
        finder = pdf_page.find_tables()
    except Exception as error:  # PyMuPDF raises several internal types.
        logger.warning("Table detection failed on page %d: %s", page_number, error)
        return []

    tables: list[ExtractedTable] = []

    for index, table in enumerate(finder.tables, start=1):
        try:
            raw_rows = table.extract()
        except Exception as error:
            logger.warning(
                "Table extraction failed on page %d (table %d): %s",
                page_number,
                index,
                error,
            )
            continue

        # Re-read each cell from its bounding box: this keeps the spaces
        # between words that ``Table.extract`` can drop for tightly set text.
        raw_rows = _cell_texts(pdf_page, table, raw_rows)

        grid = normalize_grid(raw_rows)
        if not _is_meaningful(grid):
            continue

        external_header = None
        try:
            if table.header and table.header.external:
                external_header = [_clean_cell(name) for name in table.header.names]
        except Exception:
            external_header = None

        # PyMuPDF reports a header outside the table body separately;
        # otherwise the first grid row is the header.
        if external_header and any(external_header):
            header = normalize_grid([external_header])[0]
            rows = grid
        else:
            header, rows = grid[0], grid[1:]

        tables.append(
            ExtractedTable(
                table_id=f"{page_number}.{index}",
                page_number=page_number,
                bbox=tuple(round(float(v), 2) for v in table.bbox),
                header=header,
                rows=rows,
            )
        )

    return tables
