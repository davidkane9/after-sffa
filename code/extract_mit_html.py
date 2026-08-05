# /// script
# requires-python = ">=3.11"
# ///
"""Special-case extractor for MIT.

MIT publishes the Common Data Set as HTML pages on `ir.mit.edu`, not as PDFs,
so the regular pdfplumber-based extractor in `code/extract_b2.py` only sees
the single 1999-2000 PDF that lives under `data/downloads/mit/`.

This script fetches the B2 (Enrollment by Racial/Ethnic Category) table from
each of MIT's published HTML CDS pages, parses it, and merges the rows into
`data/scraped/mit/b2_enrollment.csv` — appending years that aren't already
present (the 1999 row from the PDF is preserved).

Run order: `extract_b2.py` first (writes per-school CSVs), then this script,
then `build_complete.py`.

Usage:
    uv run code/extract_mit_html.py
"""

from __future__ import annotations

import csv
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIT_CSV = ROOT / "data" / "scraped" / "mit" / "b2_enrollment.csv"

# MIT CDS pages that have ever existed (probed in 2026-04). Years correspond
# to the academic-year *start* (e.g. 2024 = 2024-25). The script will skip
# any URL that 404s, so adding a future year here is safe.
MIT_YEARS = {
    2021: "https://ir.mit.edu/projects/2021-22-common-data-set/",
    2022: "https://ir.mit.edu/projects/2022-23-common-data-set/",
    2023: "https://ir.mit.edu/projects/2023-24-common-data-set/",
    2024: "https://ir.mit.edu/projects/2024-25-common-data-set/",
    2025: "https://ir.mit.edu/projects/2025-26-common-data-set/",
}

# CSV schema written by extract_b2.py — match exactly so build_complete.py
# treats this output identically.
COLUMNS = ["year", "category", "first_time_first_year",
           "undergraduates", "total_undergraduates", "source_file"]

# Match every B2 row inside the page's <tbody>. The B2 table on MIT's pages
# is a <table> with rows shaped like:
#
#   <tr class="row-N">
#     <td class="column-1"><strong>Black or African American, non-Hispanic</strong></td>
#     <td class="column-2">41</td>
#     <td class="column-3">349</td>
#     <td class="column-4">349</td>
#   </tr>
#
# Some labels lack the <strong> wrapper; the second alternation handles those.
ROW_RE = re.compile(
    r'<tr[^>]*>\s*'
    r'<td[^>]*class="column-1"[^>]*>\s*(?:<strong>)?([^<]+?)(?:</strong>)?\s*</td>\s*'
    r'<td[^>]*class="column-2"[^>]*>\s*([^<]*)\s*</td>\s*'
    r'<td[^>]*class="column-3"[^>]*>\s*([^<]*)\s*</td>\s*'
    r'<td[^>]*class="column-4"[^>]*>\s*([^<]*)\s*</td>\s*'
    r'</tr>',
    re.IGNORECASE | re.DOTALL,
)

B2_LABELS = {
    "Nonresidents", "Nonresident aliens",
    "Hispanic", "Hispanic/Latino",
    "Black or African American, non-Hispanic",
    "White, non-Hispanic",
    "American Indian or Alaska Native, non-Hispanic",
    "Asian, non-Hispanic",
    "Native Hawaiian or other Pacific Islander, non-Hispanic",
    "Two or more races, non-Hispanic",
    "Race and/or ethnicity unknown",
    "Total",
}


def fetch_html(url: str) -> str | None:
    """GET the URL with browser-like headers; return text or None on failure."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  ! fetch error for {url}: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def clean_num(s: str) -> str:
    """Strip whitespace, HTML entities, and thousands separators."""
    s = re.sub(r"&[a-z]+;|&#\d+;", "", s)
    return re.sub(r"[\s,]", "", s).strip()


def clean_label(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"&amp;", "&", s)
    s = re.sub(r"&[a-z]+;|&#\d+;", "", s)
    return s.strip()


def parse_b2(html: str) -> list[tuple[str, str, str, str]]:
    """Extract (label, first_year, undergrads, total_undergrads) for each B2 row.

    The MIT pages contain a B2 table for undergraduate enrollment followed by
    a similarly-structured table for graduate enrollment. We want only the
    first one — stop after the first "Total" row, and dedupe by label."""
    rows = []
    seen: set[str] = set()
    for m in ROW_RE.finditer(html):
        label = clean_label(m.group(1))
        if label not in B2_LABELS:
            continue
        if label in seen:
            continue
        seen.add(label)
        rows.append((
            label,
            clean_num(m.group(2)),
            clean_num(m.group(3)),
            clean_num(m.group(4)),
        ))
        if label == "Total":
            break
    return rows


def main() -> None:
    # Read existing rows so we preserve the 1999 PDF-derived row and any
    # other years that might already be there.
    existing = []
    existing_years: set[int] = set()
    if MIT_CSV.exists():
        with MIT_CSV.open() as f:
            reader = csv.DictReader(f)
            for r in reader:
                existing.append(r)
                try:
                    existing_years.add(int(r["year"]))
                except (ValueError, TypeError):
                    pass

    print(f"Existing MIT rows: {len(existing)} (years: {sorted(existing_years)})")

    new_rows = []
    for year, url in sorted(MIT_YEARS.items()):
        if year in existing_years:
            print(f"  {year}-{(year + 1) % 100:02d}: already in CSV, skipping")
            continue
        html = fetch_html(url)
        if not html:
            continue
        b2 = parse_b2(html)
        if len(b2) < 8:
            print(f"  ! {url}: only {len(b2)} B2 rows found, skipping")
            continue
        source = url.rstrip("/").rsplit("/", 1)[-1] + ".html"
        for label, c1, c2, c3 in b2:
            new_rows.append({
                "year": str(year),
                "category": label,
                "first_time_first_year": c1,
                "undergraduates": c2,
                "total_undergraduates": c3,
                "source_file": source,
            })
        print(f"  {year}-{(year + 1) % 100:02d}: extracted {len(b2)} rows from {url}")

    if not new_rows:
        print("No new rows added.")
        return

    # Sort by (year, category-position) and write back.
    label_order = list(B2_LABELS)  # set iteration is fine — used only as fallback
    canonical_order = [
        "Nonresident aliens", "Nonresidents",
        "Hispanic/Latino", "Hispanic",
        "Black or African American, non-Hispanic",
        "White, non-Hispanic",
        "American Indian or Alaska Native, non-Hispanic",
        "Asian, non-Hispanic",
        "Native Hawaiian or other Pacific Islander, non-Hispanic",
        "Two or more races, non-Hispanic",
        "Race and/or ethnicity unknown",
        "Total",
    ]

    def cat_rank(c: str) -> int:
        try:
            return canonical_order.index(c)
        except ValueError:
            return 999

    combined = list(existing) + new_rows
    combined.sort(key=lambda r: (int(r["year"]), cat_rank(r["category"])))

    MIT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with MIT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        # Preserve any extra columns from existing rows by passing only
        # the schema we care about — DictWriter ignores extras silently.
        for r in combined:
            writer.writerow({c: r.get(c, "") for c in COLUMNS})

    print(f"\nWrote {len(combined)} total rows ({len(new_rows)} new) to "
          f"{MIT_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
