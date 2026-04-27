"""
Statistical analyses of per-park daily climate time series.

Provides:
  * annual / seasonal aggregation (means + sums on appropriate variables)
  * reference-period anomalies (default 1981-2010)
  * Mann-Kendall trend test (with tie correction)
  * Theil-Sen slope estimator
  * Climate stripes colour values (yearly temperature z-scores)

Dependencies: pandas, numpy. SciPy is not required; the Mann-Kendall
p-value uses the normal approximation, which is standard for n >= 10.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd


# ---- variable canonicalisation --------------------------------------------

# Map dataset-prefixed band names to canonical variables used everywhere
# downstream. Multiple source columns may populate one canonical column; if
# DAYMET is available it wins (higher resolution), else ERA5 fills in.
# Temperatures emitted in degrees Celsius; ERA5 temperatures are stored in K.
# Unit tokens used to drive conversions below:
#   C        — already in Celsius
#   K        — Kelvin, subtract 273.15
#   mm       — millimeters, passthrough
#   m        — meters, multiply by 1000 (-> mm)
#   m_we     — meters of water equivalent, multiply by 1000 (-> mm)
#   m_neg    — meters, sign-flip and multiply by 1000 (ERA5 evaporation
#              fluxes are negative downward into the surface)
#   Wm2     — W/m², passthrough
#   kgm2    — kg/m², numerically equal to mm of liquid water
#   Pa       — Pascals, passthrough
CANONICAL = {
    "tmax_c": [("DAYMET_tmax", "C"), ("ERA5_temperature_2m_max", "K")],
    "tmin_c": [("DAYMET_tmin", "C"), ("ERA5_temperature_2m_min", "K")],
    "tmean_c": [("ERA5_temperature_2m", "K")],  # DAYMET has no tmean native
    "prcp_mm": [("DAYMET_prcp", "mm"), ("ERA5_total_precipitation_sum", "m")],
    "snow_depth_we_mm": [("ERA5_snow_depth", "m_we")],  # ERA5-Land: m w.e. → mm
    "snowfall_mm": [("ERA5_snowfall_sum", "m_we")],
    "snowmelt_mm": [("ERA5_snowmelt_sum", "m_we")],
    "snow_cover_pct": [("ERA5_snow_cover", "pass")],  # ERA5: % (0-100), passthrough
    "srad_wm2": [("DAYMET_srad", "Wm2")],
    "swe_mm": [("DAYMET_swe", "kgm2")],
    "vp_pa": [("DAYMET_vp", "Pa")],
    # ERA5 evaporation bands are negative by convention; flip sign so
    # pet_mm / aet_mm are the familiar positive mm / day values.
    "pet_mm": [("ERA5_potential_evaporation_sum", "m_neg")],
    "aet_mm": [("ERA5_total_evaporation_sum", "m_neg")],
    # wind_speed_ms is derived below from u/v components — not listed here
}


def canonicalise(df: pd.DataFrame) -> pd.DataFrame:
    """Map a raw per-park DataFrame into canonical units + columns."""
    df = df.copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    out = pd.DataFrame({"date": df["date"]}) if "date" in df else pd.DataFrame()

    for canon, sources in CANONICAL.items():
        series = None
        for col, unit in sources:
            if col not in df.columns:
                continue
            s = df[col].astype(float)
            if unit == "K":
                s = s - 273.15
            elif unit == "m":
                s = s * 1000.0  # m -> mm
            elif unit == "m_we":
                s = s * 1000.0
            elif unit == "m_neg":
                s = -s * 1000.0  # ECMWF sign convention -> positive mm
            # "pass" and unit tokens with no numeric conversion (Wm2, kgm2,
            # Pa, mm, C) fall through unchanged.
            if series is None:
                series = s
            else:
                series = series.where(series.notna(), s)
        if series is not None:
            out[canon] = series

    if "tmean_c" not in out.columns and {"tmax_c", "tmin_c"}.issubset(out.columns):
        out["tmean_c"] = (out["tmax_c"] + out["tmin_c"]) / 2.0

    # Wind speed derived from ERA5 u/v components (already in m/s).
    u_col = "ERA5_u_component_of_wind_10m"
    v_col = "ERA5_v_component_of_wind_10m"
    if u_col in df.columns and v_col in df.columns:
        u = df[u_col].astype(float)
        v = df[v_col].astype(float)
        out["wind_speed_ms"] = np.sqrt(u ** 2 + v ** 2)

    return out


# ---- aggregation ----------------------------------------------------------

SUM_VARS = {"prcp_mm", "snowfall_mm", "snowmelt_mm", "pet_mm", "aet_mm"}
MEAN_VARS = {
    "tmax_c", "tmin_c", "tmean_c",
    "srad_wm2", "swe_mm", "vp_pa",
    "snow_depth_we_mm", "snow_cover_pct", "wind_speed_ms",
}

SEASONS = {
    "DJF": (12, 1, 2),
    "MAM": (3, 4, 5),
    "JJA": (6, 7, 8),
    "SON": (9, 10, 11),
}


def _water_year(d: pd.Timestamp) -> int:
    return d.year + (1 if d.month >= 10 else 0)


def annual(df: pd.DataFrame) -> pd.DataFrame:
    """Calendar-year aggregation. Requires a 'date' column."""
    if df.empty:
        return df
    d = df.copy()
    d["year"] = d["date"].dt.year
    g = d.groupby("year")
    agg = {}
    for col in d.columns:
        if col in ("date", "year"):
            continue
        if col in SUM_VARS:
            agg[col] = "sum"
        elif col in MEAN_VARS:
            agg[col] = "mean"
    out = g.agg(agg).reset_index()
    # require >=330 non-null daily obs per year for the aggregate to count
    counts = g.size().reset_index(name="n_days")
    out = out.merge(counts, on="year")
    out = out[out["n_days"] >= 330].drop(columns="n_days")
    return out


def seasonal(df: pd.DataFrame) -> pd.DataFrame:
    """Season x year aggregation (DJF uses prior-year December)."""
    if df.empty:
        return df
    d = df.copy()
    d["year"] = d["date"].dt.year
    d["month"] = d["date"].dt.month

    def _season(m):
        for name, months in SEASONS.items():
            if m in months:
                return name
        return None

    d["season"] = d["month"].map(_season)
    # Assign DJF December to the following year
    d.loc[d["month"] == 12, "year"] = d.loc[d["month"] == 12, "year"] + 1

    agg = {}
    for col in d.columns:
        if col in ("date", "year", "month", "season"):
            continue
        if col in SUM_VARS:
            agg[col] = "sum"
        elif col in MEAN_VARS:
            agg[col] = "mean"
    return d.groupby(["year", "season"]).agg(agg).reset_index()


# ---- anomalies ------------------------------------------------------------

def anomalies(annual_df: pd.DataFrame, ref=(1981, 2010)) -> pd.DataFrame:
    """Subtract the reference-period mean and divide by stdev for z-scores."""
    if annual_df.empty:
        return annual_df
    ref_mask = annual_df["year"].between(ref[0], ref[1])
    ref_df = annual_df.loc[ref_mask]
    out = annual_df[["year"]].copy()
    for col in annual_df.columns:
        if col == "year":
            continue
        mu = ref_df[col].mean()
        sd = ref_df[col].std(ddof=0)
        out[f"{col}_anom"] = annual_df[col] - mu
        out[f"{col}_z"] = (annual_df[col] - mu) / sd if sd and not math.isnan(sd) else np.nan
    return out


# ---- trend tests ----------------------------------------------------------

@dataclass
class TrendResult:
    variable: str
    n: int
    start_year: int
    end_year: int
    slope_per_year: float  # Theil-Sen
    intercept: float
    total_change: float  # slope * (n_years - 1)
    mk_statistic: float  # Mann-Kendall S
    mk_z: float
    p_value: float
    significant_95: bool

    def to_dict(self) -> dict:
        return asdict(self)


def _mann_kendall(y: np.ndarray) -> tuple[float, float, float]:
    """Return (S, Z, p_value) for a 1-D series using the normal approx."""
    n = len(y)
    if n < 4:
        return (float("nan"),) * 3
    S = 0
    for i in range(n - 1):
        diff = y[i + 1:] - y[i]
        S += np.sum(np.sign(diff))
    # variance with tie correction
    unique, counts = np.unique(y, return_counts=True)
    tie_term = np.sum(counts * (counts - 1) * (2 * counts + 5))
    var_s = (n * (n - 1) * (2 * n + 5) - tie_term) / 18.0
    if var_s <= 0:
        return S, 0.0, 1.0
    if S > 0:
        z = (S - 1) / math.sqrt(var_s)
    elif S < 0:
        z = (S + 1) / math.sqrt(var_s)
    else:
        z = 0.0
    # two-sided p from standard normal
    p = math.erfc(abs(z) / math.sqrt(2.0))
    return float(S), float(z), float(p)


def _theil_sen(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    slopes = []
    for i in range(len(x) - 1):
        dx = x[i + 1:] - x[i]
        dy = y[i + 1:] - y[i]
        mask = dx != 0
        slopes.append(dy[mask] / dx[mask])
    if not slopes:
        return float("nan"), float("nan")
    slope = float(np.median(np.concatenate(slopes)))
    intercept = float(np.median(y - slope * x))
    return slope, intercept


def trend(annual_df: pd.DataFrame, variable: str) -> TrendResult | None:
    if variable not in annual_df.columns:
        return None
    sub = annual_df[["year", variable]].dropna()
    if len(sub) < 10:
        return None
    x = sub["year"].to_numpy(dtype=float)
    y = sub[variable].to_numpy(dtype=float)
    slope, intercept = _theil_sen(x, y)
    S, z, p = _mann_kendall(y)
    return TrendResult(
        variable=variable,
        n=len(sub),
        start_year=int(x.min()),
        end_year=int(x.max()),
        slope_per_year=slope,
        intercept=intercept,
        total_change=slope * (x.max() - x.min()),
        mk_statistic=S,
        mk_z=z,
        p_value=p,
        significant_95=bool(p < 0.05),
    )


def all_trends(annual_df: pd.DataFrame) -> list[TrendResult]:
    results = []
    for col in annual_df.columns:
        if col == "year":
            continue
        r = trend(annual_df, col)
        if r is not None:
            results.append(r)
    return results


# ---- decomposition --------------------------------------------------------

def decompose_monthly(
    df: pd.DataFrame,
    variable: str,
    ref: tuple[int, int] = (1981, 2010),
) -> dict | None:
    """Classical additive decomposition of a daily series into long-term
    trend, seasonal cycle, and residual at monthly resolution.

    Returns dict with arrays:
      months          — 'YYYY-MM' labels
      observed        — monthly aggregate (mean for MEAN_VARS, sum for SUM_VARS)
      trend           — 12-month centred rolling mean of `observed`
      residual        — observed - trend - seasonal_for_that_month
    and a separate 12-element climatology block:
      climatology     — {month: 1..12, mean, p10, p90} averaged over `ref`

    Returns None if the variable isn't present or has fewer than 24 months
    of data (one rolling window minimum).
    """
    if variable not in df.columns or df.empty:
        return None

    d = df[["date", variable]].copy()
    d["date"] = pd.to_datetime(d["date"])
    d = d.dropna(subset=[variable])
    if len(d) < 24 * 28:  # ~24 months of daily data minimum
        return None

    # Resample daily → monthly, choosing aggregator by variable kind.
    d.set_index("date", inplace=True)
    if variable in SUM_VARS:
        monthly = d[variable].resample("MS").sum(min_count=20)
    else:
        monthly = d[variable].resample("MS").mean()
    monthly = monthly.dropna()
    if len(monthly) < 24:
        return None

    # 12-month centred rolling mean as the long-term trend component.
    # `center=True, window=12` puts the value at the centre of the window;
    # endpoints are NaN until the window fills (~6 months on each side).
    trend = monthly.rolling(window=12, center=True, min_periods=12).mean()

    # Climatology = month-of-year mean over the reference period
    # (1981-2010 by default), so the seasonal shape is anchored to a
    # stable WMO baseline rather than drifting with the warming trend.
    ref_mask = (monthly.index.year >= ref[0]) & (monthly.index.year <= ref[1])
    ref_monthly = monthly.loc[ref_mask]
    clim_mean = ref_monthly.groupby(ref_monthly.index.month).mean()
    clim_p10 = ref_monthly.groupby(ref_monthly.index.month).quantile(0.10)
    clim_p90 = ref_monthly.groupby(ref_monthly.index.month).quantile(0.90)

    # Seasonal component for every observed month is the climatology
    # value for that calendar month. Residual is what's left after
    # removing trend and seasonal.
    seasonal = monthly.index.month.map(clim_mean.to_dict())
    seasonal = pd.Series(seasonal, index=monthly.index)
    # Anchor seasonal to zero-mean so trend absorbs the climatological mean.
    seasonal = seasonal - clim_mean.mean()
    residual = monthly - trend - seasonal

    return {
        "variable": variable,
        "ref_period": [int(ref[0]), int(ref[1])],
        "months": [d.strftime("%Y-%m") for d in monthly.index],
        "observed": [None if np.isnan(v) else float(v) for v in monthly.values],
        "trend":    [None if np.isnan(v) else float(v) for v in trend.values],
        "residual": [None if np.isnan(v) else float(v) for v in residual.values],
        "climatology": [
            {
                "month": int(m),
                "mean": float(clim_mean[m]),
                "p10":  float(clim_p10[m]),
                "p90":  float(clim_p90[m]),
            }
            for m in range(1, 13) if m in clim_mean.index
        ],
    }


# ---- climate stripes ------------------------------------------------------

def climate_stripes(annual_df: pd.DataFrame, variable: str = "tmean_c") -> list[dict]:
    """Return a year-keyed list of {year, value, z} suitable for rendering a
    Hawkins-style climate stripes visualisation."""
    if variable not in annual_df.columns:
        return []
    anom = anomalies(annual_df[["year", variable]])
    z_col = f"{variable}_z"
    out = []
    for _, row in anom.iterrows():
        out.append({
            "year": int(row["year"]),
            "value": float(annual_df.loc[annual_df["year"] == row["year"], variable].iloc[0]),
            "z": None if pd.isna(row.get(z_col)) else float(row[z_col]),
        })
    return out
