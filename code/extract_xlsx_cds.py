# /// script
# requires-python = ">=3.11"
# dependencies = ["openpyxl"]
# ///
"""Extractor for schools that publish the CDS as an Excel workbook.

Some schools (Berkeley 2025-26, Cornell 2025-26) publish the Common Data Set
only as the standard CDS Excel template, not as a PDF, so `extract_b2.py`
never sees them. This script scans every `data/downloads/<school>/*.xlsx`,
pulls the B2 (Enrollment by Racial/Ethnic Category) table from the `CDS-B`
sheet, and merges the rows into `data/scraped/<school>/b2_enrollment.csv` —
appending years that aren't already present, exactly like the MIT HTML
special-case extractor.

Run order: `extract_b2.py` first (it rewrites the per-school CSVs from PDFs),
then this script, then `build_complete.py`.

Usage:
    uv run code/extract_xlsx_cds.py
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
DOWNLOADS_DIR = ROOT / "data" / "downloads"
SCRAPED_DIR = ROOT / "data" / "scraped"

# CSV schema written by extract_b2.py — match exactly so build_complete.py
# treats this output identically.
COLUMNS = ["year", "category", "first_time_first_year",
           "undergraduates", "total_undergraduates", "source_file"]

FULL_YEAR_RE = re.compile(r"((?:19|20)\d{2})")

# First-cell labels that mark the start and end of the B2 rows inside the
# CDS-B sheet. Everything from "Nonresidents" through "TOTAL" (inclusive) is
# the table; instruction bullets above it never collide with these labels.
B2_START = "nonresident"
B2_END = re.compile(r"^total\b", re.I)


def year_from_filename(name: str) -> str:
    for m in FULL_YEAR_RE.finditer(name):
        y = int(m.group(1))
        if 1995 <= y <= 2030:
            return str(y)
    return ""


def to_count(v) -> str:
    """Workbook cells may hold ints, floats (762.0), strings, or None."""
    if v is None or v == "":
        return ""
    if isinstance(v, str):
        v = v.replace(",", "").strip()
        if not v:
            return ""
        v = float(v)
    return str(int(round(float(v))))


def extract_b2_rows(xlsx: Path) -> list[tuple[str, str, str, str]]:
    """Return (category, first_time_first_year, undergraduates,
    total_undergraduates) for each B2 row of the workbook's CDS-B sheet."""
    wb = openpyxl.load_workbook(xlsx, data_only=True, read_only=True)
    if "CDS-B" not in wb.sheetnames:
        raise ValueError(f"{xlsx.name}: no CDS-B sheet "
                         f"(sheets: {wb.sheetnames})")
    rows = list(wb["CDS-B"].iter_rows(values_only=True))
    wb.close()

    b2_at = next((i for i, r in enumerate(rows)
                  if r and str(r[0] or "").strip() == "B2"), None)
    if b2_at is None:
        raise ValueError(f"{xlsx.name}: no 'B2' marker row in CDS-B")

    out: list[tuple[str, str, str, str]] = []
    in_table = False
    for r in rows[b2_at:]:
        label = str(r[1] or "").strip() if len(r) > 1 else ""
        if not label:
            continue
        # Counts live in columns D/E/F of the standard CDS template.
        vals = [to_count(r[i]) if len(r) > i else "" for i in (3, 4, 5)]
        if not in_table:
            # The table starts at the "Nonresidents" row. Instruction bullets
            # above it ("Nonresident - A person who is not a citizen...")
            # share the prefix but carry no counts, so require a value too.
            if label.lower().startswith(B2_START) and any(vals):
                in_table = True
            else:
                continue
        if not any(vals):
            continue
        out.append((label, *vals))
        if B2_END.match(label):
            break
    if not out or not B2_END.match(out[-1][0]):
        raise ValueError(f"{xlsx.name}: B2 table not terminated by TOTAL row")
    return out


def main() -> None:
    for school_dir in sorted(d for d in DOWNLOADS_DIR.iterdir() if d.is_dir()):
        xlsxs = sorted(school_dir.glob("*.xlsx"))
        if not xlsxs:
            continue
        school = school_dir.name
        csv_path = SCRAPED_DIR / school / "b2_enrollment.csv"
        existing: list[dict] = []
        existing_years: set[str] = set()
        if csv_path.exists():
            with csv_path.open() as f:
                existing = list(csv.DictReader(f))
            existing_years = {r["year"] for r in existing}

        added = []
        for xlsx in xlsxs:
            year = year_from_filename(xlsx.name)
            if not year:
                print(f"  {school}/{xlsx.name}: no year in filename, skipped")
                continue
            if year in existing_years:
                print(f"  {school} {year}: already in CSV, skipping")
                continue
            try:
                b2 = extract_b2_rows(xlsx)
            except ValueError as e:
                print(f"  {school}/{xlsx.name}: skipped ({e})")
                continue
            for cat, ftfy, ug, total in b2:
                added.append({
                    "year": year, "category": cat,
                    "first_time_first_year": ftfy, "undergraduates": ug,
                    "total_undergraduates": total, "source_file": xlsx.name,
                })
            print(f"  {school} {year}: extracted from {xlsx.name}")

        if not added:
            continue
        combined = existing + added
        combined.sort(key=lambda r: int(r["year"]))
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS)
            w.writeheader()
            w.writerows(combined)
        print(f"{school}: wrote {len(combined)} rows "
              f"({len(added)} new) to {csv_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
