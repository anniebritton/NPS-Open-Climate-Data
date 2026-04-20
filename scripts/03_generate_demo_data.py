"""Generate plausible synthetic daily climate series for every park.

This exists so the website can be demoed end-to-end without first running
the multi-hour Earth Engine export. Replace ``data/raw/`` contents with
real output from ``01_export_all_parks.py`` before publishing results.

The synthetic series encodes:
  * per-park baseline climate (warmer for southern / coastal parks,
    colder for Alaska / high-altitude)
  * a seasonal cycle
  * a warming trend (+0.02 to +0.04 C / yr) with noise
  * precipitation drawn from a gamma distribution
  * snowfall only for cold-winter parks
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from nps_climate_data.parks import get_parks


# rough mean-annual-temp (C) and annual-precip (mm) climatology per park
# tuned from NOAA climate normals; intentionally approximate.
CLIMATOLOGY: dict[str, tuple[float, float]] = {
    "acadia": (7.0, 1400),
    "american-samoa": (27.0, 3200),
    "arches": (13.0, 250),
    "badlands": (8.5, 430),
    "big-bend": (19.0, 380),
    "biscayne": (25.0, 1500),
    "black-canyon-of-the-gunnison": (6.5, 400),
    "bryce-canyon": (4.0, 400),
    "canyonlands": (13.5, 230),
    "capitol-reef": (11.5, 230),
    "carlsbad-caverns": (16.5, 370),
    "channel-islands": (15.5, 430),
    "congaree": (17.0, 1200),
    "crater-lake": (3.5, 1700),
    "cuyahoga-valley": (10.0, 1020),
    "death-valley": (24.5, 60),
    "denali": (-3.0, 380),
    "dry-tortugas": (26.0, 1000),
    "everglades": (24.5, 1400),
    "gates-of-the-arctic": (-9.0, 300),
    "gateway-arch": (14.0, 1000),
    "glacier": (3.0, 740),
    "glacier-bay": (5.0, 1800),
    "grand-canyon": (9.5, 400),
    "grand-teton": (2.0, 560),
    "great-basin": (5.0, 330),
    "great-sand-dunes": (5.0, 280),
    "great-smoky-mountains": (10.0, 1800),
    "guadalupe-mountains": (15.5, 400),
    "haleakala": (13.0, 1500),
    "hawaii-volcanoes": (17.0, 2500),
    "hot-springs": (15.5, 1370),
    "indiana-dunes": (10.5, 980),
    "isle-royale": (3.5, 760),
    "joshua-tree": (18.5, 120),
    "katmai": (1.5, 780),
    "kenai-fjords": (3.5, 1800),
    "kings-canyon": (7.5, 880),
    "kobuk-valley": (-6.0, 430),
    "lake-clark": (0.5, 650),
    "lassen-volcanic": (5.0, 900),
    "mammoth-cave": (13.5, 1370),
    "mesa-verde": (10.0, 460),
    "mount-rainier": (3.5, 2700),
    "new-river-gorge": (11.0, 1200),
    "north-cascades": (4.0, 1800),
    "olympic": (7.0, 3500),
    "petrified-forest": (12.5, 240),
    "pinnacles": (14.5, 430),
    "redwood": (11.5, 1700),
    "rocky-mountain": (1.5, 580),
    "saguaro": (20.5, 310),
    "sequoia": (8.0, 900),
    "shenandoah": (9.0, 1200),
    "theodore-roosevelt": (6.0, 380),
    "virgin-islands": (26.5, 1200),
    "voyageurs": (3.0, 660),
    "white-sands": (15.0, 230),
    "wind-cave": (8.0, 460),
    "wrangell-st-elias": (-3.5, 530),
    "yellowstone": (1.5, 560),
    "yosemite": (8.5, 920),
    "zion": (15.0, 400),
}

START = pd.Timestamp("1980-01-01")
END = pd.Timestamp("2024-12-31")


def _seeded_rng(slug: str) -> np.random.Generator:
    h = hashlib.sha1(slug.encode()).digest()
    seed = int.from_bytes(h[:4], "big")
    return np.random.default_rng(seed)


def _daily_series(slug: str, part_index: int = 0) -> pd.DataFrame:
    mean_t, ann_precip = CLIMATOLOGY.get(slug, (10.0, 800))
    # Slight offset per multipart unit so charts differ
    mean_t += part_index * 0.6
    rng = _seeded_rng(f"{slug}-{part_index}")
    dates = pd.date_range(START, END, freq="D")
    n = len(dates)
    doy = dates.dayofyear
    years_since = (dates.year - 1980)
    warming = years_since * rng.uniform(0.015, 0.045)
    # amplitude depends on latitude proxy: colder parks have bigger swing
    amp = 15 if mean_t < 10 else 9
    seasonal = amp * np.sin((doy - 80) / 365 * 2 * np.pi)
    tmean = mean_t + seasonal + warming + rng.normal(0, 2.5, n)
    tmax = tmean + rng.uniform(4, 7) + rng.normal(0, 1, n)
    tmin = tmean - rng.uniform(4, 7) + rng.normal(0, 1, n)

    # precipitation: daily wet/dry + gamma magnitude
    wet_prob = ann_precip / (365 * 8)
    wet = rng.random(n) < wet_prob
    # allow a very small positive precip trend / dry trend per park
    precip_trend = rng.uniform(-0.05, 0.05)
    prcp = np.where(
        wet,
        rng.gamma(1.2, ann_precip / (365 * wet_prob * 1.2), n) *
        (1 + precip_trend * years_since / 45),
        0,
    )
    prcp = np.clip(prcp, 0, None)

    df = pd.DataFrame({
        "date": dates,
        "DAYMET_tmax": tmax,
        "DAYMET_tmin": tmin,
        "DAYMET_prcp": prcp,
        "DAYMET_srad": 200 + 150 * np.sin((doy - 80) / 365 * 2 * np.pi) + rng.normal(0, 30, n),
        "DAYMET_vp": np.clip(700 + 500 * np.sin((doy - 80) / 365 * 2 * np.pi) + rng.normal(0, 100, n), 50, None),
    })
    # snow only for cold parks
    if mean_t < 8:
        df["DAYMET_swe"] = np.clip(-tmean * 5 + rng.normal(0, 5, n), 0, None)
        df["ERA5_snowfall_sum"] = np.clip(np.where(tmean < 0, prcp / 1000 * 0.9, 0), 0, None)
        df["ERA5_snow_depth"] = np.clip(df["DAYMET_swe"] / 300, 0, None)

    # evaporation
    df["ERA5_potential_evaporation_sum"] = np.clip(
        (0.002 + 0.00008 * np.clip(tmean, -10, 40)) * (1 + 0.2 * np.sin((doy - 80) / 365 * 2 * np.pi)), 0, None
    )
    df["ERA5_total_evaporation_sum"] = df["ERA5_potential_evaporation_sum"] * rng.uniform(0.3, 0.8)
    return df


def main():
    root = Path("data/raw")
    root.mkdir(parents=True, exist_ok=True)
    parks = get_parks()
    for p in parks:
        slug = p["slug"]
        pd_dir = root / slug
        pd_dir.mkdir(parents=True, exist_ok=True)
        if p["multipart"]:
            n_parts = 2 if slug in {"saguaro", "kings-canyon"} else 3
            for i in range(n_parts):
                df = _daily_series(slug, part_index=i)
                stem = f"{slug}_part-{i}"
                df.to_csv(pd_dir / f"{stem}.csv", index=False)
                try:
                    df.to_parquet(pd_dir / f"{stem}.parquet", index=False)
                except Exception:
                    pass
        else:
            df = _daily_series(slug)
            df.to_csv(pd_dir / f"{slug}.csv", index=False)
            try:
                df.to_parquet(pd_dir / f"{slug}.parquet", index=False)
            except Exception:
                pass
        print(f"{slug}: wrote {'multipart' if p['multipart'] else 'single'} series")


if __name__ == "__main__":
    main()
