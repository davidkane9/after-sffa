# /// script
# requires-python = ">=3.11"
# ///
"""Extract CDS-B2-equivalent data from IPEDS Fall Enrollment files.

IPEDS publishes the same enrollment-by-race-and-level numbers that CDS B2
collects, federally mandated and centrally archived back to 2008-09. (Earlier
years exist but use a positional EFRACE01-22 schema that we don't decode.)
This script reads each year's IPEDS Access database
(`data/downloads/IPEDS/IPEDS<YYYY>.accdb`) and writes:
  - `data/scraped/<school>/ipeds.csv` per-school files for the 66 schools
    we track (same column layout as `b2_enrollment.csv`)
  - `data/processed/raw_ipeds.csv` with EVERY institution and every year,
    long-form, for cross-checks and broader analyses

The IPEDS EF<YEAR>A table is keyed by EFALEVEL (level-of-student rollup
code), with one row per (UNITID, EFALEVEL). Race breakdowns are columns
on that row. The B2 columns map as follows:
  CDS B2 "first-time first-year"     → EFALEVEL=4
  CDS B2 "degree-seeking undergrad"  → EFALEVEL=3
  CDS B2 "total undergraduates"      → EFALEVEL=2
We additionally filter LINE=99 LSTUDY=1 to grab only the rolled-up
(all-status) row per (UNITID, EFALEVEL).

Race columns differ between the pre-2010 and post-2010 IPEDS schemas:
  Modern (2010+):        EFAIANT, EFASIAT, EFBKAAT, EFHISPT, EFWHITT,
                         EFNHPIT, EF2MORT, EFUNKNT, EFNRALT, EFTOTLT
  Legacy (2008-2009):    DVEFAIT, DVEFAPT (Asian+PI combined), DVEFBKT,
                         DVEFHST, DVEFWHT, EFUNKNT, EFNRALT, EFTOTLT
Legacy "Asian or Pacific Islander" maps to canonical "Asian, non-Hispanic"
with legacy_combined=1, matching the convention used in normalize.py for
pre-2010 CDS rows.

Usage:
    uv run code/extract_ipeds.py             # extract every cached year (2008+)
    uv run code/extract_ipeds.py 2023 2024   # only those years
    uv run code/extract_ipeds.py --download  # also download missing zips
"""

from __future__ import annotations

import csv
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IPEDS_DIR = ROOT / "data" / "downloads" / "IPEDS"
SCRAPED = ROOT / "data" / "scraped"
RAW_IPEDS_OUT = ROOT / "data" / "processed" / "raw_ipeds.csv"

# UNITID lookup for our 66 schools (from HD2024 in IPEDS_2024-25_Provisional).
UNITID = {
    "airforce": 128328, "amherst": 164465, "army": 197036, "barnard": 189097,
    "bates": 160977, "berkeley": 110635, "bowdoin": 161004, "brown": 217156,
    "brynmawr": 211273, "bucknell": 211291, "caltech": 110404, "carleton": 173258,
    "clark": 165334, "cmc": 112260, "cmu": 211440, "colby": 161086,
    "colgate": 190099, "columbia": 190150, "conncoll": 128902, "cornell": 190415,
    "dartmouth": 182670, "davidson": 198385, "duke": 198419, "emory": 139658,
    "fandm": 212577, "georgetown": 131496, "grinnell": 153384, "hamilton": 191515,
    "hampshire": 166018, "harvard": 166027, "haverford": 212911, "hmc": 115409,
    "jhu": 162928, "macalester": 173902, "middlebury": 230959, "mit": 166683,
    "mtholyoke": 166939, "navy": 164155, "northwestern": 147767, "notredame": 152080,
    "oberlin": 204501, "penn": 215062, "pomona": 121345, "princeton": 186131,
    "reed": 209922, "rice": 227757, "richmond": 233374, "sarahlawrence": 195304,
    "smith": 167835, "stanford": 243744, "stolaf": 174844, "swarthmore": 216287,
    "trinity": 130590, "tufts": 168148, "uchicago": 144050, "ucla": 110662,
    "umich": 170976, "union": 196866, "vanderbilt": 221999, "vassar": 197133,
    "washandlee": 234207, "wellesley": 168218, "wesleyan": 130697, "williams": 168342,
    "wustl": 179867, "yale": 130794,
}
# Reverse lookup
SCHOOL_BY_UNITID = {uid: code for code, uid in UNITID.items()}

# Modern (2010+) IPEDS race columns. (col, label, legacy_combined_flag).
RACE_COLS_MODERN = [
    ("EFNRALT", "Nonresident", 0),
    ("EFHISPT", "Hispanic/Latino", 0),
    ("EFBKAAT", "Black or African American, non-Hispanic", 0),
    ("EFWHITT", "White, non-Hispanic", 0),
    ("EFAIANT", "American Indian or Alaska Native, non-Hispanic", 0),
    ("EFASIAT", "Asian, non-Hispanic", 0),
    ("EFNHPIT", "Native Hawaiian or other Pacific Islander, non-Hispanic", 0),
    ("EF2MORT", "Two or more races, non-Hispanic", 0),
    ("EFUNKNT", "Race and/or ethnicity unknown", 0),
    ("EFTOTLT", "Total", 0),
]

