# /// script
# requires-python = ">=3.11"
# ///
"""Build SAT-derived CSVs from the College Board 2025 Total Group Annual
Report (documents/11_collegeboard_sat_2025_annual_report.pdf):

  - data/processed/sat_scores.csv      — long-format score-band × race grid
                                         (year, score_range, race,
                                          test_takers, percent, count)
  - data/processed/sat_mean_scores.csv — mean total score by race
                                         (year, race, test_takers,
                                          mean_total_score)

For sat_scores.csv, `count` is the implied number of test-takers
(test_takers × percent / 100), rounded to integer. Percentages are
reported as whole-number percents in the source PDF, so column totals
sum to 100% only approximately (off by 1–2 percentage points in some rows
due to rounding).

Run:
    uv run code/build_sat_scores.py
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_SCORES = ROOT / "data" / "processed" / "sat_scores.csv"
OUT_MEANS  = ROOT / "data" / "processed" / "sat_mean_scores.csv"

YEAR = 2025

# Top row of the source table — total test-takers by race.
TEST_TAKERS = {
    "Total":             2_004_965,
    "American Indian":   9_237,
    "Asian":             217_459,
    "African American":  250_887,
    "Hispanic":          537_624,
    "Native Hawaiian":   3_053,
    "White":             743_981,
    "Two or More Races": 82_032,
}

# Race column order in the source table.
RACES = [
    "Total",
    "American Indian",
    "Asian",
    "African American",
    "Hispanic",
    "Native Hawaiian",
    "White",
    "Two or More Races",
]

# Score-band rows: (score_range, [percentages in RACES order]).
SCORE_RANGES = [
    ("1400-1600", [ 7,  1, 26,  1,  2,  1,  7,  9]),
    ("1200-1390", [18,  6, 33,  7,  9,  9, 23, 21]),
    ("1000-1190", [28, 18, 25, 21, 24, 23, 35, 30]),
    ("800-990",   [30, 40, 13, 40, 39, 38, 27, 28]),
    ("600-790",   [14, 31,  3, 26, 22, 24,  7,  9]),
    ("400-590",   [ 3,  6,  0,  5,  4,  4,  1,  1]),
]

# Mean total SAT score by race, from the per-race summary table in the same
# report. "No Response" is reported separately and represents test-takers
# who did not supply a race/ethnicity. Source totals add up to 2,004,965
# (matches the score-band table's Total row).
MEAN_TOTAL_SCORES = {
    "American Indian":   (    9_237,  874),
    "Asian":             (  217_459, 1229),
    "African American":  (  250_887,  904),
    "Hispanic":          (  537_624,  928),
    "Native Hawaiian":   (    3_053,  922),
    "White":             (  743_981, 1077),
    "Two or More Races": (   82_032, 1073),
    "No Response":       (  160_692, 1055),
}

# Score-band midpoints in the same order as SCORE_RANGES above (1400-1600
# capped, others nominally 200-wide).
BAND_MIDPOINTS = [1500, 1295, 1095, 895, 695, 495]

# Sheppard's correction for grouped data with equal class width w. For
# bell-shaped continuous data binned into equal-width classes, the
# midpoint-based variance overstates the true variance by w²/12. Validated
# against the overall pool below: midpoint variance (≈ 58,961) minus
# Sheppard's (3,333) gives an SD of ≈ 235.9 vs. the reported 235.
SHEPPARD = 200 ** 2 / 12


def write_score_distribution() -> int:
    OUT_SCORES.parent.mkdir(parents=True, exist_ok=True)
    with OUT_SCORES.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["year", "score_range", "race",
                    "test_takers", "percent", "count"])
        for score_range, pcts in SCORE_RANGES:
            for race, pct in zip(RACES, pcts):
                takers = TEST_TAKERS[race]
                count = round(takers * pct / 100)
                w.writerow([YEAR, score_range, race, takers, pct, count])
    return len(SCORE_RANGES) * len(RACES)


def estimate_sd_for_race(race: str) -> float | None:
    """Sheppard's-corrected SD estimate from the per-race score-band
    percentages. Returns None if the race has no score-band data
    (e.g. 'No Response', which isn't broken down by score)."""
    if race not in RACES:
        return None
    i = RACES.index(race)
    pcts = [row[1][i] for row in SCORE_RANGES]
    pct_sum = sum(pcts)
    if pct_sum == 0:
        return None
    # Renormalize: source percentages are reported as integers, so per-race
    # rows sum to 98-102% rather than exactly 100% due to rounding.
    weights = [p / pct_sum for p in pcts]
    mean_mid = sum(w * m for w, m in zip(weights, BAND_MIDPOINTS))
    var_mid = sum(w * (m - mean_mid) ** 2
                  for w, m in zip(weights, BAND_MIDPOINTS))
    var_corrected = var_mid - SHEPPARD
    return var_corrected ** 0.5 if var_corrected > 0 else None


def write_mean_scores() -> int:
    OUT_MEANS.parent.mkdir(parents=True, exist_ok=True)
    with OUT_MEANS.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["year", "race", "test_takers",
                    "mean_total_score", "sd_total_score"])
        for race, (takers, mean) in MEAN_TOTAL_SCORES.items():
            sd = estimate_sd_for_race(race)
            sd_cell = f"{round(sd)}" if sd is not None else ""
            w.writerow([YEAR, race, takers, mean, sd_cell])
    return len(MEAN_TOTAL_SCORES)


def main() -> None:
    n_scores = write_score_distribution()
    print(f"Wrote {n_scores} rows to {OUT_SCORES.relative_to(ROOT)}")

    # Sanity check on score distribution: per-race percents should sum to
    # ~100 (off by 1-2 from rounding in the source PDF).
    print("  per-race percent sums (source rounding may give 98-102):")
    for i, race in enumerate(RACES):
        total_pct = sum(row[1][i] for row in SCORE_RANGES)
        print(f"    {race:<20} {total_pct}%")

    n_means = write_mean_scores()
    print(f"Wrote {n_means} rows to {OUT_MEANS.relative_to(ROOT)}")

    # Sanity-check Sheppard's correction against the reported overall SD (235).
    total_sd = estimate_sd_for_race("Total")
    print(f"  Sheppard sanity-check: Total SD estimate = "
          f"{total_sd:.1f} (reported: 235)")


if __name__ == "__main__":
    main()
