# Elite College Admissions After *SFFA v. Harvard*

Replication package for David Kane, "Elite College Admissions After
*SFFA v. Harvard*" (submitted to Econ Journal Watch). The paper tests
the enrollment predictions made by elite colleges and their expert
witnesses during *Students for Fair Admissions v. Harvard* against
realized post-ruling enrollment through fall 2025, using Common Data Set
(CDS) and IPEDS records assembled for sixty-six selective colleges and
universities.

Everything in the paper — every number, table, and figure — can be
reproduced from this repository. There are two levels of replication:
rendering the paper from the included cleaned data (minutes), and
rebuilding the cleaned data from the primary sources (longer, documented
below).

## Repository layout

- `paper/` — the manuscript:
  - `paper.qmd` — Quarto source; all statistics in the paper are
    computed in its R chunks directly from `data/processed/clean.csv`
  - `paper.pdf`, `paper.docx` — rendered versions as submitted
  - `ejw-reference.docx` — Word style template used by the docx render
- `code/` — the Python pipeline that builds the dataset (details below)
- `data/downloads/<school>/` — the primary sources: every CDS filing
  (PDF or Excel) used, as published by each school. Schools do remove
  old filings from their sites, so these are archived here.
- `data/scraped/<school>/` — per-school extracted CSVs
  (`b2_enrollment.csv` from CDS filings, `ipeds.csv` from IPEDS)
- `data/processed/` — pipeline outputs, most importantly `clean.csv`,
  the analysis file the paper reads
- `documents/` — primary-source litigation documents (expert reports,
  court opinions, amicus briefs) and the College Board 2025 annual
  report, with a README giving sources and citations

## Reproducing the paper (the short path)

Requirements: [Quarto](https://quarto.org) with a LaTeX distribution
(for PDF), and R with the packages `dplyr`, `tidyr`, `ggplot2`,
`scales`, and `knitr`.

```bash
cd paper
quarto render paper.qmd            # html, pdf, and docx
quarto render paper.qmd --to pdf   # just the pdf
```

The manuscript reads `../data/processed/clean.csv`, which is committed,
so this step needs nothing beyond Quarto and R. The output should match
the committed `paper.pdf` and `paper.docx` up to the date stamp.

## Rebuilding the dataset (the long path)

Requirements: [uv](https://docs.astral.sh/uv/). Each script declares its
own Python dependencies inline, so `uv run` handles environments
automatically.

The pipeline has two branches, CDS and IPEDS, which merge at the end:

```
extract_b2.py        ──┐
extract_mit_html.py  ──┤
extract_xlsx_cds.py  ──┤
extract_manual.py    ──┤
                       ├─→ data/scraped/<school>/b2_enrollment.csv ──→ build_complete.py ──→ raw_cds.csv ──→ normalize.py ──→ clean_cds.csv ──┐
                       │                                                                                                                      │
extract_ipeds.py     ──┴─→ data/scraped/<school>/ipeds.csv          ──→ (also writes)  raw_ipeds.csv ──→ normalize_ipeds.py ──→ clean_ipeds.csv ─┤
                                                                                                                                                 │
                                                                                                                    merge_clean.py ──→ clean.csv ─┘
```

Run in order:

```bash
uv run code/extract_b2.py        # parse B2 tables from the CDS PDFs in data/downloads/
uv run code/extract_mit_html.py  # MIT publishes its CDS as HTML pages (fetched live)
uv run code/extract_xlsx_cds.py  # schools publishing CDS as Excel (Berkeley, Cornell, Vanderbilt)
uv run code/extract_manual.py    # hand-transcribed B2 tables (Union 2025-26: unparseable text layer)
uv run code/extract_ipeds.py     # requires IPEDS Access databases, see below
uv run code/build_complete.py    # → data/processed/raw_cds.csv
uv run code/normalize.py         # → data/processed/clean_cds.csv
uv run code/normalize_ipeds.py   # → data/processed/clean_ipeds.csv
uv run code/merge_clean.py       # → data/processed/clean.csv
uv run code/build_sat_scores.py  # → sat_scores.csv + sat_mean_scores.csv (College Board sidecar)
```

Notes:

- **Order matters.** `extract_b2.py` rewrites every per-school CSV from
  the PDFs, so the three special-case extractors (MIT, Excel, manual)
  must run after it or their schools lose their latest year.
- **IPEDS.** The IPEDS Fall Enrollment Access databases (~600 MB per
  year, ~11 GB total) are not committed. `code/extract_ipeds.py
  --download` fetches them from
  [nces.ed.gov](https://nces.ed.gov/ipeds/use-the-data/download-access-database);
  without them, the committed `data/scraped/<school>/ipeds.csv` files
  let every later stage run unchanged.
- **CDS downloads.** The filings in `data/downloads/` were collected
  from each school's institutional research pages between 2025 and
  2026. They are committed because schools remove old filings; no
  download step is needed to re-run the extraction.
- **Sanity check.** `uv run code/check_cds_ipeds.py` diffs CDS-derived
  and IPEDS-derived counts for every shared school-year-category and
  flags large discrepancies (the reason `merge_clean.py` prefers IPEDS
  where both sources exist).

## Data conventions

`clean.csv` is long-format: one row per school, fall term (`year`), and
racial/ethnic category, with counts for first-time first-year students
and all undergraduates. Categories follow the 2010 IPEDS rules (Hispanic
of any race reported as Hispanic; non-Hispanic multiracial students in a
separate category). A `source` column flags each row's origin (`ipeds`
or `cds`); where both sources covered a school-year, IPEDS wins and the
CDS values are preserved in auxiliary columns for cross-checks. Fall
2025 rows are CDS-only, since the corresponding IPEDS collection had not
been released at the time of writing.
