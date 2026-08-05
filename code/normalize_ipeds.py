# /// script
# requires-python = ">=3.11"
# ///
"""Normalize data/processed/raw_ipeds.csv → data/processed/clean_ipeds.csv.

`raw_ipeds.csv` has every institution IPEDS reports (~6000/year) in long form,
keyed by UNITID + INSTNM. This script narrows that to the 66 schools we
track and reshapes the columns to match `clean_cds.csv` so the two are
directly diffable and mergable:

  - filter rows to UNITIDs in code/extract_ipeds.py:UNITID
  - replace `unitid` + `instnm` columns with our `school` slug
  - attach the same five group-membership flags carried by clean_cds.csv
    (ivy, ivy.plus, nescac, SFFA.brief, us.news)
  - add a `legacy_combined` column (always 0; IPEDS uses post-2010 schema
    natively, and the pre-2010 EF tables already split out a single
    "Asian" line for our purposes — there's no IPEDS-internal merging to
    flag)

Output schema matches clean_cds.csv exactly.
"""

from __future__ import annotations

import csv
from pathlib import Path

# Reuse the canonical group definitions from build_complete.py so the two
# clean_*.csv files stay in lockstep.
from build_complete import IVY, IVY_PLUS, NESCAC, SFFA_BRIEF, US_NEWS
from extract_ipeds import UNITID

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "processed" / "raw_ipeds.csv"
OUT = ROOT / "data" / "processed" / "clean_ipeds.csv"

SCHOOL_BY_UNITID = {uid: code for code, uid in UNITID.items()}


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing source: {SRC}. Run extract_ipeds.py first.")

    out_rows: list[dict] = []
    with SRC.open() as f:
        for r in csv.DictReader(f):
            try:
                uid = int(r["unitid"])
            except (ValueError, TypeError, KeyError):
                continue
            school = SCHOOL_BY_UNITID.get(uid)
            if school is None:
                continue
            out_rows.append({
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
                "legacy_combined": "0",
            })

    out_rows.sort(key=lambda r: (int(r["year"]), r["school"], r["category"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "year", "school", "ivy", "ivy.plus", "nescac", "SFFA.brief",
            "us.news", "category",
            "first_time_first_year", "undergraduates", "total_undergraduates",
            "source_file", "legacy_combined",
        ])
        writer.writeheader()
        writer.writerows(out_rows)

    schools_seen = sorted({r["school"] for r in out_rows})
    years_seen = sorted({int(r["year"]) for r in out_rows})
    print(f"Wrote {len(out_rows)} rows to {OUT.relative_to(ROOT)}")
    print(f"  schools: {len(schools_seen)} of {len(UNITID)}")
    print(f"  years:   {min(years_seen)}–{max(years_seen)}")


if __name__ == "__main__":
    main()
