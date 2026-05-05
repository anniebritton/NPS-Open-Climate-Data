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

    bands = list(dataset_def["bands"])
    transforms = dataset_def.get("transforms") or {}

    if transforms:
        # Apply per-band unit conversions server-side so raw exports come out
        # in the same human-readable units as DAYMET (°C, mm, positive ET).
        def _convert(img):
            converted = []
            for band in bands:
                src = img.select(band)
                t = transforms.get(band)
                if t is None:
                    converted.append(src)
                    continue
                op, val = t
                if op == "subtract":
                    converted.append(src.subtract(val).rename(band))
                elif op == "multiply":
                    converted.append(src.multiply(val).rename(band))
                else:
                    converted.append(src)
            out = converted[0]
            for b in converted[1:]:
                out = out.addBands(b)
            return out.copyProperties(img, ["system:time_start"])

        ic = ic.map(_convert)

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


def _merged_ic(start_date: str, end_date: str, datasets: list[dict]) -> ee.ImageCollection:
    """Combine per-dataset ImageCollections into one image per date.

    Outer-joins on ``system:time_start`` so each output image carries bands
    from every dataset that had an observation on that date. The reducer
    downstream then emits a single feature per date — without this, the
    merged collection produced two features per date (one per dataset, each
    with NaNs for the other's bands), which is why downstream consumers had
    to coalesce by date in pandas.
    """
    per_ds = [_process_dataset(ds, start_date, end_date) for ds in datasets]
    if len(per_ds) == 1:
        return per_ds[0]

    f = ee.Filter.equals(leftField="system:time_start", rightField="system:time_start")
    merged = per_ds[0]
    for sec in per_ds[1:]:
        # Left-outer join: every primary image survives. Where ``sec`` has a
        # match, its bands are catted in; otherwise the primary passes through.
        left_outer = ee.Join.saveFirst(matchKey="_match", outer=True).apply(
            primary=merged, secondary=sec, condition=f
        )
        left = ee.ImageCollection(left_outer).map(
            lambda img: ee.Image(
                ee.Algorithms.If(
                    img.get("_match"),
                    ee.Image.cat(img, ee.Image(img.get("_match"))),
                    img,
                )
            ).copyProperties(img, ["system:time_start"])
        )
        # Pull in dates that exist only in ``sec`` — e.g. Dec 31 of leap years,
        # which DAYMET v4's 365-day calendar omits but ERA5-Land has.
        primary_times = ee.ImageCollection(merged).aggregate_array("system:time_start")
        right_only = sec.filter(
            ee.Filter.inList("system:time_start", primary_times).Not()
        )
        merged = left.merge(right_only)
    return merged


def make_export_task(
    park_name: str,
    start_date: str,
    end_date: str,
    geom: ee.Geometry,
    scale: int,
    datasets: list[dict],
    description: str,
    drive_folder: str,
    file_prefix: str,
) -> ee.batch.Task:
    """Create an EE batch export task for a park or sub-unit.

    The task exports a FeatureCollection (one row per day) as CSV to
    Google Drive. Call ``.start()`` on the returned task to submit it.
    Tasks run server-side; no interactive response-size limits apply.
    """
    fc = _reduce_to_table(_merged_ic(start_date, end_date, datasets), geom, scale)
    # Without explicit selectors, EE infers CSV columns from one feature's
    # schema and silently drops properties from features with different
    # schemas — which is exactly what our merged DAYMET+ERA5 collection
    # produces (one dataset per image, so one dataset's props per feature).
    selectors = ["date"] + [
        f"{ds['name']}_{band}" for ds in datasets for band in ds["bands"]
    ]
    print(f"  [export] {description}: {len(selectors)} columns "
          f"({', '.join(selectors[:3])}, ..., {selectors[-1]})")
    return ee.batch.Export.table.toDrive(
        collection=fc,
        description=description,
        folder=drive_folder,
        fileNamePrefix=file_prefix,
        fileFormat="CSV",
        selectors=selectors,
    )


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

    Uses the synchronous EE interactive API (``getInfo``). Suitable for
    small queries; for full 1980-present runs use ``make_export_task``
    via the batch module instead.

    If ``aoi_geom`` is provided it overrides the park boundary lookup;
    useful when iterating over multipart sub-units.
    """
    if aoi_geom is None:
        aoi_fc = get_park_boundary(park_name)
        if aoi_fc.size().getInfo() == 0:
            raise ValueError(f"Park '{park_name}' not found in PAD-US data.")
        aoi_geom = aoi_fc.geometry()

    use_datasets = datasets if datasets is not None else DATASETS
    print(f"Fetching data for {park_name} from {start_date} to {end_date}...")
    reduced = _reduce_to_table(
        _merged_ic(start_date, end_date, use_datasets), aoi_geom, scale
    )

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
    """High-level interactive fetch keyed by park slug.

    Returns a mapping of sub-unit label -> DataFrame. For single-part parks
    the mapping has a single entry keyed 'all'.
    """
    park = get_park(slug)
    if park is None:
        raise ValueError(f"Unknown park slug: {slug}")

    if end_date is None:
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
