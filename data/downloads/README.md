# `data/downloads/` — raw inputs

Two kinds of inputs land here:

- **`<school>/` directories** — Common Data Set PDFs (and a few HTML pages
  for MIT) downloaded from each school's institutional-research page.
  Committed to the repo as the canonical primary source.
- **`IPEDS/`** — Microsoft Access databases (`.accdb`) for each year's
  IPEDS Fall Enrollment release, downloaded from
  [nces.ed.gov](https://nces.ed.gov/ipeds/use-the-data/download-access-database).
  Gitignored: each is ~600 MB and re-fetchable via
  `uv run code/extract_ipeds.py --download`.

## School groups

The 66 schools fall into five (overlapping) groups, recorded as boolean
columns in the per-school B2 CSVs under [`../scraped/`](../scraped/) and the
project-wide files under [`../processed/`](../processed/) (`raw_cds.csv` /
`clean_cds.csv` from the PDF pipeline; `clean.csv` after `code/merge_clean.py`
folds in IPEDS gap-fill):

- **Ivy League (`ivy`, 8):** brown, columbia, cornell, dartmouth, harvard, penn, princeton, yale
- **Ivy Plus (`ivy.plus`, 14):** the eight Ivies plus caltech, duke, jhu (Johns Hopkins), mit, stanford, uchicago
- **NESCAC (`nescac`, 11):** amherst, bates, bowdoin, colby, conncoll (Connecticut College), hamilton, middlebury, trinity (Hartford), tufts, wesleyan, williams
- **SFFA brief signatories (`SFFA.brief`, 33):** the 33 colleges and universities that signed the Amherst-led amicus brief in *SFFA v. Harvard* (Aug. 1, 2022) — see [`../../documents/08_amherst_williams_amicus_brief.pdf`](../../documents/08_amherst_williams_amicus_brief.pdf). The 33: amherst, barnard, bates, bowdoin, brynmawr, bucknell, carleton, clark, colby, conncoll, davidson, fandm (Franklin & Marshall), hamilton, hampshire, haverford, macalester, middlebury, mtholyoke (Mount Holyoke), oberlin, pomona, reed, sarahlawrence, smith, stolaf (St. Olaf), swarthmore, trinity, tufts, union, vassar, washandlee (Washington & Lee), wellesley, wesleyan, williams.

## Source pages

Each school's CDS lives on its Office of Institutional Research (or equivalent) page:

| School | Source page |
|---|---|
| Amherst | https://www.amherst.edu/about/facts/common_data_sets |
| Bates | https://www.bates.edu/research/common-data-set/ |
| Bowdoin | https://www.bowdoin.edu/ir/common-data/index.html |
| Brown | https://oir.brown.edu/institutional-data/common-data-set |
| Caltech | https://finance.caltech.edu/Resources/cds |
| Colby | https://www.colby.edu/institutionalresearch/dataset/ |
| Columbia | https://opir.columbia.edu/cds |
| Conn College | https://www.conncoll.edu/institutional-research/conn-facts/ |
| Cornell | https://irp.dpb.cornell.edu/common-data-set |
| Dartmouth | https://www.dartmouth.edu/oir/data-reporting/cds/index.html |
| Duke | https://ir.provost.duke.edu/facts-figures/common-data-sets/ |
| Hamilton | https://www.hamilton.edu/offices/oir/common-data-sets |
| Harvard | https://oira.harvard.edu/common-data-set/ |
| Johns Hopkins | https://oira.jhu.edu/reports-2/ |
| Middlebury | https://www.middlebury.edu/assessment-institutional-research/institutional-data/historical-data |
| MIT | https://ir.mit.edu/project-topic/common-data-set/ |
| Penn | https://ira.upenn.edu/penn-numbers/common-data-set |
| Princeton | https://ir.princeton.edu/other-university-data/common-data-set |
| Stanford | https://irds.stanford.edu/data-findings/cds |
| Trinity | https://www.trincoll.edu/asic/factbook/ |
| Tufts | https://provost.tufts.edu/institutionalresearch/about-tufts/common-data-set/ |
| UChicago | https://data.uchicago.edu/common-data-set/ |
| Wesleyan | https://www.wesleyan.edu/ir/common-data-sets.html |
| Williams | https://www.williams.edu/institutional-research/common-data-set/ |
| Yale | https://oir.yale.edu/common-data-set |
| Barnard | https://oir.barnard.edu/institutional-data/common-data-set |
| Bryn Mawr | https://www.brynmawr.edu/inside/offices-services/institutional-research |
| Bucknell | https://www.bucknell.edu/about-bucknell/offices-resources/institutional-research-planning/common-data-set |
| Carleton | https://www.carleton.edu/ir/common-data-set/ |
| Clark | https://www.clarku.edu/offices/strategic-analytics-institutional-research/ |
| Davidson | https://www.davidson.edu/offices-and-services/institutional-research/common-data-set |
| Franklin & Marshall | https://www.fandm.edu/_resources/pdfs/ (no canonical landing page; URL-probed) |
| Hampshire | https://www.hampshire.edu/offices/office-dean-faculty/office-institutional-research/common-data-set |
| Haverford | https://www.haverford.edu/president/institutional-effectiveness/institutional-research |
| Macalester | https://www.macalester.edu/institutionalresearch/commondatasetinfo/ |
| Mount Holyoke | https://www.mtholyoke.edu/common-data-set |
| Oberlin | https://www.oberlin.edu/institutional-research/common-data-set |
| Pomona | https://www.pomona.edu/administration/institutional-research/common-data-set |
| Reed | https://www.reed.edu/ir/cdsindex.html |
| Sarah Lawrence | https://www.sarahlawrence.edu/about/institutional-research.html |
| Smith | https://www.smith.edu/about-smith/institutional-research |
| St. Olaf | https://wp.stolaf.edu/ir-e/institutional-data-and-information/common-data-set/ |
| Swarthmore | https://www.swarthmore.edu/institutional-research/common-data-set |
| Union | https://www.union.edu/institutional-research/common-data-set-cds |
| Vassar | https://offices.vassar.edu/institutional-research/data/ |
| Washington & Lee | https://www.wlu.edu/institutional-research/common-data-set |
| Wellesley | https://www.wellesley.edu/institutionalresearch/data |

## Coverage

| School | PDFs | Year range | Notes |
|---|---:|---|---|
| Amherst | 256 | 2002-03 → 2025-26 | Publishes ~10 per-section PDFs per year (sections A–K), not one combined file |
| Bates | 27 | 1999-00 → 2025-26 | Complete continuous archive |
| Bowdoin | 25 | 2001-02 → 2025-26 | |
| Brown | 22 | 2004-05 → 2025-26 | Brown's first CDS was 2004-05; older paths return 404 on live site, so older years pulled via Wayback |
| Caltech | 23 | 2002-03 → 2024-25 | Live archive at finance.caltech.edu was complete |
| Colby | 15 | 2000-01 → 2015-16 | Colby stopped publishing CDS publicly after 2015-16 |
| Columbia | 4 | 2021-22 → 2024-25 | Columbia published its first ever CDS in 2021-22 |
| Conn College | 14 | 2012-13 → 2025-26 | Older years (pre-2012) probed but unavailable; Wayback was unreachable from the search environment |
| Cornell | 26 | 1999-00 → 2024-25 | Deepest archive of any school |
| Dartmouth | 23 | 2003-04 → 2025-26 | OIR snapshots from 2001-02 and 2002-03 reference PDFs that the Internet Archive never preserved |
| Duke | 16 | 2008-09 → 2024-25 | Skipped publishing 2022-23; 1 year (2008-09) pulled from a third-party mirror |
| Harvard | 19 | 2006-07 → 2024-25 | Older years probed via Wayback; 2006-07 recovered, no earlier CDS PDFs were ever posted |
| JHU | 11 | 2007-08 → 2024-25 | **7-year gap 2014-15 through 2020-21** — JHU did not publish CDS publicly during that period |
| Middlebury | 21 | 2005-06 → 2025-26 | |
| MIT | 1 PDF + 4 HTML | 1999-00, 2021-22 → 2024-25 | MIT publishes CDS as HTML pages on `ir.mit.edu`, not PDFs (1999-2000 is the one exception ever indexed). [`code/extract_mit_html.py`](../../code/extract_mit_html.py) parses the HTML for 2021-22 onward. |
| Penn | 16 | 2009-10 → 2024-25 | Penn's first CDS was 2009-10; older years confirmed unavailable |
| Princeton | 25 | 2001-02 → 2025-26 | One filename has a "prineton" typo preserved as-is |
| Stanford | 25 | 2001-02 → 2025-26 | Older years (2001-07) recovered from Stanford Digital Repository (`stacks.stanford.edu`) |
| Trinity | 16 | 2009-10 → 2024-25 | |
| Tufts | 14 | 2011-12 → 2024-25 | Tufts started publishing 2011-12; pre-2011 confirmed unavailable |
| UChicago | 4 | 2021-22 → 2024-25 | UChicago refused to publish a CDS for decades; 2021-22 was its first (per *Chicago Maroon*) |
| Wesleyan | 22 | 2001-02 → 2022-23 | 2023-24 onward moved to auth-gated SharePoint `.xlsx` files (no public PDF) |
| Williams | 34 | 1998-99 → 2025-26 | Some years have multiple revisions (March/June, with/without tuition decrease, V1/V2/V5, etc.) — all kept on disk; revision-dedup in [`build_complete.py`](../../code/build_complete.py) picks one winner per year for the project-wide CSVs. |
| Yale | 23 | 2003-04 → 2025-26 | Pre-2008 years recovered by URL probing the OIR sites/files path |
| Barnard | 12 | 2013-14 → 2024-25 | |
| Bryn Mawr | 19 | 2007-08 → 2024-25 | |
| Bucknell | 15 | 2011-12 → 2025-26 | |
| Carleton | 27 | 1999-00 → 2025-26 | Deep continuous archive |
| Clark | 7 | 2010-11 → 2024-25 | Modern years (2024-25, 2022-23) from live site; older years (2010-15) from Wayback |
| Davidson | 1 | 2024-25 only | Only current year is publicly downloadable; historical CDS files are at non-descriptive `davidson.edu/media/<id>/download` URLs that are not enumerable |
| Franklin & Marshall | 5 | 2020-21 → 2024-25 | Live site `_resources/pdfs/` returns HTML for URLs older than 2020-21 (CloudFront serves a JS challenge instead of the PDF on GET); HEAD probes return 200 but GETs are blocked. Older years confirmed to exist in URL pattern but not retrievable without a real browser session. |
| Hampshire | 17 | 2004-05 → 2021-22 | A deeper page on hampshire.edu lists 17 years; 2022-25 not yet indexed there. |
| Haverford | 19 | 2003-04 → 2024-25 | Most historical years recovered from Wayback CDX of `haverford.edu/sites/default/files/Office/President/`. |
| Macalester | 11 | 2013-14 → 2024-25 | |
| Mount Holyoke | 28 | 1998-99 → 2025-26 | All historical PDFs sit in a public Google Drive folder. The `embeddedfolderview` endpoint exposes file IDs without auth, allowing a full enumeration. |
| Oberlin | 3 | 2022-23 → 2024-25 | 2018-22 published as `.xlsx` files (4 files in dir, ignored by extractor) — extractor processes only `.pdf` |
| Pomona | 18 | 2006-07 → 2023-24 | 2017-23 served from `pomona.box.com/shared/static/<token>.pdf`; older years from `pomona.edu/sites/default/files/` |
| Reed | 14 | 2011-12 → 2024-25 | Section-per-PDF publishing — only Section B (enrollment) is downloaded, since that's what contains B2 |
| Sarah Lawrence | 5 | 2019-20 → 2024-25 | 2020-21 from Wayback; rest from live site. Pre-2019 not publicly indexed. |
| Smith | 13 | 2010-11 → 2022-23 | Continuous coverage; URL pattern enabled probing for missing years |
| St. Olaf | 3 | 2021-22 → 2025-26 | Section-per-PDF publishing — only Section B downloaded. 2024-25 hosted on Google Drive. Pre-2021 sections were probed but URL patterns vary year-to-year. |
| Swarthmore | 26 | 2000-01 → 2025-26 | Older years on `archive.swarthmore.edu` are served behind a PDF.js viewer; the binary is reachable by appending `?__raw=1` to the URL. |
| Union | 7 | 2014-15 → 2024-25 | Some years are partial (`-section.pdf` files contain only some sections, not the full CDS) |
| Vassar | 21 | 2003-04 → 2024-25 | Most years from Wayback; current year from live |
| Washington & Lee | 27 | 1999-00 → 2025-26 | Deep continuous archive |
| Wellesley | 20 | 2006-07 → 2025-26 | |

**Total: ~1080 PDFs across 47 schools** (plus 4 MIT HTML pages parsed by `extract_mit_html.py`).

## How the older years were found

Schools commonly remove older CDS PDFs from their live institutional-research pages. Several techniques together filled most of the historical gaps:

1. **Wayback Machine CDX API.** Querying
   `https://web.archive.org/cdx/search/cdx?url=<host>&matchType=prefix&output=json&filter=mimetype:application/pdf`
   for each school's IR domain returns every PDF URL the Internet Archive ever crawled there. Filtering for "cds", "common", or "data" in the URL surfaced files that no longer existed on the live server.
2. **Wayback raw-bytes endpoint.** `https://web.archive.org/web/<TIMESTAMP>id_/<URL>` returns the original archived bytes (the `id_` modifier strips the Wayback wrapper). This was used for Brown (entire collection), Harvard's 2006-07, Duke's 2009-2019, JHU's 2007-2013, Williams (entire collection — Cloudflare blocks the live origin), Yale's 2003-04, and others.
3. **Snapshots of the canonical CDS landing page** from ~2008/2010/2015. Old versions of the page often listed PDFs that have since been pruned. Brown's 2020 snapshot, for example, listed the same 16 years that are still on its live page now — confirming Brown has never published anything older than 2004-05.
4. **URL probing of predictable filename patterns.** Yale's older `cds_YYYY-YY.pdf` files were stored at `oir.yale.edu/sites/default/files/...` even though the canonical page didn't link them; once the pattern was known, all five missing years (2003-07) downloaded cleanly. Princeton's compressed-year pattern (`cds_NNNN_princeton.pdf`) similarly let the agent walk the entire 2001-2025 range from a single URL template.
5. **Third-party / institutional repository alternatives.** Stanford's pre-2008 CDS PDFs are no longer at `ucomm.stanford.edu` but are preserved in the Stanford Digital Repository under druid `yt471fb0077`. Duke 2008-09 came from `thecollegesolution.com`'s archive after no Duke-hosted snapshot survived.

## What couldn't be retrieved

A handful of files exist somewhere but were not retrievable to local disk:

- **JHU's 2025-26 CDS PDF** is linked from `oira.jhu.edu`, but the file URL is behind Cloudflare bot protection and was never archived. Only retrievable through a real browser session.
- **Dartmouth 2001-02 and 2002-03**: published per Wayback snapshots of the OIR `dataset.html` index, but the PDFs themselves were never crawled by the Internet Archive.
- **MIT's annual CDS** (other than 1999-2000): MIT renders the CDS as HTML pages on `ir.mit.edu`, with no PDF/Excel download. The 2021-22 → 2024-25 B2 tables are now parsed directly from those HTML pages by [`code/extract_mit_html.py`](../../code/extract_mit_html.py); 2025-26 isn't yet posted, and 2000-01 through 2020-21 don't appear to have ever been published in any form.
- **Wesleyan 2023-24 and 2024-25**: hosted on a SharePoint share requiring a Wesleyan account. The `.xlsx` files are not publicly downloadable.
- **JHU 2014-15 through 2020-21** (7 years): exhaustive Wayback CDX queries across `oir.jhu.edu`, `oira.jhu.edu`, `web.jhu.edu/registrar`, `studentaffairs.jhu.edu/registrar`, `provost.jhu.edu` confirmed no CDS PDFs were ever posted during that period — consistent with JHU's documented withdrawal from public CDS publication for those years.
- **Franklin & Marshall historical CDS (pre-2020)**: 13 PDFs at `fandm.edu/_resources/pdfs/IR_CDS_YYYY-YY.pdf` show 200 on HEAD but return HTML on GET (similar CDN/bot-protection pattern as Swarthmore).
- **Davidson historical CDS**: stored at non-descriptive `davidson.edu/media/<id>/download` URLs (where `<id>` is a numeric ID with no year information). Without an enumerable index, only the current 2024-25 file (id 9718) is retrievable.
