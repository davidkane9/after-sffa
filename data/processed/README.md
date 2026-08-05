# `data/processed/` — pipeline outputs

Five long-form CSVs sit here, in two parallel CDS/IPEDS tracks plus one
merged file:

| File | Source | Universe | Notes |
|---|---|---|---|
| `raw_cds.csv` | PDFs | 66 schools | Faithful to source — category strings are whatever the PDF said. Output of `code/build_complete.py`. |
| `clean_cds.csv` | PDFs | 66 schools | `raw_cds.csv` with normalized category names + 5 cleanup passes. Output of `code/normalize.py`. |
| `raw_ipeds.csv` | IPEDS | All ~6,000 institutions | Long-form race counts for every institution IPEDS reports, 2008-2024. Output of `code/extract_ipeds.py`. ~99 MB. |
| `clean_ipeds.csv` | IPEDS | 66 schools | `raw_ipeds.csv` filtered to the 66 schools we track and reshaped to match `clean_cds.csv` exactly. Output of `code/normalize_ipeds.py`. |
| `clean.csv` | merged | 66 schools | PDF-preferred merge: every CDS row, plus IPEDS rows for (school, year) cells CDS doesn't cover. A `source` column flags `cds` vs `ipeds`. Output of `code/merge_clean.py`. **Use this for analysis.** |

## Schema

`clean.csv` (and `clean_cds.csv` / `clean_ipeds.csv`):

```
year                    academic year start (e.g. 2024 = 2024-25 cycle)
school                  internal short code (e.g. "dartmouth")
ivy, ivy.plus, nescac,
SFFA.brief, us.news     boolean group-membership flags
category                one of 10 canonical race/ethnicity labels
first_time_first_year   count of first-time first-year (degree-seeking)
undergraduates          count of degree-seeking undergraduates
total_undergraduates    count of total undergraduates (degree + non-degree)
source_file             provenance — PDF filename or "IPEDS_EF<year>A"
legacy_combined         1 for pre-2010 "Asian or Pacific Islander" rows, else 0
source                  "cds" or "ipeds" (only on clean.csv)
```

`raw_ipeds.csv` differs: it carries `unitid` and `instnm` instead of
`school` (which doesn't exist for institutions outside our 66) and lacks
the group-membership flags.

## Comparison

`analysis/compare.qmd` quantifies CDS-vs-IPEDS agreement. Across the
~760 (school, year) cells covered by both sources, ~90% agree exactly on
the Black first-time first-year count; the rest typically differ by
single digits and trace to revision timing, census-date drift, or
race-question reporting differences. See the rendered report for buckets
and outliers.
