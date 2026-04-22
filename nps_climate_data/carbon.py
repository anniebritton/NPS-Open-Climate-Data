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
  3. Claude API usage — cumulative across all dev sessions
  4. GitHub Actions CI — cumulative across all commits
  5. Static hosting on GitHub Pages
  6. Average page view on a user's browser

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
# daily data) is dominated by I/O and reductions.
# With EE tasks (serverless), no chunking overhead; budget 2 CPU-min/park.
EE_CPU_MIN_PER_PARK = 2.0
EE_WH_PER_CPU_HR = 15.0

# Egress: measured ~5.7 MB uncompressed CSV per park (from the actual
# 2026 full batch: 361 MB for 63 parks across 45 years of daily values).
# Round to 6 MB. Estimate 50 Wh / GB end-to-end (Aslan et al., 2017).
EGRESS_WH_PER_GB = 50.0
RAW_MB_PER_PARK = 6.0

# Local Python analysis: trend tests, aggregates. ~30s CPU per park at
# ~20 W laptop draw.
LOCAL_CPU_SEC_PER_PARK = 30.0
LOCAL_POWER_W = 20.0

# Claude API usage — cumulative over every dev session that touched the repo.
# Anthropic's 2024 disclosures and independent estimates (Luccioni et al.)
# put LLM inference at roughly 2-4 Wh per 1k output tokens for large models,
# and ~0.2 Wh per 1k input tokens (input is much cheaper).
# Per-commit budget is a rough proxy for session work; baseline covers the
# initial build sessions before the first commit.
CLAUDE_INPUT_WH_PER_KT = 0.2
CLAUDE_OUTPUT_WH_PER_KT = 3.0
CLAUDE_IN_PER_COMMIT = 50_000    # tokens per commit (rolling average)
CLAUDE_OUT_PER_COMMIT = 10_000
CLAUDE_IN_BASELINE = 300_000     # pre-first-commit build work
CLAUDE_OUT_BASELINE = 60_000

# GitHub Actions CI — each push to main triggers a deploy workflow + a test
# workflow. The ubuntu-latest runner is a 2-vCPU Azure VM; we budget ~4 min
# of wall-clock compute per run at ~12.5 W per vCPU (CPU + cooling + overhead).
CI_RUNS_PER_COMMIT = 2           # deploy.yml + tests.yml
# Measured ~45-90s wall-clock per run on this repo (the deploy job is the
# longer of the two). Round to 1.5 min.
CI_MINUTES_PER_RUN = 1.5
CI_VCPUS = 2
CI_W_PER_VCPU = 12.5

# GitHub Pages hosting: very low; ~50 Wh per GB served, and we expect
# ~5 MB per page view amortised, serving up to ~10k views / month.
PAGES_WH_PER_GB_SERVED = 50.0

# Average page view on the user's browser: ~1 minute, phone at 2 W, plus
# ~500 KB of network transfer (measured: per-park JSON ~175 KB,
# boundary GeoJSON ~30 KB, park-map PNG ~70 KB, plus Chart.js/Leaflet
# from a CDN cache hit on repeat visits). 0.5 MB is a realistic amortised
# figure for users browsing a few parks.
VIEW_SECONDS = 60.0
VIEW_DEVICE_W = 2.0
VIEW_MB = 0.5


def _wh_to_g(wh: float) -> float:
    return wh * GRID_INTENSITY_G_PER_KWH / 1000.0


