# /// script
# requires-python = ">=3.11"
# dependencies = ["pdfplumber", "pypdf"]
# ///
"""Extract B2 (Enrollment by Racial/Ethnic Category) tables from CDS PDFs.

Iterates every school directory under data/downloads/ and writes one CSV per
school to data/scraped/<school>/b2_enrollment.csv with columns:
    year, category, first_time_first_year, undergraduates, total_undergraduates
"""

from __future__ import annotations

import csv
import re
import urllib.parse
from pathlib import Path

import pdfplumber
import pypdf

ROOT = Path(__file__).resolve().parent.parent
DOWNLOADS_DIR = ROOT / "data" / "downloads"
SCRAPED_DIR = ROOT / "data" / "scraped"

FULL_YEAR_RE       = re.compile(r"((?:19|20)\d{2})")
COMPRESSED_YEAR_RE = re.compile(r"(?<!\d)(\d{2})(\d{2})(?!\d)")
SPLIT_YEAR_RE      = re.compile(r"(?<!\d)(\d{2})[-_](\d{2})(?!\d)")
B2_KEYWORDS = (
    "hispanic", "black", "white", "asian",
    "american indian", "native hawaiian", "pacific islander",
    "two or more", "ethnicity unknown", "nonresident",
)


def year_from_filename(name: str) -> str:
    """Pull the academic year start from a CDS filename. Handles formats like
    cds_2024-2025.pdf, CDS_2425_..., Brown_CDS07_08.pdf, CDS_1999-2000.pdf,
    and URL-encoded filenames (%20 etc.)."""
    name = urllib.parse.unquote(name)
    # Take the first plausible 4-digit year, ignoring stray "20" from %20 etc.
    for m in FULL_YEAR_RE.finditer(name):
        y = int(m.group(1))
        if 1995 <= y <= 2030:
            return str(y)
    # Fall back to compressed academic-year forms like _2425_ or 07_08.
    for pat in (COMPRESSED_YEAR_RE, SPLIT_YEAR_RE):
        for mm in pat.finditer(name):
            a, b = int(mm.group(1)), int(mm.group(2))
            if b == a + 1:
                return str(2000 + a) if a < 90 else str(1900 + a)
    return ""


def b2_score(table) -> int:
    flat = " ".join((c or "") for r in table for c in r).lower()
    return sum(1 for kw in B2_KEYWORDS if kw in flat)


def pick_b2_table(pdf):
    """Scan every page; return the table with the highest B2-keyword score.

    If the chosen table is missing the canonical "Total" row, look at tables
    on subsequent pages for continuation rows (Yale 2025-26 splits its B2
    table across two pages — first page has 8 race categories, second page
    has Race-and/or-ethnicity unknown + TOTAL). Append any such continuation
    rows so the full B2 table comes through."""
    best, best_score, best_loc = None, 0, (-1, -1)
    all_tables: list[tuple[int, int, list]] = []
    for pi, page in enumerate(pdf.pages):
        for ti, table in enumerate(page.extract_tables() or []):
            all_tables.append((pi, ti, table))
            s = b2_score(table)
            if s > best_score:
                best, best_score, best_loc = table, s, (pi, ti)
    if best is None or best_score < 4:
        return None

    # Continuation: if best table doesn't already contain a "Total" row, look
    # at subsequent tables (later on same page or on later pages) for small
    # tables whose first cell is "TOTAL" or contains "ethnicity unknown" and
    # has the same column count.
    def has_total(tbl):
        return any(re.match(r"\s*total\b", (c or "").strip(), re.I)
                   for r in tbl for c in (r or [])[:1])

    if has_total(best):
        return best

    pi, ti = best_loc
    target_cols = max((len(r) for r in best), default=0)
    extras = []
    for ppi, tti, tbl in all_tables:
        if (ppi, tti) <= (pi, ti):
            continue  # only look forward
        if ppi - pi > 1:
            break  # don't search beyond the immediately-next page
        # Pull rows whose first cell looks like a B2 continuation row.
        for raw in tbl:
            if not raw:
                continue
            first = (raw[0] or "").strip().lower()
            if not first:
                continue
            if (re.match(r"^total\b", first)
                    or "ethnicity unknown" in first
                    or first.startswith("unknown")):
                # Pad/truncate to target column count for shape consistency.
                row = list(raw)[:target_cols]
                row += [""] * (target_cols - len(row))
                extras.append(row)
        if extras:
            break  # take continuation rows from the first page that had any

    return best + extras if extras else best


