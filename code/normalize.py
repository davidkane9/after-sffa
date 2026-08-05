# /// script
# requires-python = ">=3.11"
# ///
"""Normalize data/processed/raw_cds.csv → data/processed/clean_cds.csv.

`data/processed/raw_cds.csv` faithfully reproduces what the PDFs say. This
script bakes in the cleanup passes a downstream analysis needs:

  1. Drop AcroForm-empty rows. Some 2024-25/2025-26 fillable PDFs have
     categories listed in the table but with all three numeric cells empty.
     Those rows have no analytical value; drop them.
  2. Williams revision dedup is already handled by build_complete.py and is
     idempotent here — we don't apply it again.
  3. Princeton 2020-21 reassignment is handled upstream in build_complete.py
     (so the row survives the revision-dedup that happens there). It's left
     here as a no-op safety net.
  4. Normalize category strings to a canonical 10-category vocabulary
     (matching the post-2010 IPEDS schema). Pre-2010's "Asian or Pacific
     Islander" combined line is mapped to "Asian, non-Hispanic" with a
     `legacy_combined` flag column added so analyses can choose how to
     handle the schema break.
  5. Strip Middlebury 2014–2020's polluted category labels of their
     embedded percentages. The trailing 3 numeric columns are still correct.

Run order (after extract_b2.py, extract_mit_html.py, build_complete.py):

    uv run code/normalize.py

Output: data/processed/clean_cds.csv with the same columns as raw_cds.csv,
plus a `legacy_combined` int (0 or 1) flagging pre-2010 "Asian or Pacific
Islander" rows.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "processed" / "raw_cds.csv"
OUT = ROOT / "data" / "processed" / "clean_cds.csv"


# Canonical 10-category vocabulary (post-2010 IPEDS).
CANONICAL = [
    "Nonresident",
    "Hispanic/Latino",
    "Black or African American, non-Hispanic",
    "White, non-Hispanic",
    "American Indian or Alaska Native, non-Hispanic",
    "Asian, non-Hispanic",
    "Native Hawaiian or other Pacific Islander, non-Hispanic",
    "Two or more races, non-Hispanic",
    "Race and/or ethnicity unknown",
    "Total",
]


def normalize_category(raw: str) -> tuple[str, int] | None:
    """Map a raw category string to (canonical_label, legacy_combined_flag).

    Returns None for rows that don't represent any of the 10 canonical CDS B2
    categories (e.g. "Bachelor's degrees Postbachelor's certificates ..." junk
    that crept in from non-B2 tables).

    `legacy_combined` is 1 only when the source category is the pre-2010
    combined "Asian or Pacific Islander" line, which we map to "Asian,
    non-Hispanic" but flag so analyses can exclude or relabel it.
    """
    if not raw:
        return None

    # Strip Middlebury's embedded-percentage pollution: "B2 Nonresident aliens
    # 11.7% 10.0% 10.7%" → "Nonresident aliens". Also drops generic "B2 "
    # prefixes and Williams-style "B211 ", "B221 " prefixes.
    s = raw.strip().strip('"')
    s = re.sub(r"^B\d{1,4}\s*", "", s)
    s = re.sub(r"\s+\d+(?:\.\d+)?%(?:\s+\d+(?:\.\d+)?%)*\s*$", "", s)

    # Strip a bunch of trailing IPEDS column-numbers tags ("IPEDS cols. 5-6",
    # "1999 IPEDS cols. 1-2") and any "Enrollment Enrollment ..." breadcrumbs
    # that crept in from Carleton-style listings.
    s = re.sub(r"\s+(?:1999\s+)?IPEDS\s+cols?\.\s*[\d\-]+\s*$", "", s, flags=re.I)
    s = re.sub(r"\s+Enrollment\s+.*$", "", s, flags=re.I)

    s_low = s.lower()

    # Reject obvious garbage from non-B2 tables (graduate enrollment tables,
    # degree-conferral tables, instruction blurbs, etc.). The B2 categories
    # only describe undergraduates; any row mentioning "graduate" or
    # "all students" is the wrong table.
    if any(bad in s_low for bad in (
        "bachelor", "postbachelor", "master's", "doctoral",
        "graduate", "all students",  # broader rejection for grad rows
        "all other degree",
        "credit courses", "first-time first-year students",
        "official fall reporting", "racial/ethnic destinations",
    )):
        return None

    # Now classify.
    # Order matters: more-specific patterns first.
    # The canonical "Total" row is the bare-word "Total" / "TOTAL" / "Total\b"
    # plus the variant "Total all undergraduates". We must NOT match
    # "Total Hispanic", "Total Graduate", etc. — those are sub-totals that
    # would fail the rejection list above if they referenced grad/degree
    # categories.
    if re.fullmatch(r"\s*total\s*\d*\s*", s_low) \
       or re.fullmatch(r"\s*total\s+(?:all\s+)?undergraduates?\s*", s_low):
        return ("Total", 0)
    if "unknown" in s_low and ("race" in s_low or "ethnic" in s_low):
        return ("Race and/or ethnicity unknown", 0)
    # Yale's 2025-26 PDF labels the row just "Unknown".
    if re.fullmatch(r"\s*unknown\s*", s_low):
        return ("Race and/or ethnicity unknown", 0)
    if "two or more" in s_low or "multi-?rac" in s_low or s_low.startswith("bi/multi"):
        return ("Two or more races, non-Hispanic", 0)
    if "hawaiian" in s_low or "pacific islander" in s_low:
        # The combined pre-2010 "Asian or Pacific Islander" line goes to
        # Asian (with legacy_combined=1), not here. So this branch only
        # matches the standalone post-2010 Pacific Islander row.
        if "asian" in s_low:
            return ("Asian, non-Hispanic", 1)
        return ("Native Hawaiian or other Pacific Islander, non-Hispanic", 0)
    if "asian" in s_low:
        # "Asian or Pacific Islander" pre-2010 → flag legacy.
        legacy = 1 if "pacific" in s_low else 0
        return ("Asian, non-Hispanic", legacy)
    if "american indian" in s_low or "alaska" in s_low:
        return ("American Indian or Alaska Native, non-Hispanic", 0)
    if re.search(r"\bblack\b|african\s*american|^\s*african", s_low):
        return ("Black or African American, non-Hispanic", 0)
    if re.search(r"^white\b|\bwhite,?\s*non", s_low):
        return ("White, non-Hispanic", 0)
    if "hispanic" in s_low or "latin" in s_low:
        return ("Hispanic/Latino", 0)
    if (re.search(r"\bnonresident", s_low) or "non-resident" in s_low or
            s_low.startswith("non- resident") or s_low.startswith("non-­resident") or
            s_low.startswith("international")):
        return ("Nonresident", 0)

    return None


def is_all_empty(r: dict) -> bool:
    """True if all three numeric columns are blank or '0' would still be a
    valid datum. We keep '0' (real zero counts); we drop only truly-blank rows."""
    return all(not (r.get(c) or "").strip()
               for c in ("first_time_first_year", "undergraduates",
                         "total_undergraduates"))


# Princeton 2021 reassignment: this filename actually reports 2020-21.
PRINCETON_2020_FILE = "cds_2021_princeton.pdf"


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing source: {SRC}. Run build_complete.py first.")

    rows_in = list(csv.DictReader(SRC.open()))

    out_rows = []
    counts = {
        "input": len(rows_in),
        "dropped_empty": 0,
        "princeton_reassigned": 0,
        "dropped_uncategorizable": 0,
        "legacy_combined": 0,
        "dropped_dup_category": 0,
    }
    # Track first-occurrence per (school, year, canonical_category) so we can
    # deduplicate multi-cell-layout PDFs like Barnard 2024 where pdfplumber
    # reads the table's three columns as three separate rows of every
    # category, all written into the first_time_first_year column.
    seen_keys: set[tuple[str, int, str]] = set()

    for r in rows_in:
        # Pass 1: drop AcroForm-empty rows.
        if is_all_empty(r):
            counts["dropped_empty"] += 1
            continue

        # Pass 3: Princeton 2021 → 2020 reassignment.
        if r.get("school") == "princeton" and r.get("source_file") == PRINCETON_2020_FILE:
            r = dict(r)
            r["year"] = "2020"
            counts["princeton_reassigned"] += 1

        # Pass 5 + Pass 4: clean up category, normalize.
        norm = normalize_category(r.get("category", ""))
        if norm is None:
            counts["dropped_uncategorizable"] += 1
            continue
        canonical, legacy = norm
        if legacy:
            counts["legacy_combined"] += 1

        # Pass 6 (in-house): drop duplicate (school, year, category) rows
        # caused by multi-cell-layout PDFs. Keep the first occurrence; the
        # extractor processes year sections in order so the first set is the
        # first-year column (the one we want).
        try:
            yr_int = int(r["year"])
        except (ValueError, TypeError):
            yr_int = -1
        key = (r["school"], yr_int, canonical)
        if key in seen_keys:
            counts["dropped_dup_category"] += 1
            continue
        seen_keys.add(key)

        out = dict(r)
        out["category"] = canonical
        out["legacy_combined"] = str(legacy)
        out_rows.append(out)

    # Sort: year, school, canonical-category-order, then source_file as tiebreak.
    cat_rank = {c: i for i, c in enumerate(CANONICAL)}
    out_rows.sort(key=lambda r: (
        int(r["year"]),
        r["school"],
        cat_rank.get(r["category"], 999),
        r.get("source_file", ""),
    ))

    fieldnames = list(rows_in[0].keys()) + ["legacy_combined"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"Wrote {len(out_rows)} rows to {OUT.relative_to(ROOT)}")
    for k, v in counts.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
