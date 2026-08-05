# /// script
# requires-python = ">=3.11"
# ///
"""Combine every per-school B2 CSV into one long-format file at
data/processed/raw_cds.csv, with school, year, and four boolean
group-membership columns (ivy, ivy.plus, nescac, SFFA.brief). Rows ordered
by year, then school.

When a school publishes multiple revisions of the same year's CDS (Williams,
Vassar, etc.), only the "winning" revision contributes rows. The winner is
chosen per (school, year) by `revision_score` below.

Output is "raw" in the sense that category strings come straight from the PDFs
and may include garbage rows from non-B2 tables. Use code/normalize.py to
produce data/processed/clean_cds.csv with canonical category names and the 5
cleanup passes applied.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRAPED = ROOT / "data" / "scraped"
OUT = ROOT / "data" / "processed" / "raw_cds.csv"

IVY = {"brown", "columbia", "cornell", "dartmouth",
       "harvard", "penn", "princeton", "yale"}

# "Ivy Plus" per the user: the Ivies plus Duke, MIT, Stanford, Caltech,
# Johns Hopkins, and the University of Chicago.
IVY_PLUS = IVY | {"duke", "mit", "stanford", "caltech", "jhu", "uchicago"}

NESCAC = {"amherst", "bates", "bowdoin", "colby", "conncoll", "hamilton",
          "middlebury", "trinity", "tufts", "wesleyan", "williams"}

# 33 schools that signed the Amherst-led amicus brief in SFFA v. Harvard
# (Brief of Amherst, Barnard, Bates, ..., Williams Colleges, and Bucknell,
# Clark, Tufts, Washington & Lee, and Wesleyan Universities, Aug. 1, 2022).
SFFA_BRIEF = {
    # 28 colleges
    "amherst", "barnard", "bates", "bowdoin", "brynmawr", "carleton",
    "colby", "conncoll", "davidson", "fandm", "hamilton", "hampshire",
    "haverford", "macalester", "middlebury", "mtholyoke", "oberlin",
    "pomona", "reed", "sarahlawrence", "smith", "stolaf", "swarthmore",
    "trinity", "union", "vassar", "wellesley", "williams",
    # 5 universities
    "bucknell", "clark", "tufts", "washandlee", "wesleyan",
}
assert len(SFFA_BRIEF) == 33

# 50 schools in the top 25 of the *2026* US News Best National Universities OR
# Best National Liberal Arts Colleges rankings (released September 2025).
# Top-25 ties produce a few more than 25 per list, but the two lists don't
# overlap (a school is classified as one or the other), so the union is
# exactly 50.
US_NEWS = {
    # Top 25 National Universities
    "princeton", "mit", "harvard", "stanford", "yale", "uchicago",
    "duke", "jhu", "northwestern", "penn", "caltech", "cornell",
    "brown", "dartmouth", "columbia", "berkeley", "rice", "ucla",
    "vanderbilt", "cmu", "umich", "notredame", "wustl", "emory",
    "georgetown",
    # Top 25 National Liberal Arts Colleges
    "williams", "amherst", "navy", "swarthmore", "bowdoin", "airforce",
    "cmc", "pomona", "wellesley", "carleton", "hmc", "army",
    "barnard", "davidson", "grinnell", "hamilton", "middlebury",
    "smith", "vassar", "wesleyan", "washandlee", "colgate", "richmond",
    "bates", "colby",
}
assert len(US_NEWS) == 50


# Tie-break order for picking the winning revision when a school publishes
# multiple CDS PDFs for the same year. Higher tuples win.
MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def revision_score(filename: str) -> tuple:
    """Higher score wins when comparing two revisions of the same year.

    Priority order:
      1. Filename contains 'FINAL' (case-insensitive)
      2. Highest version number from a `[_-][vV]?<n>` segment (V5 > V1; -2 > -1)
      3. Latest month name embedded in the filename (June > March > January)
      4. Last alphabetically (stable tiebreak)
    """
    upper = filename.upper()
    final = 1 if "FINAL" in upper else 0

    # Pull every numeric token preceded by _ or - (and optionally V/v).
    # Examples: "_V5", "-V1", "_2", "-1". Skip 4-digit run-ins that look like
    # academic years (e.g. "2024" in CDS_2023_2024 isn't a revision number).
    versions = []
    for m in re.finditer(r"[_-]([vV]?)(\d+)", filename):
        marker, num = m.group(1), int(m.group(2))
        # If preceded by V/v, always count it. Otherwise, ignore 4-digit
        # year-like runs unless the file has an explicit V-marked segment too.
        if marker:
            versions.append(num)
        elif len(m.group(2)) <= 2:  # short numbers like _1, -2
            versions.append(num)
    version = max(versions) if versions else 0

    # Latest month name found in the filename.
    month = 0
    low = filename.lower()
    for tok in re.findall(r"[a-z]+", low):
        if tok in MONTH_NAMES:
            month = max(month, MONTH_NAMES[tok])

    return (final, version, month, filename)


def main() -> None:
    schools = sorted(d.name for d in SCRAPED.iterdir() if d.is_dir())

    # Step 1: read every per-school PDF-derived CSV (`b2_enrollment.csv`,
    # produced by extract_b2.py / extract_mit_html.py) into a flat list with
    # source_file attached. The IPEDS-derived `ipeds.csv` files are NOT read
    # here — they flow through extract_ipeds.py → raw_ipeds.csv → clean_ipeds.csv,
    # and the PDF-vs-IPEDS merge happens later in code/merge_clean.py.
    raw = []
    has_source_col = True
    for school in schools:
        for fname in ("b2_enrollment.csv",):
            path = SCRAPED / school / fname
            if not path.exists():
                continue
            with path.open() as f:
                for r in csv.DictReader(f):
                    try:
                        year = int(r["year"])
                    except (ValueError, TypeError):
                        continue
                    source = r.get("source_file", "") or ""
                    if not source:
                        has_source_col = False
                    # Princeton's `cds_2021_princeton.pdf` actually reports the
                    # 2020-21 academic year. Without this fix the dedup picks
                    # one of two 2021 revisions and Princeton has no 2020-21
                    # row at all. Apply the reassignment before dedup so both
                    # years survive.
                    if school == "princeton" and source == "cds_2021_princeton.pdf":
                        year = 2020
                    raw.append({
                        "year": year,
                        "school": school,
                        "category": r["category"],
                        "first_time_first_year": r["first_time_first_year"],
                        "undergraduates": r["undergraduates"],
                        "total_undergraduates": r["total_undergraduates"],
                        "source_file": source,
                    })

    # Step 2: pick the winning revision per (school, year).
    # Skipped (and warned) if the per-school CSVs don't carry source_file yet.
    if has_source_col:
        winners: dict[tuple[str, int], str] = {}
        candidates: dict[tuple[str, int], set[str]] = {}
        for r in raw:
            key = (r["school"], r["year"])
            candidates.setdefault(key, set()).add(r["source_file"])
        for key, files in candidates.items():
            if len(files) == 1:
                winners[key] = next(iter(files))
            else:
                winners[key] = max(files, key=revision_score)
        before = len(raw)
        raw = [r for r in raw
               if r["source_file"] == winners[(r["school"], r["year"])]]
        dropped = before - len(raw)
        if dropped:
            print(f"  Dropped {dropped} rows from non-winning revisions "
                  f"(out of {before}; {len(set(candidates))} school-years).")
    else:
        print("  ! Per-school CSVs lack source_file column — no dedup applied.")

    # Step 3: attach group flags + sort + write raw_cds.csv.
    rows = []
    for r in raw:
        school = r["school"]
        rows.append({
            "year": r["year"],
            "school": school,
            "ivy": int(school in IVY),
            "ivy.plus": int(school in IVY_PLUS),
            "nescac": int(school in NESCAC),
            "SFFA.brief": int(school in SFFA_BRIEF),
            "us.news": int(school in US_NEWS),
            "category": r["category"],
            "first_time_first_year": r["first_time_first_year"],
            "undergraduates": r["undergraduates"],
            "total_undergraduates": r["total_undergraduates"],
            "source_file": r["source_file"],
        })

    rows.sort(key=lambda r: (r["year"], r["school"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "year", "school", "ivy", "ivy.plus", "nescac", "SFFA.brief",
            "us.news",
            "category", "first_time_first_year",
            "undergraduates", "total_undergraduates",
            "source_file",
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUT.relative_to(ROOT)}")
    print(f"  schools: {len(schools)}")
    print(f"  years:   {min(r['year'] for r in rows)}–{max(r['year'] for r in rows)}")


if __name__ == "__main__":
    main()
