"""
Batch export driver for all 63 US National Parks.

Given a local output directory, writes:
  data/raw/<slug>/<slug>[_<part>].parquet
  data/raw/<slug>/<slug>[_<part>].csv

Use from a script after running ``ee.Initialize()``. Long time ranges
spanning 1980-present for 63 parks can take hours; chunking by year is
used to stay under Earth Engine's interactive response limits.
"""

from __future__ import annotations

import os
import time
import traceback
from pathlib import Path

import pandas as pd

from .datasets import datasets_for_park
from .parks import get_parks


def _chunk_years(start: str, end: str, chunk: int = 5):
    """Yield (start, end) ISO date pairs where ``end`` is the *exclusive*
    upper bound (EE's ``filterDate`` is exclusive on its end argument).
    """
    s = pd.Timestamp(start).year
    # The caller's ``end`` itself is exclusive, so stop when y_start >= end_year+1.
    last_year = pd.Timestamp(end).year
    y = s
    while y <= last_year:
        y_end = min(y + chunk - 1, last_year)
        # end is exclusive => use Jan 1 of the following year
        yield f"{y}-01-01", f"{y_end + 1}-01-01"
        y = y_end + 1


def _fetch_range(park_name, start, end, scale, datasets, geom):
    from .core import get_data  # lazy: needs ee
    frames = []
    for s, e in _chunk_years(start, end, chunk=5):
        df = get_data(
            park_name, s, e, scale=scale,
            datasets=datasets, aoi_geom=geom,
        )
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"])
    return out.drop_duplicates("date").sort_values("date").reset_index(drop=True)


def _write(df: pd.DataFrame, out_dir: Path, stem: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    csv = out_dir / f"{stem}.csv"
    pq = out_dir / f"{stem}.parquet"
    df.to_csv(csv, index=False)
    try:
        df.to_parquet(pq, index=False)
    except Exception as exc:
        print(f"  parquet write failed ({exc}); csv is still written")


def export_park(park: dict, out_root: Path, start: str, end: str) -> list[Path]:
    """Export one park; returns list of files written."""
    import ee
    from .utils import get_park_boundary, split_multipart_features

    slug = park["slug"]
    ds = datasets_for_park(slug)
    scale = min(d["scale"] for d in ds)
    park_dir = out_root / "raw" / slug
    written: list[Path] = []

    aoi_fc = get_park_boundary(park["unit_name"])
    if aoi_fc.size().getInfo() == 0:
        print(f"  SKIP {slug}: not found in PAD-US")
        return written

    if park["multipart"]:
        parts = split_multipart_features(aoi_fc).getInfo()["features"]
        for i, feat in enumerate(parts):
            geom = ee.Geometry(feat["geometry"])
            df = _fetch_range(park["unit_name"], start, end, scale, ds, geom)
            stem = f"{slug}_part-{i}"
            _write(df, park_dir, stem)
            written.append(park_dir / f"{stem}.parquet")
    else:
        df = _fetch_range(
            park["unit_name"], start, end, scale, ds, aoi_fc.geometry()
        )
        _write(df, park_dir, slug)
        written.append(park_dir / f"{slug}.parquet")
    return written


def export_all(
    out_root: str | Path = "data",
    start: str = "1980-01-01",
    end: str | None = None,
    slugs: list[str] | None = None,
) -> None:
    """Export every national park (or a filtered subset by slug)."""
    out = Path(out_root)
    if end is None:
        end = pd.Timestamp.utcnow().strftime("%Y-%m-%d")
    parks = get_parks()
    if slugs:
        parks = [p for p in parks if p["slug"] in set(slugs)]

    for park in parks:
        print(f"[{park['slug']}] starting export")
        t0 = time.time()
        try:
            export_park(park, out, start, end)
            print(f"[{park['slug']}] done in {time.time() - t0:.0f}s")
        except Exception:
            print(f"[{park['slug']}] FAILED:")
            traceback.print_exc()
