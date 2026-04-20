"""
Build the JSON files consumed by the Astro site from raw per-park data.

Outputs under ``<out>/site/``:
  parks.json                  -- index of all parks + headline trends
  parks/<slug>.json           -- full summary per park (series, trends, stripes)

Run after batch export:

    from nps_climate_data.summarize import build_site_data
    build_site_data("data")
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .analysis import (
    canonicalise,
    annual,
    seasonal,
    anomalies,
    all_trends,
    climate_stripes,
)
from .parks import get_parks


HEADLINE_VARS = ["tmean_c", "tmax_c", "tmin_c", "prcp_mm"]


def _load_raw_park(park_dir: Path) -> dict[str, pd.DataFrame]:
    """Return {label: df} from a park directory of parquet/csv files."""
    out = {}
    files = sorted(list(park_dir.glob("*.parquet")) or list(park_dir.glob("*.csv")))
    for f in files:
        if f.suffix == ".parquet":
            df = pd.read_parquet(f)
        else:
            df = pd.read_csv(f)
        label = f.stem
        out[label] = df
    return out


def _combine_parts(parts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Area-naive combination: average daily values across multipart units.

    For headline statistics this is an acceptable approximation; per-part
    series are still available individually on the park page.
    """
    frames = []
    for label, df in parts.items():
        c = canonicalise(df)
        c["_part"] = label
        frames.append(c)
    if not frames:
        return pd.DataFrame()
    big = pd.concat(frames, ignore_index=True)
    big = big.groupby("date").mean(numeric_only=True).reset_index()
    return big


def _json_safe(obj):
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        return None if np.isnan(v) or np.isinf(v) else v
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return [_json_safe(x) for x in obj.tolist()]
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(x) for x in obj]
    return obj


def summarise_park(park: dict, park_dir: Path) -> dict | None:
    parts = _load_raw_park(park_dir)
    if not parts:
        return None

    part_summaries = {}
    for label, raw in parts.items():
        canon = canonicalise(raw)
        ann = annual(canon)
        part_summaries[label] = {
            "annual": ann.to_dict(orient="records"),
            "trends": [t.to_dict() for t in all_trends(ann)],
        }

    combined_daily = _combine_parts(parts)
    combined_annual = annual(combined_daily)
    combined_seasonal = seasonal(combined_daily)
    combined_anom = anomalies(combined_annual)
    trends = all_trends(combined_annual)
    stripes = climate_stripes(combined_annual, "tmean_c")

    headline = {t.variable: t.to_dict() for t in trends if t.variable in HEADLINE_VARS}

    summary = {
        "slug": park["slug"],
        "unit_name": park["unit_name"],
        "state": park["state"],
        "multipart": park["multipart"],
        "parts": list(part_summaries.keys()),
        "period": {
            "start_year": int(combined_annual["year"].min()) if not combined_annual.empty else None,
            "end_year": int(combined_annual["year"].max()) if not combined_annual.empty else None,
        },
        "annual": combined_annual.to_dict(orient="records"),
        "anomalies": combined_anom.to_dict(orient="records"),
        "seasonal": combined_seasonal.to_dict(orient="records"),
        "trends": [t.to_dict() for t in trends],
        "stripes": stripes,
        "headline_trends": headline,
        "part_summaries": part_summaries,
    }
    return _json_safe(summary)


def build_site_data(data_root: str | Path = "data") -> None:
    root = Path(data_root)
    raw_root = root / "raw"
    site_root = root / "site"
    parks_dir = site_root / "parks"
    parks_dir.mkdir(parents=True, exist_ok=True)

    index: list[dict] = []
    for park in get_parks():
        park_dir = raw_root / park["slug"]
        if not park_dir.exists():
            continue
        summary = summarise_park(park, park_dir)
        if summary is None:
            continue
        out_path = parks_dir / f"{park['slug']}.json"
        out_path.write_text(json.dumps(summary, separators=(",", ":")))

        index.append({
            "slug": summary["slug"],
            "unit_name": summary["unit_name"],
            "state": summary["state"],
            "multipart": summary["multipart"],
            "period": summary["period"],
            "headline_trends": summary["headline_trends"],
            "stripes": summary["stripes"],
        })

    (site_root / "parks.json").write_text(
        json.dumps(_json_safe({"parks": index}), separators=(",", ":"))
    )
    print(f"Wrote {len(index)} park summaries to {site_root}")