# Pattern for the "B-prefix" CDS layout used by some 2024-25 / 2025-26 PDFs
# (e.g. Williams, Carleton). The B2 table is written as 30 single-line rows:
#   B201 Nonresidents 60                       <- first-time first-year column
#   B202 Hispanic/Latino 85
#   ...
#   B210 TOTAL 547
#   B211 Nonresidents 182                      <- degree-seeking undergraduates
#   ...
#   B220 TOTAL 2071
#   B221 Nonresidents 189                      <- total undergraduates
#   ...
#   B230 TOTAL ...
# Each row has B-number = "B2" + column-digit (0/1/2) + 2-digit category
# (01-09 + 10 for the TOTAL of that column). One PDF row per (column, category)
# rather than the canonical 10 rows × 3 columns layout.
_B_PREFIX_RE = re.compile(
    # B-number, then category (greedy non-greedy), then value, then optional
    # trailing breadcrumb text. Carleton's pages put garbage like
    # "EnrollmentE nro llmentD eg ree-se..." after the value; Williams has
    # nothing after.
    r"^B2(\d{2})\s+(.+?)\s+([\d,]+)(?:\s+\D.*)?$"
)
_B_PREFIX_CATS = {
    1: "Nonresidents",
    2: "Hispanic/Latino",
    3: "Black or African American, non-Hispanic",
    4: "White, non-Hispanic",
    5: "American Indian or Alaska Native, non-Hispanic",
    6: "Asian, non-Hispanic",
    7: "Native Hawaiian or other Pacific Islander, non-Hispanic",
    8: "Two or more races, non-Hispanic",
    9: "Race and/or ethnicity unknown",
    0: "TOTAL",  # B210, B220, B230 → TOTAL of each column
}


def parse_b2_via_b_prefix(pdf):
    """Detect and parse the single-column B-prefix CDS layout.

    Returns rows shaped [(label, [first_year, undergrads, total_undergrads])]
    or [] if the PDF doesn't use this layout. We only return rows when at
    least 16 of the expected 30 (B201-B230) entries are found, to avoid
    accidentally picking up a stray "B201" appearing somewhere else.
    """
    by_cat_col: dict[int, dict[int, str]] = {}
    for page in pdf.pages:
        text = page.extract_text() or ""
        for line in text.splitlines():
            m = _B_PREFIX_RE.match(line.strip())
            if not m:
                continue
            num = int(m.group(1))
            value = m.group(3).replace(",", "")
            # Numbering: 01-10 = first-year column, 11-20 = undergrads,
            # 21-30 = total undergrads. Within each block, 1-9 are the nine
            # racial/ethnic categories and 10/20/30 are the TOTAL row.
            col = (num - 1) // 10       # 0, 1, or 2
            cat = num % 10              # 1-9 + 0 (TOTAL)
            if col > 2:
                continue
            by_cat_col.setdefault(cat, {})[col] = value

    # Need a critical mass of cells before we trust this layout.
    n_cells = sum(len(v) for v in by_cat_col.values())
    if n_cells < 16:
        return []

    rows = []
    for cat in (1, 2, 3, 4, 5, 6, 7, 8, 9, 0):  # canonical order, TOTAL last
        if cat not in by_cat_col:
            continue
        d = by_cat_col[cat]
        rows.append((
            _B_PREFIX_CATS[cat],
            [d.get(0, ""), d.get(1, ""), d.get(2, "")],
        ))
    return rows


