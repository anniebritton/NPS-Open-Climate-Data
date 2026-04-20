"""
Core Earth Engine reduction logic for per-park daily climate time series.
"""

from __future__ import annotations

import ee
import pandas as pd

from .datasets import DATASETS, datasets_for_park
from .utils import get_park_boundary, split_multipart_features
from .parks import get_park


def _process_dataset(dataset_def: dict, start_date: str, end_date: str) -> ee.ImageCollection:
    ic = (
        ee.ImageCollection(dataset_def["asset_id"])
        .filterDate(start_date, end_date)
        .select(dataset_def["bands"])
    )
    pfx = dataset_def["name"] + "_"

    def _rename(img):
        old = img.bandNames()
        new = old.map(lambda n: ee.String(pfx).cat(n))
        return img.rename(new)

    return ic.map(_rename)


def _reduce_to_table(
    merged_ic: ee.ImageCollection, geom: ee.Geometry, scale: int
) -> ee.FeatureCollection:
    def _reduce(img):
        stats = img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geom,
            scale=scale,
            maxPixels=1e13,
            bestEffort=True,
        )
        stats = stats.set("date", img.date().format("YYYY-MM-dd"))
        return ee.Feature(None, stats)

    return merged_ic.map(_reduce)


def get_data(
    park_name: str,
    start_date: str,
    end_date: str,
    output_file: str | None = None,
    scale: int = 1000,
    datasets: list[dict] | None = None,
    aoi_geom: ee.Geometry | None = None,
) -> pd.DataFrame:
    """Fetch daily climate data for a park and return as DataFrame.

    If ``aoi_geom`` is provided it overrides the park boundary lookup;
    useful when iterating over multipart sub-units.
    """
    if aoi_geom is None:
        aoi_fc = get_park_boundary(park_name)
        if aoi_fc.size().getInfo() == 0:
            raise ValueError(f"Park '{park_name}' not found in PAD-US data.")
        aoi_geom = aoi_fc.geometry()

    use_datasets = datasets if datasets is not None else DATASETS
    # Note: ee.ImageCollection.filterDate treats ``end_date`` as an EXCLUSIVE
    # upper bound, so pass e.g. '1985-01-01' to include all of 1984.
    per_ds = [_process_dataset(ds, start_date, end_date) for ds in use_datasets]
    merged = per_ds[0]
    for ic in per_ds[1:]:
        merged = merged.merge(ic)

    print(f"Fetching data for {park_name} from {start_date} to {end_date}...")
    reduced = _reduce_to_table(merged, aoi_geom, scale)

    features = reduced.getInfo()["features"]
    if not features:
        return pd.DataFrame()

    df = pd.DataFrame([f["properties"] for f in features])
    if "date" not in df.columns:
        return df

    df_final = df.groupby("date").max().reset_index()
    df_final["date"] = pd.to_datetime(df_final["date"])
    df_final = df_final.sort_values("date").reset_index(drop=True)

    if output_file:
        df_final.to_csv(output_file, index=False)

    return df_final


def get_park_data(
    slug: str,
    start_date: str = "1980-01-01",
    end_date: str | None = None,
) -> dict[str, pd.DataFrame]:
    """High-level fetch keyed by park slug.

    Returns a mapping of sub-unit label -> DataFrame. For single-part parks
    the mapping has a single entry keyed 'all'.
    """
    park = get_park(slug)
    if park is None:
        raise ValueError(f"Unknown park slug: {slug}")

    if end_date is None:
        # filterDate end is EXCLUSIVE, so tomorrow captures all of today.
        end_date = (pd.Timestamp.utcnow().normalize() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    aoi_fc = get_park_boundary(park["unit_name"])
    if aoi_fc.size().getInfo() == 0:
        raise ValueError(f"Park '{park['unit_name']}' not found in PAD-US.")

    ds = datasets_for_park(slug)
    scale = min(d["scale"] for d in ds)

    out: dict[str, pd.DataFrame] = {}
    if park["multipart"]:
        parts = split_multipart_features(aoi_fc).getInfo()["features"]
        for i, feat in enumerate(parts):
            geom = ee.Geometry(feat["geometry"])
            label = f"part-{i}"
            df = get_data(
                park["unit_name"], start_date, end_date,
                scale=scale, datasets=ds, aoi_geom=geom,
            )
            out[label] = df
    else:
        out["all"] = get_data(
            park["unit_name"], start_date, end_date,
            scale=scale, datasets=ds, aoi_geom=aoi_fc.geometry(),
        )
    return out
