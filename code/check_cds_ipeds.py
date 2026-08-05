# /// script
# requires-python = ">=3.11"
# ///
"""Cross-check CDS-extracted counts against IPEDS for the same school × year ×
race category. Both sources are supposed to report the same underlying
enrollment, so large disagreements almost always mean an extraction bug in
one of them (usually CDS, since the PDFs vary by school and year while IPEDS
is a single homogeneous source).

We discovered this is necessary after Northwestern 2020 showed 483 Black
first-time first-year students in CDS (25.4%) vs. 113 in IPEDS (5.9%); the
CDS value was an extraction error from the 2020-21 PDF that survived into
clean.csv because merge_clean.py prefers CDS over IPEDS.

Reads:
    data/processed/clean_cds.csv
    data/processed/clean_ipeds.csv

Compares both `first_time_first_year` and `undergraduates` columns for every
(school, year, category) key present in both files. Flags rows that exceed
*both* an absolute threshold (so 1-2 students in tiny categories don't
dominate) and a relative threshold.

Run:
    uv run code/check_cds_ipeds.py
    uv run code/check_cds_ipeds.py --min-abs 10 --min-rel 0.5
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CDS_PATH   = ROOT / "data" / "processed" / "clean_cds.csv"
IPEDS_PATH = ROOT / "data" / "processed" / "clean_ipeds.csv"

COLUMNS = ("first_time_first_year", "undergraduates")
KEY = ("school", "year", "category")


def load(path: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    with path.open() as f:
        return {tuple(r[k] for k in KEY): r for r in csv.DictReader(f)}


def to_int(s: str) -> int | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-abs", type=int, default=10,
                    help="minimum absolute count difference to flag (default: 10)")
    ap.add_argument("--min-rel", type=float, default=0.30,
                    help="minimum relative difference to flag (default: 0.30)")
    ap.add_argument("--limit", type=int, default=40,
                    help="show top N flagged rows (default: 40)")
    args = ap.parse_args()

    cds = load(CDS_PATH)
    ipeds = load(IPEDS_PATH)
    shared = sorted(set(cds) & set(ipeds))

    flags = []
    for key in shared:
        for col in COLUMNS:
            c = to_int(cds[key][col])
            i = to_int(ipeds[key][col])
            if c is None or i is None:
                continue
            diff = c - i
            denom = max(c, i)
            if denom == 0:
                continue
            rel = abs(diff) / denom
            if abs(diff) >= args.min_abs and rel >= args.min_rel:
                flags.append((abs(diff), rel, col, key, c, i))

    flags.sort(reverse=True)

    print(f"Compared {len(shared):,} shared (school, year, category) keys "
          f"across columns {COLUMNS}.")
    print(f"Thresholds: |diff| >= {args.min_abs} AND rel >= {args.min_rel:.0%}")
    print(f"Flagged: {len(flags):,}\n")

    if not flags:
        return

    print(f"Top {min(args.limit, len(flags))} discrepancies (largest |diff| first):\n")
    print(f"{'school':<14} {'year':<5} {'category':<55} {'col':<22} "
          f"{'cds':>7} {'ipeds':>7} {'diff':>7} {'rel':>6}")
    print("-" * 130)
    for abs_diff, rel, col, key, c, i in flags[: args.limit]:
        school, year, cat = key
        print(f"{school:<14} {year:<5} {cat:<55} {col:<22} "
              f"{c:>7} {i:>7} {c-i:>+7} {rel:>5.0%}")


if __name__ == "__main__":
    main()