def parse_b2_via_words(pdf):
    """Fallback: when extract_tables loses row labels, group words by y-coordinate
    and reattach wrapped labels by walking adjacent text-only / numbers-only rows."""
    best_rows, best_score = [], 0
    for page in pdf.pages:
        words = page.extract_words()
        if not words:
            continue
        # Bin words into rows by their top y-coordinate (3px tolerance).
        bins: dict[int, list] = {}
        for w in words:
            y = round(w["top"])
            key = next((k for k in bins if abs(k - y) <= 3), y)
            bins.setdefault(key, []).append(w)

        items = []
        for y in sorted(bins):
            ws = sorted(bins[y], key=lambda w: w["x0"])
            text = " ".join(w["text"] for w in ws if not NUM_RE.match(w["text"])).strip()
            nums = [w["text"] for w in ws if NUM_RE.match(w["text"])]
            items.append((text, nums))

        # Merge wrapped rows: numbers-only line absorbs adjacent text-only neighbours.
        rows: list[tuple[str, list[str]]] = []
        skip_next = False
        for i, (text, nums) in enumerate(items):
            if skip_next:
                skip_next = False
                continue
            if nums and text:
                rows.append((text, nums))
            elif nums and not text:
                prefix = items[i - 1][0] if i > 0 and not items[i - 1][1] else ""
                suffix = ""
                if i + 1 < len(items) and not items[i + 1][1] and items[i + 1][0]:
                    suffix = items[i + 1][0]
                    skip_next = True
                label = f"{prefix} {suffix}".strip()
                if label:
                    rows.append((label, nums))

        # Keep only rows whose label looks like a B2 category.
        b2_rows = [
            (lbl, nums) for lbl, nums in rows
            if any(kw in lbl.lower() for kw in B2_KEYWORDS) or lbl.lower().startswith("total")
        ]
        score = sum(1 for lbl, _ in b2_rows if any(kw in lbl.lower() for kw in B2_KEYWORDS))
        if score > best_score:
            best_rows, best_score = b2_rows, score

    if best_score < 4:
        return []
    # A page can hold B1 above B2 (Pomona's Tableau export): B1's "Total ..."
    # rows pass the label filter but precede the first racial/ethnic category
    # row. The B2 table always opens with a category row, so drop leading
    # total-rows.
    first_cat = next((i for i, (lbl, _) in enumerate(best_rows)
                      if any(kw in lbl.lower() for kw in B2_KEYWORDS)), 0)
    return best_rows[first_cat:]


# Match a numeric cell, tolerating internal whitespace and commas — some PDFs
# render "366" as "3 66" or "1,554" as "1 ,554" due to kerning.
NUM_RE = re.compile(r"^\d[\d,\s]*(?:\.\d+)?$")

# Stanford's 2025-26 CDS wraps every numeric B2 cell in parentheses — "(237)"
# instead of "237". Strip a wrapping pair when the inside is a plain number.
PAREN_NUM_RE = re.compile(r"^\((\d[\d,\s]*(?:\.\d+)?)\)$")


# Tufts' 2025-26 PDF embeds its bold font without a ToUnicode map, so labels
# set in it extract as "(cid:55)(cid:82)..." — the cid is the glyph id, which
# for this font is the codepoint shifted by 29. Decode only when the result
# reads like a B2 label; otherwise the garbled original is returned (and will
# be dropped downstream like any other junk row).
CID_RE = re.compile(r"\(cid:(\d+)\)")


def decode_cid(s: str) -> str:
    if "(cid:" not in s:
        return s
    decoded = CID_RE.sub(lambda m: chr(int(m.group(1)) + 29), s)
    dl = decoded.lower()
    if dl.startswith("total") or any(kw in dl for kw in B2_KEYWORDS):
        return decoded
    return s


def clean(cell: str | None) -> str:
    s = decode_cid((cell or "").replace("\n", " ").strip())
    m = PAREN_NUM_RE.match(s)
    return m.group(1) if m else s


def is_number(s: str) -> bool:
    return bool(NUM_RE.match(s))


