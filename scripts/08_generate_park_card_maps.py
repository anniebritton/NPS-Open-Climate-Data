"""
Generate tiny static basemap thumbnails for each park card on the home page.

For each of the 63 parks, plots the committed PAD-US polygon over a
muted Carto Positron (no-labels) basemap, cropped to a padded bounding
box. Output: ``site/public/data/park-maps/<slug>.png`` at ~600x400 px.

Runs locally once; PNGs are committed. Only needs re-running when park
boundaries change.

Requires: geopandas, contextily, matplotlib, shapely.
"""

from __future__ import annotations

import json
from pathlib import Path

import contextily as cx
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import shape

REPO = Path(__file__).resolve().parents[1]
BOUNDS_DIR = REPO / "site" / "public" / "data" / "boundaries"
OUT_DIR = REPO / "site" / "public" / "data" / "park-maps"

# 600x400 keeps each PNG under 40KB while still looking sharp on a
# retina card; total footprint ~1.5MB for 63 parks.
FIG_W = 6.0
FIG_H = 4.0
DPI = 100

# Percentage of the park's bbox to pad on every side. Too tight and the
# park feels cramped; too loose and it vanishes.
PAD_FRAC = 0.25

# Minimum bbox size in WGS84 degrees so a tiny park (like Hot Springs)
# doesn't zoom to street level. Roughly 25km at 45°N.
MIN_SPAN_DEG = 0.25


def _plot_park(slug: str, geojson_path: Path, out_path: Path) -> bool:
    with open(geojson_path) as f:
        gj = json.load(f)
    feats = gj.get("features", [])
    if not feats:
        return False

    geom = shape(feats[0]["geometry"])
    gdf = gpd.GeoDataFrame({"slug": [slug]}, geometry=[geom], crs="EPSG:4326")

    # Reproject to Web Mercator for contextily (basemap is in EPSG:3857).
    gdf_3857 = gdf.to_crs("EPSG:3857")
    minx, miny, maxx, maxy = gdf_3857.total_bounds
    dx = maxx - minx
    dy = maxy - miny

    # Enforce a minimum span in Mercator metres (MIN_SPAN_DEG → ~28km).
    min_span_m = MIN_SPAN_DEG * 111_320
    if dx < min_span_m:
        cx_ = (minx + maxx) / 2
        minx, maxx = cx_ - min_span_m / 2, cx_ + min_span_m / 2
        dx = maxx - minx
    if dy < min_span_m:
        cy = (miny + maxy) / 2
        miny, maxy = cy - min_span_m / 2, cy + min_span_m / 2
        dy = maxy - miny

    pad_x = dx * PAD_FRAC
    pad_y = dy * PAD_FRAC
    bbox = (minx - pad_x, miny - pad_y, maxx + pad_x, maxy + pad_y)

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H), dpi=DPI)
    ax.set_xlim(bbox[0], bbox[2])
    ax.set_ylim(bbox[1], bbox[3])

    # Park fill: deep terracotta at ~35% opacity so the basemap reads
    # through, with a crisp dark edge.
    gdf_3857.plot(ax=ax, facecolor="#ff603a", edgecolor="#1e1e1e",
                  linewidth=1.2, alpha=0.55)

    try:
        cx.add_basemap(
            ax,
            source=cx.providers.CartoDB.PositronNoLabels,
            attribution=False,  # attribution is shown once on the page, not per card
        )
    except Exception as exc:
        # Tile fetch failed (offline, rate-limit) — leave a clean backdrop.
        print(f"  {slug}: basemap fetch failed ({exc}); using plain background")
        ax.set_facecolor("#eae8df")

    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    return True


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(BOUNDS_DIR.glob("*.geojson"))
    # Skip the combined file.
    files = [f for f in files if f.stem != "all_parks"]

    n_ok = 0
    for f in files:
        slug = f.stem
        out = OUT_DIR / f"{slug}.png"
        print(f"  {slug} ...", end=" ", flush=True)
        ok = _plot_park(slug, f, out)
        if ok:
            n_ok += 1
            print("✓")
        else:
            print("skip (no features)")
    print(f"\nWrote {n_ok} park-card maps to {OUT_DIR}")


if __name__ == "__main__":
    main()
