# /// script
# requires-python = ">=3.11"
# ///
"""Hand-transcribed B2 tables for filings no automated extractor can read.

Union's 2025-26 CDS PDF has a text layer whose font encoding produces
garbage from pdfplumber/pdftotext, so `extract_b2.py` cannot parse it.
The B2 values below were transcribed from a visual read of page 6 of
`data/downloads/union/union-cds-2025-2026.pdf` and double-checked against
an independent read of the same page.

Like `extract_mit_html.py` and `extract_xlsx_cds.py`, this script merges
its rows into `data/scraped/<school>/b2_enrollment.csv`, appending only
years not already present. Run it after `extract_b2.py` (which rewrites
the per-school CSVs from PDFs) so the manual rows survive a full rebuild.

Usage:
    uv run code/extract_manual.py
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRAPED_DIR = ROOT / "data" / "scraped"

COLUMNS = ["year", "category", "first_time_first_year",
           "undergraduates", "total_undergraduates", "source_file"]

# (school, year, source_file) -> rows of
# (category, first_time_first_year, undergraduates, total_undergraduates)
MANUAL: dict[tuple[str, str, str], list[tuple[str, str, str, str]]] = {
    ("union", "2025", "union-cds-2025-2026.pdf"): [
        ("Nonresidents", "28", "186", "187"),
        ("Hispanic/Latino", "64", "223", "224"),
        ("Black or African American, non-Hispanic", "50", "119", "119"),
        ("White, non-Hispanic", "262", "1164", "1167"),
        ("American Indian or Alaska Native, non-Hispanic", "0", "0", "0"),
        ("Asian, non-Hispanic", "34", "150", "152"),
        ("Native Hawaiian or other Pacific Islander, non-Hispanic",
         "0", "2", "2"),
        ("Two or more races, non-Hispanic", "27", "87", "87"),
        ("Race and/or ethnicity unknown", "0", "2", "16"),
        ("TOTAL", "465", "1933", "1954"),
    ],
}


def main() -> None:
    for (school, year, source), rows in MANUAL.items():
        csv_path = SCRAPED_DIR / school / "b2_enrollment.csv"
        existing: list[dict] = []
        if csv_path.exists():
            with csv_path.open() as f:
                existing = list(csv.DictReader(f))
        if any(r["year"] == year for r in existing):
            print(f"  {school} {year}: already in CSV, skipping")
            continue
        for cat, ftfy, ug, total in rows:
            existing.append({
                "year": year, "category": cat,
                "first_time_first_year": ftfy, "undergraduates": ug,
                "total_undergraduates": total, "source_file": source,
            })
        existing.sort(key=lambda r: int(r["year"]))
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS)
            w.writeheader()
            w.writerows(existing)
        print(f"{school}: added {len(rows)} manual rows for {year} "
              f"to {csv_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
