"""Optional Tesseract OCR fallback for scanned (image-only) pages.

The Tesseract command-line binary is called directly, so no extra Python
dependency is needed. OCR runs only on pages whose digital text layer is
missing or nearly empty *and* which contain an image. It never runs on every
page.

Configuration (environment variables):
    LEXISYNC_OCR       "auto" (default) | "off"
    TESSERACT_CMD      explicit path to ``tesseract`` / ``tesseract.exe``
    LEXISYNC_OCR_LANG  Tesseract language code, default "eng"
"""

from __future__ import annotations

import csv
import io
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from lexisync.utils.logger import get_logger


logger = get_logger(__name__)

OCR_DPI = 300
OCR_TIMEOUT_SECONDS = 120

_WINDOWS_DEFAULT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")


@dataclass
class OCRResult:
    """Text recognised on one page plus the mean word confidence (0–100)."""

    text: str
    mean_confidence: float | None
    word_count: int


def ocr_mode() -> str:
    """Return the configured OCR mode ("auto" or "off")."""

    mode = os.getenv("LEXISYNC_OCR", "auto").strip().casefold()
    return mode if mode in {"auto", "off"} else "auto"


def find_tesseract() -> str | None:
    """Locate the Tesseract executable, or return ``None`` if unavailable."""

    configured = os.getenv("TESSERACT_CMD")
    if configured and Path(configured).is_file():
        return configured

    found = shutil.which("tesseract")
    if found:
        return found

    if _WINDOWS_DEFAULT.is_file():
        return str(_WINDOWS_DEFAULT)

    return None


def is_ocr_available() -> bool:
    """Return True when OCR is enabled and a Tesseract binary exists."""

    return ocr_mode() != "off" and find_tesseract() is not None


def parse_tesseract_tsv(tsv_text: str) -> OCRResult:
    """Convert Tesseract TSV output into reading-ordered text.

    Words are grouped by (block, paragraph, line). Paragraph breaks are
    preserved as blank lines. Confidence values of -1 (non-word rows) are
    ignored when averaging.
    """

    reader = csv.DictReader(
        io.StringIO(tsv_text),
        delimiter="\t",
        quoting=csv.QUOTE_NONE,
    )

    lines: dict[tuple[int, int, int], list[str]] = {}
    confidences: list[float] = []

    for row in reader:
        if row.get("level") != "5":
            continue

        word = (row.get("text") or "").strip()
        if not word:
            continue

        try:
            confidence = float(row.get("conf", "-1"))
        except ValueError:
            confidence = -1.0

        if confidence >= 0:
            confidences.append(confidence)

        key = (
            int(row.get("block_num", 0)),
            int(row.get("par_num", 0)),
            int(row.get("line_num", 0)),
        )
        lines.setdefault(key, []).append(word)

    output: list[str] = []
    previous_paragraph = None

    for (block, paragraph, _), words in sorted(lines.items()):
        if previous_paragraph is not None and previous_paragraph != (block, paragraph):
            output.append("")
        output.append(" ".join(words))
        previous_paragraph = (block, paragraph)

    mean_confidence = (
        sum(confidences) / len(confidences) if confidences else None
    )

    return OCRResult(
        text="\n".join(output).strip(),
        mean_confidence=mean_confidence,
        word_count=len(confidences),
    )


def ocr_png_bytes(png_bytes: bytes, language: str | None = None) -> OCRResult:
    """Run Tesseract on a rendered page image.

    Raises:
        RuntimeError: when Tesseract is unavailable or fails.
    """

    executable = find_tesseract()
    if executable is None:
        raise RuntimeError("Tesseract OCR is not installed or not on PATH.")

    language = language or os.getenv("LEXISYNC_OCR_LANG", "eng")

    with tempfile.TemporaryDirectory() as directory:
        image_path = Path(directory) / "page.png"
        image_path.write_bytes(png_bytes)

        completed = subprocess.run(
            [executable, str(image_path), "stdout", "-l", language, "--psm", "3", "tsv"],
            capture_output=True,
            timeout=OCR_TIMEOUT_SECONDS,
            check=False,
        )

    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Tesseract failed: {message[:300]}")

    return parse_tesseract_tsv(
        completed.stdout.decode("utf-8", errors="replace")
    )


def ocr_pdf_page(pdf_page, language: str | None = None) -> OCRResult:
    """Render a PyMuPDF page at 300 DPI and OCR it."""

    import pymupdf

    zoom = OCR_DPI / 72.0
    pixmap = pdf_page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    return ocr_png_bytes(pixmap.tobytes("png"), language=language)
