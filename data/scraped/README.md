# `data/scraped/` — extracted enrollment tables, one CSV per school

Each `<school>/` directory holds two per-school CSVs in the same column shape:

- `b2_enrollment.csv` — extracted from the school's CDS PDFs by
  `code/extract_b2.py` (and `code/extract_mit_html.py` for MIT, which
  publishes its CDS as HTML rather than PDF).
- `ipeds.csv` — extracted from each year's IPEDS Fall Enrollment Access
  database by `code/extract_ipeds.py`. Same row layout (year, category,
  three count columns) so the two files are directly comparable.

The combined cross-school files live in
[`../processed/`](../processed/): `raw_cds.csv` is the consolidated PDF
data, `raw_ipeds.csv` is the IPEDS data for **every** institution (not
just our 66), and `clean.csv` is the PDF-preferred merge used for analysis.
See `../../README.md` for the full pipeline.

Both per-school CSVs share these columns:

```
year, category, first_time_first_year, undergraduates, total_undergraduates,
[legacy_combined,] source_file
```

## How extraction works

Three methods are tried in order; the first one that returns rows wins:

1. **Bordered-table extraction.** `pdfplumber.extract_tables()` finds the page's tables and the script picks the one with the highest count of B2-keyword matches ("Hispanic", "Black", "Asian", etc.). This handles the common case where labels and numbers share cells.
2. **Word-position fallback.** When the table extractor returns blank cells (some 2023-24+ PDFs put labels in bordered cells but render the numbers outside them), the script bins all words on the page by y-coordinate and reattaches multi-line wrapped categories ("American Indian or Alaska Native, non-Hispanic" wraps in the 2023-24 Dartmouth template).
3. **AcroForm-widget fallback.** Brown's 2025-26 and Cornell's 2024-25 are interactive form-fillable PDFs — the values aren't in the text layer at all. The script reads the widget annotations directly, mapping field names like `EN_1ST_BLACK_NONHISPANIC_N` to canonical category labels.

Filename year detection handles four naming conventions: `cds_2024-2025.pdf`, `Brown_CDS07_08.pdf` (split short years), `cds_2425_princeton.pdf` (compressed short years), and URL-encoded names (`CDS%20...%202022-2023.pdf`). Plausibility check rejects 4-digit matches outside `[1995, 2030]` and falls back to compressed parsing — without this, Princeton's `cds_1920_princeton.pdf` (= academic year 2019-20) was being tagged as year 1920.

## The 2010 IPEDS revision — when each school switched

The 2010 IPEDS race/ethnicity revision replaced an 8-row schema (with "Asian or Pacific Islander" and "Hispanic" combined-line) with a 10-row schema (split Asian from Pacific Islander, added "Two or more races, non-Hispanic", changed "Hispanic" to "Hispanic/Latino"). The new schema was first reported on the 2010-11 CDS for most schools.

Detection: I treated the first appearance of "Two or more races" in a school's data as the switch year:

| Switch year | Schools |
|---|---|
| 2010-11 | amherst, bates, bowdoin, brown, colby, cornell, dartmouth, hamilton, harvard, jhu, penn, princeton, stanford, wesleyan, williams, yale (16 schools — the standard adoption) |
| 2011-12 | caltech, duke, trinity, tufts (one year delayed) |
| 2012-13 | conncoll (the school's earliest available CDS is 2012-13, so this just reflects when the data starts) |
| 2021-22 | columbia, uchicago (their first ever CDS publications, both already on the post-2010 schema) |
| never | mit (only one year of data, 1999-2000) |

So **the answer is no** — schools didn't all switch at the same year. The cleanest break is 2010-11; the four "delayed" schools (caltech, duke, trinity, tufts) kept the old categories one extra year.

Pre-2010 categories also vary slightly across schools — most use "Black, non-Hispanic" but a few used "Black or African American". Exact category strings should be normalized (e.g., regex-grouping `^Black|^African`) before doing cross-school analysis.

## Coverage by school

(Year ranges and PDF counts. Rows per year vary but should be 8 pre-2010 / 10 post-2010 in normal cases. Per-year row counts under that suggest extraction loss; over that suggests duplicates from multiple PDF revisions.)

| School | PDFs | Rows | Range | Notes |
|---|---:|---:|---|---|
| amherst | 256 | 213 | 2002–2025 | Section-per-PDF publishing — only Section B PDFs contain B2; the other 233 "files" are sections A, C, D... and correctly produce 0 rows. The 213 actual B2 rows cover ~24 years. |
| bates | 27 | 239 | 1999–2025 | Recent two years (2024, 2025) yield 6 rows each — see "form-field empty values" below |
| bowdoin | 25 | 223 | 2001–2025 | Recent two years yield 6 rows each — same form-field issue |
| brown | 22 | 204 | 2003–2025 | 2025 yields only 6 rows (form-field issue) |
| caltech | 23 | 198 | 2002–2024 | 2007 yields 1 row, 2008 yields 0 — these PDFs have unusual layouts; investigation pending |
| colby | 15 | 126 | 2000–2015 | 2001 yields only 2 rows — partial extraction; 2016+ years not published |
| columbia | 4 | 40 | 2021–2024 | Clean — 10 rows × 4 years |
| conncoll | 14 | 140 | 2012–2025 | Clean — 10 rows × 14 years |
| cornell | 26 | 228 | 1999–2024 | 2024 yields 6 rows (form-field issue); 2022/2023 yield 8/9 rows |
| dartmouth | 23 | 214 | 2003–2025 | Clean reference dataset |
| duke | 16 | 152 | 2008–2024 | 2022 missing (Duke skipped publishing) |
| hamilton | 21 | 196 | 2005–2025 | 2023 yields 8 rows |
| harvard | 19 | 184 | 2006–2024 | 2023 yields 13 rows (extra rows include sub-totals) |
| jhu | 11 | 101 | 2007–2024 | 2014–2020 missing (JHU didn't publish); 2022 yields 7 |
| middlebury | 21 | 149 | 2005–2025 | **2014–2020 returns mostly 1 row each** — those years have an unusual table layout with embedded percentages in category cells. The numeric values for 2014 are still recoverable from the polluted labels but require post-processing. |
| mit | 1 | 8 | 1999 only | Only one PDF exists; MIT publishes HTML for other years |
| penn | 16 | 156 | 2009–2024 | Clean — 10 rows × ~16 years |
| princeton | 25 | 228 | 2001–2025 | **2020 returns 0 rows** (PDF format different); 2021 returns 20 (duplicate from `cds_2021_princeton.pdf` + `cds_2122_princeton.pdf` both tagged as year 2021); 2022 only 6 rows |
| stanford | 25 | 215 | 2001–2025 | **2008 returns 1 row**, 2017 returns 4 graduate-student rows (table picker found wrong table); 2019–2022 return 20+ rows (multiple tables on one page, all included) |
| trinity | 16 | 154 | 2009–2024 | 2013 yields 9, 2022 yields 11 |
| tufts | 14 | 140 | 2011–2024 | Clean |
| uchicago | 4 | 39 | 2021–2024 | 2022 yields 9 rows |
| wesleyan | 22 | 201 | 2001–2022 | Clean for available years; 2023+ not published |
| williams | 33 | 277 | 1998–2024 | **Inflated row counts in 2018–2023** — Williams publishes multiple revisions per year and all are present in `data/downloads/williams/`, so the same year appears multiple times in the CSV |
| yale | 23 | 214 | 2003–2025 | 2025 yields 8 rows |

## Known issues that affect downstream analysis

### Form-field PDFs underreport empty cells

Several recent (2024-25, 2025-26) PDFs are interactive AcroForm files. The school fills in numbers as form-field values. **Empty form fields are skipped entirely** by `parse_b2_via_form_fields`. Looking at Brown 2025 in `brown/b2_enrollment.csv`:

```
Nonresident aliens, 227, 926, 1074
Hispanic/Latino,    , 828,
Black or African American, non-Hispanic,  , 566,
```

Only the middle (`undergraduates`) column is populated for most rows. The first and third columns appear empty because Brown's form has those fields blank — likely either zero values stored as empty strings, or the school only filled the middle column. Affected years: bates 2024+25, bowdoin 2024+25, brown 2025, cornell 2024.

**Workaround for analysis:** when a form-field row has an empty `first_time_first_year` or `total_undergraduates`, treat it as missing rather than imputing 0. The `undergraduates` column is reliable for these rows.

### Duplicate rows from multiple PDF revisions

- **Williams** has March vs. June revisions, "with tuition decrease" vs. without, V4 vs. V5, etc. for 2018-2024. All revisions are in the downloads folder and all appear in the CSV. For aggregate analysis, deduplicate by year (keep the latest revision: `_FINAL`, `_V5`, or the last by filename).
- **Princeton 2021** appears twice because `cds_2021_princeton.pdf` (probably 2020-21) and `cds_2122_princeton.pdf` (definitely 2021-22) both resolve to year 2021 under the current filename-year regex. The numbers differ (1288 vs 1146 first-year totals), confirming they're different academic years. Manual fix: rename `cds_2021_princeton.pdf` to clarify which year it represents, or drop one.

### Wrong-table extraction

- **Stanford 2017** captured the graduate-enrollment table instead of B2 — the score-based picker picked a high-scoring table that wasn't B2. Numbers in those four rows are about graduate students.
- **Stanford 2008** and **Caltech 2008** and **Princeton 2020** returned 0 or 1 rows — the B2 tables weren't found at all. Those PDFs need a closer look (probably scanned, or atypical layout).

### Polluted category labels

- **Middlebury 2014** has labels like `"B2 Nonresident aliens 11.7% 10.0% 10.7%"` because that year's PDF format embeds percentages into the same cell. The trailing 3 numeric columns *are* correct values; only the category string is messy. If you filter on `category` substring rather than equality, this is recoverable.
- Several schools have an extra space in `non- Hispanic` (Bowdoin, Stanford, Wesleyan, Yale, Cornell — depending on year) due to the soft-hyphen line wrap in their PDFs. Match with `"non-?\s*Hispanic"` regex if exact equality matters.
- The `Total` row label varies: `Total`, `TOTAL`, `total`. Lower-case before comparing.

## Cleanup pipeline (now implemented downstream)

These five passes are baked into `code/normalize.py` (which produces
`../processed/clean_cds.csv` from `../processed/raw_cds.csv`):

1. Drop rows with all three numeric columns empty (the empty form-field
   artifacts).
2. Williams revision dedup — `code/build_complete.py` picks the winning
   revision per (school, year) using `revision_score()` (FINAL > V<n> >
   latest month name > alphabetical).
3. Reassign Princeton's `cds_2021_princeton.pdf` rows to academic year 2020.
4. Normalize categories to a canonical 10-category vocabulary, with a
   `legacy_combined` flag for pre-2010 "Asian or Pacific Islander" rows.
5. Strip the `"B2 ... XX.X% YY.Y% ZZ.Z%"` pollution from Middlebury
   2014-2020 categories.

The extractor's job is still just to faithfully reproduce what the PDFs say;
normalization happens downstream.