def num_value(s: str) -> str:
    """Strip whitespace and thousands separators from a number string."""
    return re.sub(r"[\s,]", "", s)


def normalize_row(row):
    """Return (category, [numbers]) or None if the row is a header/blank."""
    cells = [clean(c) for c in row if clean(c)]
    if not cells:
        return None
    # Find the category cell (first non-numeric) and collect trailing numbers.
    category = None
    nums = []
    for c in cells:
        if is_number(c):
            nums.append(num_value(c))
        elif category is None:
            category = c
        else:
            # text after we already have a category — likely a wrapped header
            return None
    if category is None or not nums:
        return None
    return category, nums


# Map AcroForm widget field-name fragments to canonical B2 category labels.
# Used by parse_b2_via_form_fields for interactive (form-fillable) CDS PDFs,
# where the numeric values live in form widgets rather than the text layer.
# Keys are matched against the substring between the EN_<col>_ prefix and the
# trailing _N. Order matters: longer/more-specific keys are tried first so
# RACE_ETHNICITY_TOT doesn't match before RACE_ETHNICITY_UNKNOWN, etc.
FORM_CATEGORY_MAP = (
    ("NONRES_ALIEN",            "Nonresident aliens"),
    ("HISPANIC_ETHNICITY",      "Hispanic/Latino"),
    ("BLACK_NONHISPANIC",       "Black or African American, non-Hispanic"),
    ("WHITE_NONHISPANIC",       "White, non-Hispanic"),
    ("NATIVE_NONHISPANIC",      "American Indian or Alaska Native, non-Hispanic"),
    ("ASIAN_NONHISPANIC",       "Asian, non-Hispanic"),
    ("ISLANDER_NONHISPANIC",    "Native Hawaiian or other Pacific Islander, non-Hispanic"),
    ("HAWAIIAN_NONHISPANIC",    "Native Hawaiian or other Pacific Islander, non-Hispanic"),
    ("MULTIRACE_NONHISPANIC",   "Two or more races, non-Hispanic"),
    ("MULTI_NONHISPANIC",       "Two or more races, non-Hispanic"),
    ("RACE_ETHNICITY_UNKNOWN",  "Race and/or ethnicity unknown"),
    ("UNKNOWN",                 "Race and/or ethnicity unknown"),
    ("RACE_ETHNICITY_TOT",      "Total"),
    ("TOTAL",                   "Total"),
)


_FORM_KEY_TO_LABEL = dict(FORM_CATEGORY_MAP)


def _classify_field(name: str) -> tuple[str | None, str | None]:
    """For a CDS B2 form-field name, return (category_label, column) or (None, None).

    Field naming used by the College Board's CDS template:
      EN_1ST_<CATEGORY>_N         → first-time first-year
      EN_1ST_<CATEGORY>_1ST_N     → first-time first-year (NONRES_ALIEN special case)
      EN_<CATEGORY>_N             → degree-seeking undergraduates
      EN_TOT_<CATEGORY>_N         → total undergraduates
      EN_TOT_<CATEGORY>_TOT_N     → total undergraduates (NONRES_ALIEN special case)
    """
    if not (name.startswith("EN_") and name.endswith("_N")):
        return None, None
    body = name[3:-2]  # strip 'EN_' and '_N'
    if body.startswith("1ST_"):
        col = "first_time_first_year"
        cat_part = body[4:]
    elif body.startswith("TOT_"):
        col = "total_undergraduates"
        cat_part = body[4:]
    else:
        col = "undergraduates"
        cat_part = body
    # Try exact match first; only strip a trailing _1ST/_TOT if the result is
    # itself a known category (preserves keys that legitimately contain _TOT,
    # e.g. RACE_ETHNICITY_TOT means the totals row, not a TOT-suffix on
    # RACE_ETHNICITY).
    if cat_part in _FORM_KEY_TO_LABEL:
        return _FORM_KEY_TO_LABEL[cat_part], col
    for suf in ("_1ST", "_TOT"):
        if cat_part.endswith(suf):
            stripped = cat_part[: -len(suf)]
            if stripped in _FORM_KEY_TO_LABEL:
                return _FORM_KEY_TO_LABEL[stripped], col
    return None, None