# Pre-2010 IPEDS race columns. DVEFAPT is the combined "Asian or Pacific
# Islander" line — we map it to Asian and flag with legacy_combined=1.
RACE_COLS_LEGACY = [
    ("EFNRALT", "Nonresident", 0),
    ("DVEFHST", "Hispanic/Latino", 0),
    ("DVEFBKT", "Black or African American, non-Hispanic", 0),
    ("DVEFWHT", "White, non-Hispanic", 0),
    ("DVEFAIT", "American Indian or Alaska Native, non-Hispanic", 0),
    ("DVEFAPT", "Asian, non-Hispanic", 1),
    ("EFUNKNT", "Race and/or ethnicity unknown", 0),
    ("EFTOTLT", "Total", 0),
]


def race_cols_for_year(year: int) -> list[tuple[str, str, int]]:
    return RACE_COLS_LEGACY if year < 2010 else RACE_COLS_MODERN


# EFALEVEL → CDS B2 column name. We additionally filter LINE=99 LSTUDY=1
# so we only see the rolled-up race breakdown per (UNITID, EFALEVEL).
EFALEVEL_TO_COL = {
    4: "first_time_first_year",
    3: "undergraduates",
    2: "total_undergraduates",
}

# IPEDS years before this use EFRACE01-22 positional codes that we don't
# decode. extract_ipeds.py just skips them.
MIN_IPEDS_YEAR = 2008


def years_available() -> list[int]:
    """Years for which an IPEDS .accdb is cached locally."""
    years: list[int] = []
    for p in IPEDS_DIR.glob("IPEDS*.accdb"):
        try:
            # filename like IPEDS202425.accdb → start year 2024
            yy = int(p.name[len("IPEDS"):len("IPEDS") + 4])
            years.append(yy)
        except ValueError:
            continue
    return sorted(years)


def extract_ef_table(accdb: Path, year: int) -> dict[int, dict[tuple[int, str], int]]:
    """Run mdb-export on EF<year>A and return:
        { unitid: { (EFALEVEL, RACE_COL): count } }
    for *every* institution (not just our 66). Filters to
    EFALEVEL ∈ {2, 3, 4} (total undergrad / degree-seeking / first-time
    first-year) and the rolled-up LINE=99 LSTUDY=1 row per (UNITID, EFALEVEL).
    """
    table = f"EF{year}A"
    proc = subprocess.run(
        ["mdb-export", str(accdb), table],
        capture_output=True, text=True, check=True,
    )
    reader = csv.DictReader(proc.stdout.splitlines())
    cols = race_cols_for_year(year)
    out: dict[int, dict] = {}
    for r in reader:
        try:
            uid = int(r["UNITID"])
            efalevel = int(r["EFALEVEL"])
            line = int(r["LINE"])
            lstudy = int(r["LSTUDY"])
        except (ValueError, TypeError, KeyError):
            continue
        if efalevel not in EFALEVEL_TO_COL:
            continue
        if line != 99 or lstudy != 1:
            continue
        bucket = out.setdefault(uid, {})
        for col, _label, _legacy in cols:
            v = (r.get(col) or "").strip()
            if v == "":
                continue
            try:
                bucket[(efalevel, col)] = int(v)
            except ValueError:
                continue
    return out


def extract_hd_table(accdb: Path, year: int) -> dict[int, str]:
    """Return {unitid: institution name} from HD<year>. The HD table is the
    institutional-directory header file shipped with each year's IPEDS DB."""
    table = f"HD{year}"
    proc = subprocess.run(
        ["mdb-export", str(accdb), table],
        capture_output=True, text=True, check=True,
    )
    out: dict[int, str] = {}
    for r in csv.DictReader(proc.stdout.splitlines()):
        try:
            uid = int(r["UNITID"])
        except (ValueError, TypeError, KeyError):
            continue
        out[uid] = (r.get("INSTNM") or "").strip()
    return out


def write_school_csvs(year: int, ef: dict) -> int:
    """Write data/scraped/<school>/ipeds.csv rows for year, restricted to the
    66 schools we track in UNITID. Returns rows written."""
    cols = race_cols_for_year(year)
    written = 0
    for uid, by_key in ef.items():
        if uid not in SCHOOL_BY_UNITID:
            continue
        school = SCHOOL_BY_UNITID[uid]
        out_dir = SCRAPED / school
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "ipeds.csv"

        existing: list[dict] = []
        if out_path.exists():
            with out_path.open() as f:
                existing = [r for r in csv.DictReader(f)
                            if r.get("year") and int(r["year"]) != year]

        new_rows: list[dict] = []
        for col, label, legacy in cols:
            row = {
                "year": str(year),
                "category": label,
                "first_time_first_year": "",
                "undergraduates": "",
                "total_undergraduates": "",
                "legacy_combined": str(legacy),
                "source_file": f"IPEDS_EF{year}A",
            }
            present = False
            for efalevel, cds_col in EFALEVEL_TO_COL.items():
                v = by_key.get((efalevel, col))
                if v is not None:
                    row[cds_col] = str(v)
                    present = True
            if present:
                new_rows.append(row)

        with out_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "year", "category", "first_time_first_year",
                "undergraduates", "total_undergraduates",
                "legacy_combined", "source_file",
            ])
            writer.writeheader()
            writer.writerows(existing + new_rows)
        written += len(new_rows)
    return written


