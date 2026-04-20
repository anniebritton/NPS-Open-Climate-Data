"""
Transparent, order-of-magnitude carbon footprint estimator for the
NPS Open Climate Data project.

Everything here is an *estimate*. Values are published intentionally so
that researchers can audit assumptions and users can see that digital
climate dashboards are not free. Numbers come from public sources and are
rounded generously; see the methodology page on the site for citations.

Scopes covered:
  1. Earth Engine batch exports (compute + egress)
  2. Local analysis (Python processing)
  3. Claude API usage while building the site
  4. Static hosting on GitHub Pages
  5. Average page view on a user's browser

All outputs are in grams of CO2-equivalent.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict


# ---- assumptions (all order-of-magnitude; documented in the site) --------

# Average grid intensity (gCO2e / kWh). Global 2023 ~ 480 g; Google Cloud's
# reported regional average is ~300 g. We use 400 g as a conservative middle.
GRID_INTENSITY_G_PER_KWH = 400.0

# Earth Engine: we don't have exact per-job energy, so we approximate by
# assuming 1 CPU-hour on a shared server ~ 15 Wh (covers CPU + cooling +
# amortised hardware). A full national-park batch (63 parks, ~45 years of
# daily data, ~6 chunks each) is dominated by I/O and reductions. We
# budget 2 CPU-minutes per park per chunk for DAYMET+ERA5.
EE_CPU_MIN_PER_PARK_CHUNK = 2.0
EE_CHUNKS_PER_PARK = 9  # 1980-2024 at 5-year chunks
EE_WH_PER_CPU_HR = 15.0

# Egress: ~200 MB raw CSV/parquet per park (pre-compression). 63 parks ~ 13 GB.
# Estimate 50 Wh / GB end-to-end (Aslan et al., 2017, updated).
EGRESS_WH_PER_GB = 50.0
RAW_MB_PER_PARK = 200.0

# Local Python analysis: trend tests, aggregates. ~30s CPU per park at
# ~20 W laptop draw.
LOCAL_CPU_SEC_PER_PARK = 30.0
LOCAL_POWER_W = 20.0

# Claude API usage during build. Estimated from session transcript:
# ~300k input tokens + ~60k output tokens for Opus-class runs.
# Anthropic's 2024 disclosures and independent estimates (Luccioni et al.)
# put LLM inference at roughly 2-4 Wh per 1k output tokens for large models,
# and ~0.2 Wh per 1k input tokens (input is much cheaper).
CLAUDE_INPUT_WH_PER_KT = 0.2
CLAUDE_OUTPUT_WH_PER_KT = 3.0

# GitHub Pages hosting: very low; ~0.05 kWh per GB served, and we expect
# ~5 MB per page view amortised, serving up to ~10k views / month.
PAGES_WH_PER_GB_SERVED = 50.0

# Average page view on the user's browser: ~1 minute, phone at 2 W, plus
# ~5 MB of network transfer.
VIEW_SECONDS = 60.0
VIEW_DEVICE_W = 2.0
VIEW_MB = 5.0


def _wh_to_g(wh: float) -> float:
    return wh * GRID_INTENSITY_G_PER_KWH / 1000.0


@dataclass
class CarbonBreakdown:
    ee_processing_g: float
    ee_egress_g: float
    local_analysis_g: float
    claude_api_g: float
    hosting_per_month_g: float
    per_view_g: float

    def total_build_g(self) -> float:
        return (
            self.ee_processing_g
            + self.ee_egress_g
            + self.local_analysis_g
            + self.claude_api_g
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["total_build_g"] = self.total_build_g()
        d["assumptions"] = assumptions()
        return d


def assumptions() -> dict:
    return {
        "grid_intensity_g_per_kWh": GRID_INTENSITY_G_PER_KWH,
        "ee_cpu_min_per_park_chunk": EE_CPU_MIN_PER_PARK_CHUNK,
        "ee_chunks_per_park": EE_CHUNKS_PER_PARK,
        "ee_Wh_per_cpu_hr": EE_WH_PER_CPU_HR,
        "egress_Wh_per_GB": EGRESS_WH_PER_GB,
        "raw_MB_per_park": RAW_MB_PER_PARK,
        "local_cpu_sec_per_park": LOCAL_CPU_SEC_PER_PARK,
        "local_power_W": LOCAL_POWER_W,
        "claude_input_Wh_per_kt": CLAUDE_INPUT_WH_PER_KT,
        "claude_output_Wh_per_kt": CLAUDE_OUTPUT_WH_PER_KT,
        "pages_Wh_per_GB": PAGES_WH_PER_GB_SERVED,
        "view_seconds": VIEW_SECONDS,
        "view_device_W": VIEW_DEVICE_W,
        "view_MB": VIEW_MB,
    }


def estimate(
    n_parks: int = 63,
    claude_input_tokens: int = 300_000,
    claude_output_tokens: int = 60_000,
    monthly_views: int = 10_000,
) -> CarbonBreakdown:
    """Compute the full carbon breakdown. Defaults match a full build."""
    # EE processing
    ee_cpu_hours = (n_parks * EE_CHUNKS_PER_PARK * EE_CPU_MIN_PER_PARK_CHUNK) / 60.0
    ee_proc_wh = ee_cpu_hours * EE_WH_PER_CPU_HR
    # Egress
    ee_gb = (n_parks * RAW_MB_PER_PARK) / 1024.0
    ee_egress_wh = ee_gb * EGRESS_WH_PER_GB
    # Local
    local_wh = (n_parks * LOCAL_CPU_SEC_PER_PARK / 3600.0) * LOCAL_POWER_W
    # Claude
    claude_wh = (
        (claude_input_tokens / 1000.0) * CLAUDE_INPUT_WH_PER_KT
        + (claude_output_tokens / 1000.0) * CLAUDE_OUTPUT_WH_PER_KT
    )
    # Hosting (monthly)
    monthly_gb = (monthly_views * VIEW_MB) / 1024.0
    hosting_wh = monthly_gb * PAGES_WH_PER_GB_SERVED
    # Per view
    view_wh = (VIEW_SECONDS / 3600.0) * VIEW_DEVICE_W + (
        (VIEW_MB / 1024.0) * PAGES_WH_PER_GB_SERVED
    )

    return CarbonBreakdown(
        ee_processing_g=_wh_to_g(ee_proc_wh),
        ee_egress_g=_wh_to_g(ee_egress_wh),
        local_analysis_g=_wh_to_g(local_wh),
        claude_api_g=_wh_to_g(claude_wh),
        hosting_per_month_g=_wh_to_g(hosting_wh),
        per_view_g=_wh_to_g(view_wh),
    )
