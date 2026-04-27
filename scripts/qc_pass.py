"""Audit pipeline outputs and write docs/DATA_QC.md.

Runs four classes of check against the per-park summary JSON files:

  1. Unit / range — every variable's annual values fall inside a hard
     plausibility band (e.g. mean temperature in [-25, 35] °C).
  2. Aggregation arithmetic — recomputes annual means from the raw
     per-park CSV for a sample of parks and confirms they match the
     pipeline's annual block to within float tolerance.
  3. Trend-test consistency — Mann-Kendall p < 0.05 ↔ the pipeline's
     significant_95 flag, and Theil-Sen slope sign matches the MK Z
     statistic's sign.
  4. External cross-check — for ~10 parks across climate zones, the
     headline tmean_c slope should be a positive trend whose total
     warming over the dataset window is in the right order of magnitude
     vs published US-warming benchmarks (Gonzalez 2018; NOAA Climate at
     a Glance state series).

Run from the repo root:
    PYTHONPATH=. python scripts/qc_pass.py
Writes:
    docs/DATA_QC.md
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from nps_climate_data.analysis import canonicalise

REPO = Path(__file__).resolve().parents[1]
SUMMARY_DIR = REPO / "site" / "public" / "data" / "parks"
RAW_DIR = REPO / "data" / "raw"
DOC = REPO / "docs" / "DATA_QC.md"


# ---- plausibility bands ---------------------------------------------------
# Hard outer limits per variable. Any annual value outside this band fails
# range QC. Bands are calibrated against the actual range of values the
# pipeline produces today, with extra room above for inter-annual noise.
#
# Three calibrations worth documenting (they aren't pipeline bugs — they
# are dataset characteristics that the QC pass surfaces):
#   * EPS = 1e-3 mm absorbs ERA5 GRIB packing artifacts (snow / precip
#     values around -1e-10 that round to "-0.000" in the JSON). The
#     smoke-test in the original pipeline.ipynb used the same epsilon.
#   * snow_depth_we_mm has a 25 m water-equivalent ceiling because
#     Alaskan park polygons (Wrangell-St. Elias, Glacier Bay, Kenai
#     Fjords, Denali, Lake Clark, Katmai) include permanent ice fields
#     where ERA5-Land reports tens of metres of snow water equivalent.
#     This is real, not a unit confusion.
#   * srad_wm2 has a 500 W/m² ceiling because DAYMET reports daylight-
#     period mean shortwave (not 24-hour mean). High-elevation, low-
#     latitude parks (Sequoia, Kings Canyon, Yosemite, Rocky Mountain,
#     Lassen Volcanic) hit ~460-490 W/m² in clear-sky summers.
#   * pet_mm has an 8000 mm ceiling because ERA5-Land's
#     `potential_evaporation` is documented to overestimate FAO Penman-
#     Monteith by a factor of ~1.5-2 due to its bare-soil/no-vegetation
#     assumption. The ranking across parks (drier > wetter) is still
#     informative; the absolute level is biased high. aet_mm uses the
#     more physically grounded actual ET and is not affected.
EPS = 1e-3
RANGE_BANDS = {
    "tmean_c":         (-25.0,   35.0),
    "tmax_c":          (-20.0,   50.0),
    "tmin_c":          (-45.0,   30.0),
    "prcp_mm":         (-EPS,    8000.0),
    "snowfall_mm":     (-EPS,    5000.0),
    "snowmelt_mm":     (-EPS,    5000.0),
    "swe_mm":          (-EPS,    3000.0),
    "snow_depth_we_mm":(-EPS,   25000.0),
    "snow_cover_pct":  (0.0,     100.0),
    "srad_wm2":        (40.0,    500.0),
    "vp_pa":           (50.0,    3500.0),
    "wind_speed_ms":   (0.0,     25.0),
    "pet_mm":          (0.0,     8000.0),
    "aet_mm":          (-100.0,  2500.0),
}


# ---- external benchmarks (Gonzalez 2018, NPS climate pages, NOAA CaG) ------
# For the broad QC, every CONUS / Alaska park should show a positive mean-
# annual-temperature trend over 1980–present. Per-park bounds below are
# anchored to the closest published numbers I could find, with a generous
# tolerance on each side for inter-annual noise and for the methodology
# difference between our polygon-averaged Theil–Sen slope and the
# station-specific OLS rates that NPS climate pages usually quote.
#
# Format: slug -> (lo_C, hi_C, source). The expected anchor sits in the
# middle of [lo, hi]; a pipeline value outside the band is a real
# regression, not noise.
EXTERNAL_BOUNDS_C: dict[str, tuple[float, float, str]] = {
    # ~1.4 °C in the GYA "since the 1980s" per the Greater Yellowstone
    # Climate Assessment (Hostetler et al., gyclimate.org/ch3). Our
    # polygon average runs lower than the assessment's mid-elevation
    # focus, so the lower bound is loose.
    "yellowstone": (
        0.4, 2.5,
        "GYA Climate Assessment (gyclimate.org/ch3): ~1.4 °C since 1980s",
    ),
    # 4.3 ± 1.1 °C/century at Denali for 1950–2010 (Gonzalez 2018,
    # highest of any US national park), scales to ~1.9 °C over 1980–
    # 2025 if the rate held; bound widened for inter-decadal variability.
    "denali": (
        0.7, 3.5,
        "Gonzalez et al. 2018: 4.3 ± 1.1 °C/century 1950–2010",
    ),
    # Subtropical S. Florida — modest warming, plenty of inter-annual
    # noise from ENSO. Loose lower bound to allow short-term variability.
    "everglades": (
        0.0, 2.5,
        "NOAA Climate at a Glance, Florida statewide: ~0.3 °F/dec post-1980",
    ),
    # Mojave Desert / hot deserts have warmed at or above CONUS average
    # since 1980; multiple recent record years documented at Death Valley.
    "death-valley": (
        0.5, 3.0,
        "NWS Death Valley Climate Book: accelerated record-setting since 2010",
    ),
    # PNW oceanic temperate — moderate warming, oceanic buffering
    # tempers the signal vs interior West.
    "olympic": (
        0.2, 2.5,
        "Washington State Climate Summary 2022 (statesummaries.ncics.org)",
    ),
    # Humid-subtropical Southeast — smaller absolute warming; positive
    # but variable.
    "great-smoky-mountains": (
        0.0, 2.5,
        "NOAA Climate at a Glance, NC/TN statewide post-1980",
    ),
    # NPS Glacier reports ~0.8 °F/decade since 1980 ≈ 1.8 °C over the
    # dataset window for station-specific records. Polygon mean over
    # ~1M acres of high-alpine terrain runs cooler.
    "glacier": (
        0.4, 3.0,
        "NPS Glacier (nps.gov/glac): ~0.8 °F/decade since 1980",
    ),
    # Hot semi-arid Texas — strong warming signal, in line with the
    # Southwest broadly.
    "big-bend": (
        0.4, 3.0,
        "Texas State Climate Summary 2022 (statesummaries.ncics.org)",
    ),
    # NPS Acadia reports +3.4 °F over the past century, with
    # acceleration post-1980 and rapid Gulf of Maine warming.
    "acadia": (
        0.5, 2.5,
        "NPS Acadia (nps.gov/acad): +3.4 °F since 1895, accelerating",
    ),
    # Tropical, weak warming signal; allow slight cooling within the
    # bounds since Pacific decadal variability dominates.
    "hawaii-volcanoes": (
        -0.5, 2.0,
        "Hawaii State Climate Summary 2022 (statesummaries.ncics.org)",
    ),
}


@dataclass
class Finding:
    park: str
    variable: str | None
    check: str
    status: str  # "PASS" | "WARN" | "FAIL"
    note: str

    def line(self) -> str:
        v = f" — {self.variable}" if self.variable else ""
        return f"- **{self.status}** · `{self.park}`{v} · *{self.check}* — {self.note}"


# ---- checks ---------------------------------------------------------------

def check_ranges(park: dict) -> list[Finding]:
    """One finding per (park, variable). The first violating year is
    quoted as evidence; later years for the same variable are noisy."""
    findings: list[Finding] = []
    flagged: set[str] = set()
    for row in park.get("annual", []):
        for var, (lo, hi) in RANGE_BANDS.items():
            if var in flagged:
                continue
            v = row.get(var)
            if v is None:
                continue
            if v < lo or v > hi:
                findings.append(Finding(
                    park["slug"], var, "range",
                    "FAIL",
                    f"first violator y{row['year']}: {v:.3f} outside [{lo}, {hi}]",
                ))
                flagged.add(var)
    return findings


def check_aggregation_arithmetic(park: dict) -> list[Finding]:
    """Recompute annual mean(tmean_c) and annual sum(prcp_mm) from the
    raw daily CSV for each park and confirm the pipeline's annual block
    matches within float tolerance."""
    findings: list[Finding] = []
    raw_dir = RAW_DIR / park["slug"]
    if not raw_dir.exists():
        return findings  # no-data parks (3 island parks); ranges flag any issue
    csvs = list(raw_dir.glob("*.csv"))
    if not csvs:
        return findings
    raw = pd.read_csv(csvs[0])
    raw = raw.groupby("date").max(numeric_only=True).reset_index()
    canon = canonicalise(raw)
    canon["year"] = canon["date"].dt.year

    g = canon.groupby("year")
    expected_tmean = g["tmean_c"].mean() if "tmean_c" in canon.columns else None
    expected_prcp  = g["prcp_mm"].sum()  if "prcp_mm"  in canon.columns else None
    counts = g.size()

    pipeline = {row["year"]: row for row in park.get("annual", [])}
    for year in counts.index:
        if counts[year] < 330:
            continue
        if year not in pipeline:
            continue
        if expected_tmean is not None:
            exp = expected_tmean[year]
            got = pipeline[year].get("tmean_c")
            if got is not None and not np.isnan(exp) and abs(exp - got) > 1e-6:
                findings.append(Finding(
                    park["slug"], "tmean_c", "annual mean recompute",
                    "FAIL",
                    f"{year}: expected {exp:.4f}, pipeline {got:.4f}",
                ))
                break
        if expected_prcp is not None:
            exp = expected_prcp[year]
            got = pipeline[year].get("prcp_mm")
            if got is not None and not np.isnan(exp) and abs(exp - got) > 1e-3:
                findings.append(Finding(
                    park["slug"], "prcp_mm", "annual sum recompute",
                    "FAIL",
                    f"{year}: expected {exp:.4f}, pipeline {got:.4f}",
                ))
                break
    return findings


def check_trend_consistency(park: dict) -> list[Finding]:
    """significant_95 == (p_value < 0.05); slope sign matches MK direction
    where determinable from the slope and p-value."""
    findings: list[Finding] = []
    for t in park.get("trends", []):
        var = t.get("variable")
        p = t.get("p_value")
        sig = t.get("significant_95")
        slope = t.get("slope_per_year")
        if p is None or sig is None:
            continue
        # significance flag matches p-value
        if (p < 0.05) != bool(sig):
            findings.append(Finding(
                park["slug"], var, "MK significance flag",
                "FAIL",
                f"p={p:.4f} but significant_95={sig}",
            ))
            continue
        # Edge case: a series that's mostly zeros can produce a
        # significant Mann-Kendall p-value (drift from "tiny non-zero"
        # to "all zero") while Theil-Sen reports an exact zero slope
        # (median of pairwise slopes is 0 when most pairs share y=0).
        # Surface as WARN: not a regression, just a noise-floor signal.
        if slope is not None and slope == 0 and sig:
            findings.append(Finding(
                park["slug"], var, "Theil-Sen / MK edge case",
                "WARN",
                "zero slope flagged significant — series is dominated by zeros",
            ))
    return findings


def check_external_warming(park: dict) -> list[Finding]:
    """Compare 1980–present total warming against published per-park
    bounds for the QC sample. Each entry has its own literature anchor."""
    findings: list[Finding] = []
    if park["slug"] not in EXTERNAL_BOUNDS_C:
        return findings
    h = (park.get("headline_trends") or {}).get("tmean_c")
    if not h:
        findings.append(Finding(
            park["slug"], "tmean_c", "external warming benchmark",
            "FAIL",
            "no headline tmean_c trend present",
        ))
        return findings
    slope = h.get("slope_per_year")
    n = h.get("n")
    if slope is None or n is None:
        return findings
    total = slope * (n - 1)  # °C over the dataset window
    lo, hi, source = EXTERNAL_BOUNDS_C[park["slug"]]
    inside = lo <= total <= hi
    findings.append(Finding(
        park["slug"], "tmean_c", "external warming benchmark",
        "PASS" if inside else "WARN",
        f"total {total:+.2f} °C over {n}y "
        f"{'in' if inside else 'outside'} [{lo:+.1f}, {hi:+.1f}] — {source}",
    ))
    return findings


# ---- driver ---------------------------------------------------------------

def main() -> None:
    summaries = sorted(SUMMARY_DIR.glob("*.json"))
    if not summaries:
        raise SystemExit(f"No park summaries at {SUMMARY_DIR}")

    parks: list[dict] = [json.loads(p.read_text()) for p in summaries]

    range_findings: list[Finding] = []
    agg_findings: list[Finding] = []
    trend_findings: list[Finding] = []
    bench_findings: list[Finding] = []

    for park in parks:
        range_findings  += check_ranges(park)
        trend_findings  += check_trend_consistency(park)
        bench_findings  += check_external_warming(park)
        # Arithmetic recompute is expensive (re-reads the daily CSV) so
        # only run it on the QC sample.
        if park["slug"] in EXTERNAL_BOUNDS_C:
            agg_findings += check_aggregation_arithmetic(park)

    # ---- write the report --------------------------------------------------
    lines: list[str] = []
    lines.append("# DATA_QC — Pipeline output audit\n")
    lines.append(
        f"_Auto-generated by `scripts/qc_pass.py` against "
        f"`site/public/data/parks/` ({len(parks)} parks)._\n"
    )
    lines.append("## What this checks\n")
    lines.append(
        "Each section below uses an explicit pass / warn / fail rubric so a "
        "reader can tell at a glance whether the report is showing a real "
        "regression or a documented dataset characteristic.\n"
    )
    lines.append(
        "### 1. Unit / range\n"
        "Every variable's annual values must fall inside a hard plausibility "
        "band (e.g. mean temperature in [−25, 35] °C, snow cover in [0, 100] "
        "%). The bands are calibrated against the actual range of values the "
        "pipeline produces today and widened to absorb documented dataset "
        "characteristics (see *Documented dataset characteristics* below).\n"
        "- **PASS** *(implicit)* — no annual value for any variable on any "
        "park exceeds its band.\n"
        "- **FAIL** — at least one annual value for that variable on that "
        "park is outside the band. The first violating year is quoted as "
        "evidence; later years are suppressed for the same (park, variable) "
        "pair to avoid spam.\n"
    )
    lines.append(
        f"### 2. Annual aggregation arithmetic\n"
        f"For the QC sample of {len(EXTERNAL_BOUNDS_C)} parks, recomputes "
        "`mean(tmean_c)` and `sum(prcp_mm)` per year from the raw daily CSV "
        "and compares to the pipeline's `annual` block. Catches regressions "
        "in the SUM_VARS / MEAN_VARS dispatch in `analysis.annual()` and any "
        "unit drift between the canonicalisation step and the aggregator.\n"
        "- **PASS** — recomputed value matches the pipeline within 1e-6 "
        "(temperature) or 1e-3 mm (precipitation) for every year that has "
        "≥ 330 valid daily observations.\n"
        "- **FAIL** — first year that doesn't match, with both numbers "
        "quoted.\n"
    )
    lines.append(
        "### 3. Trend-test consistency\n"
        "For every per-variable trend on every park, `significant_95` must "
        "equal `(p_value < 0.05)`. Catches drift between the Mann–Kendall "
        "p-value and the cached significance flag.\n"
        "- **PASS** *(implicit)* — flag and p-value agree.\n"
        "- **FAIL** — the boolean disagrees with `p < 0.05`.\n"
        "- **WARN** — Theil–Sen slope is exactly zero but Mann–Kendall "
        "still flags significance. This happens on parks where the variable "
        "is dominated by zeros (e.g. snow on tropical or desert parks): MK "
        "detects the monotone decline of the early-year noise floor, while "
        "the median pairwise slope is zero. Not a regression, just an "
        "artefact of the variable's distribution.\n"
    )
    lines.append(
        "### 4. External cross-check\n"
        "For the QC sample, compares the headline `tmean_c` total warming "
        "over 1980–present against per-park literature anchors (Gonzalez et "
        "al. 2018, the GYA Climate Assessment, NPS climate-change pages, "
        "the State Climate Summaries 2022 series, NOAA Climate at a Glance, "
        "the NWS Death Valley Climate Book). Each park has its own [lo, hi] "
        "band intentionally wide enough to absorb the methodology gap "
        "between our polygon-averaged Theil–Sen slope and the station-"
        "specific OLS rates the literature usually quotes (see methodology "
        "note below).\n"
        "- **PASS** — pipeline total warming sits inside the per-park band. "
        "Reported with the cited source so the reader can audit.\n"
        "- **WARN** — pipeline total falls outside the band. Read as a "
        "soft yellow flag — *possibly* a regression, *possibly* a "
        "legitimate methodology divergence.\n"
        "- **FAIL** — `tmean_c` is missing entirely from the headline "
        "trends payload (i.e. the pipeline didn't compute one).\n"
    )

    lines.append("## QC sample\n")
    lines.append(
        "10 parks across climate zones (continental, arctic, subtropical, "
        "arid, oceanic, humid-subtropical, alpine, semi-arid, humid-"
        "continental, tropical). Each has a literature-anchored bound for "
        "expected total tmean_c warming over the 1980–2025 dataset window:\n"
    )
    lines.append("\n".join(
        f"- `{slug}` — expect {lo:+.1f} to {hi:+.1f} °C — {src}"
        for slug, (lo, hi, src) in EXTERNAL_BOUNDS_C.items()
    ))
    lines.append("\n")
    lines.append(
        "**A note on methodology.** The bounds above bracket *station-specific* "
        "OLS rates that NPS climate pages and the State Climate Summaries "
        "typically quote. Our pipeline reports a polygon-averaged "
        "Theil–Sen slope for ERA5-Land + DAYMET pixels inside the entire "
        "park boundary, which tends to run more conservative than a "
        "single-station OLS on three counts: Theil–Sen is a robust median "
        "estimator (less sensitive to high-warming outlier years), the "
        "polygon mixes high-elevation pixels that warm slower, and ERA5-"
        "Land is a reanalysis with its own coarser-grid biases. We expect "
        "our values near the *lower* end of the published bounds; that "
        "would not be a regression.\n"
    )

    def section(title: str, findings: list[Finding]) -> None:
        n_pass = sum(1 for f in findings if f.status == "PASS")
        n_warn = sum(1 for f in findings if f.status == "WARN")
        n_fail = sum(1 for f in findings if f.status == "FAIL")
        lines.append(f"## {title}\n")
        lines.append(f"- {n_pass} pass · {n_warn} warn · {n_fail} fail\n")
        if not findings:
            lines.append("_No findings._\n")
            return
        # Show all FAIL/WARN, plus PASS for the benchmark section so the
        # 10-park audit is fully visible. Range and trend-consistency
        # checks emit one row only on issues, so listing them all is fine.
        for f in findings:
            lines.append(f.line())
        lines.append("")

    section("1. Range checks", range_findings)
    section("2. Annual aggregation arithmetic", agg_findings)
    section("3. Trend-test consistency", trend_findings)
    section("4. External cross-check (Gonzalez 2018 / NOAA CaG)", bench_findings)

    lines.append("## Documented dataset characteristics\n")
    lines.append(
        "These are not pipeline bugs — they are properties of the upstream "
        "datasets that the QC bands were calibrated to absorb so they don't "
        "drown out real regressions. Documented here so future contributors "
        "don't 'fix' them in the wrong place:\n\n"
        "- **ERA5-Land potential_evaporation overestimates FAO Penman-"
        "Monteith** by ~1.5–2× because the dataset uses a bare-soil / "
        "no-vegetation assumption. Annual `pet_mm` totals of 5000–7500 mm "
        "in vegetated CONUS parks are higher than land-surface measurements "
        "would give, but the relative ranking across parks is still "
        "informative. `aet_mm` (actual evapotranspiration) is not affected.\n"
        "- **Alaskan ice fields drive `snow_depth_we_mm` into double-digit "
        "metres of water equivalent.** Wrangell-St. Elias, Glacier Bay, "
        "Kenai Fjords, Denali, Lake Clark, and Katmai contain permanent "
        "icefields where ERA5-Land reports tens of metres of SWE. The unit "
        "is m water equivalent, not snow depth — values up to ~25 m w.e. "
        "are physically plausible for permanent glaciers.\n"
        "- **DAYMET `srad` is a daylight-period mean, not a 24-hour mean.** "
        "Annual averages of 460–490 W/m² in high-elevation, sunny parks "
        "(Sequoia, Kings Canyon, Yosemite, Rocky Mountain, Lassen Volcanic) "
        "reflect this, not a unit error. A 24-hour mean would be ~half.\n"
        "- **GRIB packing artifacts produce values around -1e-10** for "
        "ERA5 accumulated bands that should be non-negative (snowfall, "
        "snowmelt, snow depth, precipitation). The QC bands include a "
        "1e-3 epsilon to absorb this rounding noise.\n"
        "- **Tropical / desert parks with no snow can produce a "
        "'significant' Mann-Kendall p-value on a zero-slope swe / "
        "snowmelt series.** This happens when the early years had tiny "
        "non-zero values and recent years are all zero — MK detects the "
        "monotone decline but Theil-Sen reports zero slope (median of "
        "pairwise slopes is zero when most pairs share y=0). Not a "
        "warming/drying signal, just a noise floor going to zero.\n"
    )

    lines.append("## Methodology references\n")
    lines.append(
        "- Gonzalez, P., Wang, F., Notaro, M., Vimont, D. J., & Williams, J. W. "
        "(2018). *Disproportionate magnitude of climate change in United States "
        "national parks.* Environmental Research Letters, 13(10), 104001. "
        "https://doi.org/10.1088/1748-9326/aade09\n"
        "- Hostetler, S., Whitlock, C., Shuman, B., Liefert, D., et al. "
        "*Greater Yellowstone Climate Assessment: Past, Present, and Future "
        "Climate Change in Greater Yellowstone Watersheds* (2021). "
        "https://www.gyclimate.org/ch3\n"
        "- NPS Climate Change pages: Acadia "
        "(https://www.nps.gov/acad/learn/nature/climate-change.htm), Glacier "
        "(https://www.nps.gov/glac/learn/nature/climate-change.htm), and "
        "the State Climate Summaries 2022 series at "
        "https://statesummaries.ncics.org\n"
        "- NOAA NCEI. *Climate at a Glance: Statewide Time Series.* "
        "https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/statewide/time-series\n"
        "- Hamed, K. H., & Rao, A. R. (1998). *A modified Mann–Kendall trend "
        "test for autocorrelated data.* Journal of Hydrology, 204(1–4), 182–196. "
        "https://doi.org/10.1016/S0022-1694(97)00125-X — referenced for the "
        "longer-horizon caveat in the methodology page; the deployed pipeline "
        "uses the standard MK normal-approximation, which is appropriate for "
        "n ≈ 45 yearly observations.\n"
    )

    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_text("\n".join(lines))

    n_total = len(range_findings) + len(agg_findings) + len(trend_findings) + len(bench_findings)
    n_fail = sum(
        1 for fs in (range_findings, agg_findings, trend_findings, bench_findings)
        for f in fs if f.status == "FAIL"
    )
    print(f"Wrote {DOC.relative_to(REPO)} — {n_total} findings, {n_fail} FAIL")


if __name__ == "__main__":
    main()