def parse_b2_via_form_fields(pdf_path: Path):
    """Pull B2 values from AcroForm widgets via pypdf's get_fields(). Returns
    list of (label, [first_year, undergraduates, total_undergraduates])."""
    try:
        reader = pypdf.PdfReader(str(pdf_path))
    except Exception:
        return []
    fields = reader.get_fields() or {}
    if not fields:
        return []

    by_label: dict[str, dict[str, str]] = {}
    for name, field in fields.items():
        label, col = _classify_field(name)
        if not label:
            continue
        v = field.get("/V", "")
        if isinstance(v, bytes):
            v = v.decode("utf-8", errors="ignore")
        v = "" if v is None else str(v).strip()
        # Empty form fields are recorded as "" not skipped — the user wants to
        # know the category exists even if the school left a value blank.
        by_label.setdefault(label, {})[col] = v

    # Emit rows in the canonical order. A row is included only if at least one
    # of its three columns has a non-empty value.
    rows = []
    seen = set()
    for _key, label in FORM_CATEGORY_MAP:
        if label in seen:
            continue
        seen.add(label)
        if label not in by_label:
            continue
        d = by_label[label]
        triple = [
            d.get("first_time_first_year", ""),
            d.get("undergraduates", ""),
            d.get("total_undergraduates", ""),
        ]
        if any(t.strip() for t in triple):
            rows.append((label, triple))
    return rows


def extract_b2_rows(pdf_path: Path):
    year = year_from_filename(pdf_path.name)

    # Method 0: AcroForm widgets (try first — when present, the form-field
    # values are authoritative and the text-layer table is usually blank).
    # Used by 2024-25 and 2025-26 fillable templates from the College Board.
    try:
        form_rows = parse_b2_via_form_fields(pdf_path)
    except Exception as e:
        print(f"  ! form-field error in {pdf_path.name}: {type(e).__name__}: {e}")
        form_rows = []
    if form_rows and len(form_rows) >= 8:
        out = []
        for category, nums in form_rows:
            cleaned = [num_value(n) for n in nums]
            out.append([year, category, *((cleaned + ["", "", ""])[:3])])
        return out

    # All pdfplumber-backed methods share one open() call to avoid re-parsing
    # the PDF three times.
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Method 0.5: B-prefix layout. Some 2024-25/2025-26 PDFs
            # (Williams, Carleton) write the B2 table as 30 single-line rows
            # like "B203 Black or African American, non-Hispanic 40" — the
            # column membership is encoded in the B-number, not in the
            # visual table layout, so the standard table extractor pulls
            # them in the wrong order or only the wrong subset.
            try:
                b_rows = parse_b2_via_b_prefix(pdf)
            except Exception as e:
                print(f"  ! b-prefix error in {pdf_path.name}: {type(e).__name__}: {e}")
                b_rows = []
            if b_rows:
                out = []
                for category, nums in b_rows:
                    cleaned = [num_value(n) for n in nums]
                    out.append([year, category, *((cleaned + ["", "", ""])[:3])])
                return out

            # Method 1: bordered table extraction (works when cells contain text+numbers)
            rows = []
            try:
                table = pick_b2_table(pdf)
            except Exception as e:
                print(f"  ! table-extract error in {pdf_path.name}: {type(e).__name__}: {e}")
                table = None
            if table is not None:
                # Column map: the indices that hold numbers anywhere in the
                # table. When there are exactly three (the canonical B2
                # shape), assign values by column index so a blank cell
                # (Duke 2025-26 leaves first-time first-year empty for
                # Pacific Islander) stays in its column instead of the
                # remaining values shifting left.
                numeric_cols = sorted({
                    j for raw in table for j, c in enumerate(raw or [])
                    if is_number(clean(c))
                })
                for raw in table:
                    norm = normalize_row(raw)
                    if norm:
                        category, nums = norm
                        if (2 <= len(numeric_cols) <= 3
                                and 0 < len(nums) < len(numeric_cols)):
                            nums = [
                                num_value(clean(raw[j]))
                                if j < len(raw) and is_number(clean(raw[j]))
                                else ""
                                for j in numeric_cols
                            ]
                        rows.append([year, category, *((nums + ["", "", ""])[:3])])
            if rows:
                # Plausibility check: a real B2 table has ≥2 numeric columns
                # on most rows. Tableau-exported PDFs (Pomona 2024-25 on)
                # fuse the three counts into one undelimited number per row
                # in the extracted table; the word layer keeps them separate,
                # so prefer the word fallback when it splits better.
                multi = sum(1 for r in rows
                            if sum(1 for v in r[2:5] if v) >= 2)
                if multi * 2 < len(rows):
                    try:
                        word_rows = parse_b2_via_words(pdf)
                    except Exception:
                        word_rows = []
                    w = [[year, c, *(([num_value(n) for n in ns] + ["", "", ""])[:3])]
                         for c, ns in word_rows]
                    w_multi = sum(1 for r in w
                                  if sum(1 for v in r[2:5] if v) >= 2)
                    if w_multi > multi:
                        return w
                return rows

            # Method 2: word-position fallback (numbers separated from labels in text layer)
            try:
                word_rows = parse_b2_via_words(pdf)
            except Exception as e:
                print(f"  ! word-fallback error in {pdf_path.name}: {type(e).__name__}: {e}")
                word_rows = []
            if word_rows:
                for category, nums in word_rows:
                    cleaned = [num_value(n) for n in nums]
                    rows.append([year, category, *((cleaned + ["", "", ""])[:3])])
                return rows
    except Exception as e:
        print(f"  ! pdf-open error in {pdf_path.name}: {type(e).__name__}: {e}")

    # Final fallback: if we had partial form-field data (<8 rows), use it.
    if form_rows:
        out = []
        for category, nums in form_rows:
            cleaned = [num_value(n) for n in nums]
            out.append([year, category, *((cleaned + ["", "", ""])[:3])])
        return out

    print(f"  ! B2 table not found in {pdf_path.name}")
    return []