@dataclass
class CarbonBreakdown:
    ee_processing_g: float
    ee_egress_g: float
    local_analysis_g: float
    claude_api_g: float
    ci_actions_g: float
    hosting_per_month_g: float
    per_view_g: float

    def total_build_g(self) -> float:
        return (
            self.ee_processing_g
            + self.ee_egress_g
            + self.local_analysis_g
            + self.claude_api_g
            + self.ci_actions_g
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["total_build_g"] = self.total_build_g()
        d["assumptions"] = assumptions()
        return d


def assumptions() -> dict:
    return {
        "grid_intensity_g_per_kWh": GRID_INTENSITY_G_PER_KWH,
        "ee_cpu_min_per_park": EE_CPU_MIN_PER_PARK,
        "ee_Wh_per_cpu_hr": EE_WH_PER_CPU_HR,
        "egress_Wh_per_GB": EGRESS_WH_PER_GB,
        "raw_MB_per_park": RAW_MB_PER_PARK,
        "local_cpu_sec_per_park": LOCAL_CPU_SEC_PER_PARK,
        "local_power_W": LOCAL_POWER_W,
        "claude_input_Wh_per_kt": CLAUDE_INPUT_WH_PER_KT,
        "claude_output_Wh_per_kt": CLAUDE_OUTPUT_WH_PER_KT,
        "claude_in_per_commit": CLAUDE_IN_PER_COMMIT,
        "claude_out_per_commit": CLAUDE_OUT_PER_COMMIT,
        "ci_runs_per_commit": CI_RUNS_PER_COMMIT,
        "ci_minutes_per_run": CI_MINUTES_PER_RUN,
        "ci_vcpus": CI_VCPUS,
        "ci_W_per_vcpu": CI_W_PER_VCPU,
        "pages_Wh_per_GB": PAGES_WH_PER_GB_SERVED,
        "view_seconds": VIEW_SECONDS,
        "view_device_W": VIEW_DEVICE_W,
        "view_MB": VIEW_MB,
    }


def estimate(
    n_parks: int = 63,
    n_commits: int = 0,
    monthly_views: int = 10_000,
) -> CarbonBreakdown:
    """Compute the full carbon breakdown.

    Claude token usage and CI run counts both scale with ``n_commits`` so
    the estimate grows honestly as the project accumulates history.
    """
    # EE processing (one-time export, serverless tasks)
    ee_cpu_hours = (n_parks * EE_CPU_MIN_PER_PARK) / 60.0
    ee_proc_wh = ee_cpu_hours * EE_WH_PER_CPU_HR
    # Egress (Drive download after tasks complete)
    ee_gb = (n_parks * RAW_MB_PER_PARK) / 1024.0
    ee_egress_wh = ee_gb * EGRESS_WH_PER_GB
    # Local analysis
    local_wh = (n_parks * LOCAL_CPU_SEC_PER_PARK / 3600.0) * LOCAL_POWER_W
    # Claude API — cumulative across all dev sessions
    claude_in = CLAUDE_IN_BASELINE + n_commits * CLAUDE_IN_PER_COMMIT
    claude_out = CLAUDE_OUT_BASELINE + n_commits * CLAUDE_OUT_PER_COMMIT
    claude_wh = (
        (claude_in / 1000.0) * CLAUDE_INPUT_WH_PER_KT
        + (claude_out / 1000.0) * CLAUDE_OUTPUT_WH_PER_KT
    )
    # GitHub Actions CI — cumulative across all commits
    ci_run_hours = (n_commits * CI_RUNS_PER_COMMIT * CI_MINUTES_PER_RUN) / 60.0
    ci_wh = ci_run_hours * CI_VCPUS * CI_W_PER_VCPU
    # Hosting (monthly)
    monthly_gb = (monthly_views * VIEW_MB) / 1024.0
    hosting_wh = monthly_gb * PAGES_WH_PER_GB_SERVED
    # Per view
    view_wh = (VIEW_SECONDS / 3600.0) * VIEW_DEVICE_W + (VIEW_MB / 1024.0) * PAGES_WH_PER_GB_SERVED

    return CarbonBreakdown(
        ee_processing_g=_wh_to_g(ee_proc_wh),
        ee_egress_g=_wh_to_g(ee_egress_wh),
        local_analysis_g=_wh_to_g(local_wh),
        claude_api_g=_wh_to_g(claude_wh),
        ci_actions_g=_wh_to_g(ci_wh),
        hosting_per_month_g=_wh_to_g(hosting_wh),
        per_view_g=_wh_to_g(view_wh),
    )
