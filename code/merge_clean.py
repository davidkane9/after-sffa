# /// script
# requires-python = ">=3.11"
# ///
"""Merge data/processed/clean_cds.csv + clean_ipeds.csv → clean.csv.

Both inputs are already normalized to the same canonical 10-category vocabulary
and identical column schema. The merge is IPEDS-preferred:

  - For each (school, year), if clean_ipeds.csv has any row for that
    (school, year), use the entire IPEDS block (all categories present
    there). IPEDS is a single homogeneous federal source with one extractor;
    CDS is one PDF parser per school × year and silently drops or misaligns
    cells in some PDFs (see code/check_cds_ipeds.py).
  - Otherwise, fall back to clean_cds.csv for that (school, year). This is
    the only source for years IPEDS doesn't cover (1998-2007, and the most
    recent year before IPEDS releases its Fall file).

Why this granularity (whole school-year, not individual category)? A CDS or
IPEDS table is published as a unit and is internally consistent. Mixing rows
for some categories from one source with rows for others within the same
(school, year) could produce a Frankentable that doesn't sum to the published
Total. Whole-block preference avoids that.

The CDS values, where they exist for an IPEDS-preferred row, are preserved
as auxiliary columns `cds_first_time_first_year` and `cds_undergraduates` so
analyses can still cross-check or use the CDS number explicitly. These are
empty for school-years where only one source exists.

A `source` column ('cds' or 'ipeds') indicates which source supplied the
primary `first_time_first_year` / `undergraduates` values on each row.
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
CDS = PROC / "clean_cds.csv"
IPEDS = PROC / "clean_ipeds.csv"
OUT = PROC / "clean.csv"


def load(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"missing input: {path}")
    with path.open() as f:
        return list(csv.DictReader(f))


def main() -> None:
    cds_rows = load(CDS)
    ipeds_rows = load(IPEDS)

    ipeds_keys = {(r["school"], r["year"]) for r in ipeds_rows}
    cds_by_cat = {(r["school"], r["year"], r["category"]): r for r in cds_rows}

    merged: list[dict] = []

    for r in ipeds_rows:
        out = dict(r)
        out["source"] = "ipeds"
        cds_row = cds_by_cat.get((r["school"], r["year"], r["category"]))
        out["cds_first_time_first_year"] = (
            cds_row["first_time_first_year"] if cds_row else "")
        out["cds_undergraduates"] = (
            cds_row["undergraduates"] if cds_row else "")
        merged.append(out)

    cds_only_added = 0
    for r in cds_rows:
        if (r["school"], r["year"]) in ipeds_keys:
            continue
        out = dict(r)
        out["source"] = "cds"
        out["cds_first_time_first_year"] = ""
        out["cds_undergraduates"] = ""
        merged.append(out)
        cds_only_added += 1

    fieldnames = (list(ipeds_rows[0].keys())
                  + ["cds_first_time_first_year", "cds_undergraduates",
                     "source"])
    merged.sort(key=lambda r: (int(r["year"]), r["school"], r["category"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged)

    ipeds_school_years = len(ipeds_keys)
    cds_school_years = len({(r["school"], r["year"]) for r in merged
                            if r["source"] == "cds"})
    aux_filled = sum(1 for r in merged
                     if r["source"] == "ipeds"
                     and r["cds_first_time_first_year"])
    print(f"Wrote {len(merged)} rows to {OUT.relative_to(ROOT)}")
    print(f"  IPEDS: {len(ipeds_rows):>6} rows, "
          f"{ipeds_school_years} school-years")
    print(f"  CDS:   {cds_only_added:>6} rows added "
          f"({cds_school_years} school-years that IPEDS doesn't cover)")
    print(f"  CDS aux columns populated on {aux_filled} IPEDS rows "
          f"(both sources had this category)")


if __name__ == "__main__":
    main()