def process_school(school_dir: Path) -> tuple[int, int, int]:
    out_dir = SCRAPED_DIR / school_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "b2_enrollment.csv"

    pdfs = sorted(school_dir.glob("*.pdf"), key=lambda p: year_from_filename(p.name))
    print(f"\n=== {school_dir.name} ({len(pdfs)} PDFs) ===")
    total_rows = empty_pdfs = 0
    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "year", "category",
            "first_time_first_year", "undergraduates", "total_undergraduates",
            "source_file",
        ])
        for pdf in pdfs:
            year = year_from_filename(pdf.name)
            extracted = extract_b2_rows(pdf)
            if not extracted:
                empty_pdfs += 1
            print(f"  {pdf.name:<55.55} year={year or '????'}  rows={len(extracted)}")
            # Append source filename so downstream dedup can pick the winning revision
            writer.writerows([row + [pdf.name] for row in extracted])
            total_rows += len(extracted)
    print(f"Wrote {total_rows} rows to {out_path.relative_to(ROOT)}")
    return len(pdfs), total_rows, empty_pdfs


def main():
    schools = sorted(d for d in DOWNLOADS_DIR.iterdir() if d.is_dir())
    summary = []
    for school_dir in schools:
        pdfs, rows, empty = process_school(school_dir)
        summary.append((school_dir.name, pdfs, rows, empty))
    print("\n=== Summary ===")
    print(f"  {'school':<12} {'PDFs':>5} {'rows':>6} {'empty':>6}")
    for name, pdfs, rows, empty in summary:
        print(f"  {name:<12} {pdfs:>5} {rows:>6} {empty:>6}")


if __name__ == "__main__":
    main()
