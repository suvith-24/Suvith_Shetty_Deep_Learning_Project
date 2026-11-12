"""Generate the synthetic demo amendment used to show conflicts, tables and OCR.

    python scripts/make_demo_documents.py

Writes data/demo/lexisync_sample_amendment.pdf. It is clearly labelled as
synthetic and amends the (also synthetic) sample act in
data/raw/lexisync_sample_legal_document.pdf:

* page 1: changed retention period (seven vs five years) and incident
  notification deadline (forty-eight vs seventy-two hours) -> conflict detection
* page 2: a ruled retention schedule with a spanning header -> table extraction
* page 3: an image-only (scanned) annex -> scanned-page detection + OCR
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "demo" / "lexisync_sample_amendment.pdf"

BANNER = "LexiSyncAI synthetic test document - not a real law"


def _text(page, y: float, text: str, size: float = 10.5, bold: bool = False) -> float:
    font = "hebo" if bold else "helv"
    rect = pymupdf.Rect(56, y, page.rect.width - 56, y + 400)
    used = page.insert_textbox(rect, text, fontsize=size, fontname=font)
    lines = max(1, int(round((400 - used) / (size * 1.25))))
    return y + lines * size * 1.25 + 8


def page_one(doc) -> None:
    page = doc.new_page()
    page.insert_text((56, 40), BANNER, fontsize=8)
    y = 70
    y = _text(page, y, "AMENDMENT No. 1 TO THE SAMPLE DATA PROTECTION AND RECORDS ACT", 13, True)
    y = _text(page, y, "Synthetic amendment for LexiSyncAI conflict, table and OCR testing. Not legal advice.", 9)
    y = _text(page, y, "ARTICLE 1 - AMENDMENT OF RETENTION AND DELETION", 11, True)
    y = _text(page, y, "1.1 Standard retention period. Unless a longer period is required by a documented statutory duty, "
                      "an active service record shall be retained for no longer than seven years after the relevant "
                      "service relationship ends.")
    y = _text(page, y, "1.2 This Article replaces Article 3.1 of the Sample Data Protection and Records Act.")
    y = _text(page, y, "ARTICLE 2 - AMENDMENT OF SECURITY INCIDENT NOTIFICATION", 11, True)
    y = _text(page, y, "2.1 External notification. Where an incident is likely to affect individuals, the Authority shall "
                      "notify the fictional Independent Data Office within forty-eight hours after the Authority becomes "
                      "aware of the incident.")
    y = _text(page, y, "ARTICLE 3 - COMMENCEMENT", 11, True)
    _text(page, y, "3.1 Commencement. This amendment takes effect on 1 July 2026.")


def page_two(doc) -> None:
    page = doc.new_page()
    page.insert_text((56, 40), BANNER, fontsize=8)
    y = _text(page, 70, "SCHEDULE 1 - RETENTION SCHEDULE", 12, True)
    rows = [
        ["Record type", "Retention period", "Retention period"],
        ["", "Active", "Archived"],
        ["Service record", "7 years", "2 years"],
        ["Payroll record", "10 years", "None"],
        ["Access log", "12 months", "6 months"],
        ["Complaint file", "3 years", "1 year"],
    ]
    x = [56, 236, 386, 536]
    top = y + 10
    height = 24
    for r, row in enumerate(rows):
        y0 = top + r * height
        for c, value in enumerate(row):
            if r == 0 and c == 2:
                continue  # spanning header "Retention period" covers columns 2-3
            if value:
                page.insert_text((x[c] + 6, y0 + 16), value, fontsize=10, fontname="hebo" if r < 2 else "helv")
    bottom = top + len(rows) * height
    shape = page.new_shape()
    for r in range(len(rows) + 1):
        y_line = top + r * height
        x_start = x[1] if r == 1 else x[0]
        shape.draw_line((x_start, y_line), (x[-1], y_line))
    for c, x_line in enumerate(x):
        y_start = top + height if c == 2 else top
        shape.draw_line((x_line, y_start), (x_line, bottom))
    shape.finish(width=0.8, color=(0, 0, 0))
    shape.commit()
    _text(page, bottom + 20, "Note: the retention periods in this Schedule apply from the commencement date in Article 3.")


def page_three(doc) -> None:
    source = pymupdf.open()
    src_page = source.new_page()
    y = _text(src_page, 70, "ANNEX - CONTACT POINTS (SCANNED COPY)", 13, True)
    y = _text(src_page, y, "The Data Governance Officer is the contact point for requests under this amendment.", 12)
    y = _text(src_page, y, "Requests may be submitted in writing to the Records Office, which shall forward them "
                          "within two working days.", 12)
    pixmap = src_page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
    page = doc.new_page()
    page.insert_image(page.rect, stream=pixmap.tobytes("png"))
    source.close()


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open()
    page_one(doc)
    page_two(doc)
    page_three(doc)
    doc.set_metadata({"title": "Amendment No. 1 (synthetic)", "author": "LexiSyncAI test fixtures",
                      "creationDate": "D:20260301000000"})
    doc.save(OUTPUT)
    doc.close()
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