def download_missing_zips(years_wanted: list[int]) -> list[int]:
    """Download IPEDS zips for years not yet cached, and unzip the .accdb only.
    Returns the list of years now available locally."""
    base = "https://nces.ed.gov/ipeds/tablefiles/zipfiles"
    for year in years_wanted:
        accdb = IPEDS_DIR / f"IPEDS{year}{(year + 1) % 100:02d}.accdb"
        if accdb.exists():
            continue
        zip_year = f"{year}-{(year + 1) % 100:02d}"
        # Most years are "_Final"; the most recent one is "_Provisional".
        for status in ("Final", "Provisional"):
            url = f"{base}/IPEDS_{zip_year}_{status}.zip"
            zip_path = IPEDS_DIR / f"IPEDS_{zip_year}_{status}.zip"
            print(f"  fetching {url}")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    if r.status != 200:
                        continue
                    zip_path.write_bytes(r.read())
            except Exception as e:
                print(f"    {type(e).__name__}: {e}")
                continue
            # Extract just the .accdb
            subprocess.run(
                ["unzip", "-o", "-j", str(zip_path),
                 f"IPEDS{year}{(year + 1) % 100:02d}.accdb",
                 "-d", str(IPEDS_DIR)],
                check=False, capture_output=True,
            )
            zip_path.unlink()
            break
    return years_available()


def ef_rows_for_year(year: int, ef: dict, names: dict[int, str]) -> list[dict]:
    """Flatten one year's EF dict into long-form rows for raw_ipeds.csv.
    Includes every institution, not just our 66."""
    cols = race_cols_for_year(year)
    rows: list[dict] = []
    for uid, by_key in ef.items():
        for col, label, legacy in cols:
            row = {
                "year": str(year),
                "unitid": str(uid),
                "instnm": names.get(uid, ""),
                "category": label,
                "first_time_first_year": "",
                "undergraduates": "",
                "total_undergraduates": "",
                "legacy_combined": str(legacy),
                "source_file": f"IPEDS_EF{year}A",
            }
            present = False
            for efalevel, cds_col in EFALEVEL_TO_COL.items():
                v = by_key.get((efalevel, col))
                if v is not None:
                    row[cds_col] = str(v)
                    present = True
            if present:
                rows.append(row)
    return rows


def write_raw_ipeds(rows: list[dict]) -> None:
    """Write the consolidated all-institutions long-form CSV."""
    rows.sort(key=lambda r: (int(r["year"]), int(r["unitid"]), r["category"]))
    RAW_IPEDS_OUT.parent.mkdir(parents=True, exist_ok=True)
    with RAW_IPEDS_OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "year", "unitid", "instnm", "category",
            "first_time_first_year", "undergraduates", "total_undergraduates",
            "legacy_combined", "source_file",
        ])
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = sys.argv[1:]
    do_download = "--download" in args
    args = [a for a in args if a != "--download"]
    only_years: set[int] | None = (
        {int(a) for a in args} if args else None
    )

    if do_download:
        # Try every IPEDS year from 2004-05 to 2024-25.
        download_missing_zips(list(range(2004, 2025)))

    years = [y for y in years_available() if y >= MIN_IPEDS_YEAR]
    if only_years:
        years = [y for y in years if y in only_years]
    if not years:
        raise SystemExit(f"No IPEDS .accdb files in {IPEDS_DIR} (>= {MIN_IPEDS_YEAR}). "
                         f"Run with --download or place files manually.")

    total_school_rows = 0
    all_raw_rows: list[dict] = []
    for year in years:
        accdb = IPEDS_DIR / f"IPEDS{year}{(year + 1) % 100:02d}.accdb"
        print(f"\n=== year {year} ({accdb.name}) ===")
        ef = extract_ef_table(accdb, year)
        names = extract_hd_table(accdb, year)
        rows = write_school_csvs(year, ef)
        total_school_rows += rows
        year_rows = ef_rows_for_year(year, ef, names)
        all_raw_rows.extend(year_rows)
        print(f"  {len(ef)} institutions, {rows} per-school CDS-style rows, "
              f"{len(year_rows)} long-form rows")

    print(f"\nPer-school CSVs: {total_school_rows} rows across {len(years)} years.")

    # When run with --years filter, don't clobber raw_ipeds.csv with a partial
    # year set. Only rewrite when we covered every cached year.
    if not only_years:
        write_raw_ipeds(all_raw_rows)
        print(f"Wrote {len(all_raw_rows)} rows to {RAW_IPEDS_OUT.relative_to(ROOT)}")
    else:
        print(f"  (skipping raw_ipeds.csv rewrite — partial year set: {sorted(only_years)})")


if __name__ == "__main__":
    main()
