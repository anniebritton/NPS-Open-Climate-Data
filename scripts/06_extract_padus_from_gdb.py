"""
Extract real park boundaries from a locally-stored PAD-US File Geodatabase.

The PAD-US 4.1 GDB is a ~2 GB download — too large for git and awkward
for CI. Users who want to refresh boundaries download it once, drop it
at ``data/PADUS4_1Geodatabase/`` (gitignored), and run this script.
Resulting GeoJSON files are small enough to commit, so CI doesn't need
network access to USGS.

For each of the 63 national parks:
1. Match by Unit_Nm (with the same aliases used for EE boundary lookups).
2. Union all proclamation features for that park (multi-district parks
   produce a MultiPolygon; single-contiguous parks produce a Polygon).
3. Reproject from USA Contiguous Albers (EPSG:ESRI:102039) to WGS84.
4. Simplify in projected metres before reprojecting to keep file size
   reasonable — the Leaflet overview map doesn't need sub-metre
   precision.
5. Write ``site/public/data/boundaries/<slug>.geojson`` as a single
   Feature inside a FeatureCollection.

Follow-up step ``05_generate_boundaries.py`` fills in any park that
wasn't matched here (with a circle) and merges warming-slope
properties into each feature before writing ``all_parks.geojson``.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
from shapely.ops import unary_union

from nps_climate_data.parks import get_parks
from nps_climate_data.utils import PADUS_UNIT_ALIASES

REPO = Path(__file__).resolve().parents[1]
GDB = REPO / "data" / "PADUS4_1Geodatabase" / "PADUS4_1Geodatabase.gdb"
LAYER = "PADUS4_1Proclamation"
OUT_DIR = REPO / "site" / "public" / "data" / "boundaries"

# Simplify tolerance in PAD-US native CRS (metres). 50 m preserves
# coastal and ridge detail that's visible at per-park zoom levels.
# Too high and Acadia's islands smooth into blobs.
SIMPLIFY_M = 50


def _aliases_for(unit_name: str) -> list[str]:
    return PADUS_UNIT_ALIASES.get(unit_name, [unit_name])


def main() -> None:
    if not GDB.exists():
        raise SystemExit(
            f"PAD-US GDB not found at {GDB}. Download PADUS 4.1 from USGS "
            "and unpack it at data/PADUS4_1Geodatabase/."
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Read the full NPS subset once (much faster than 63 filtered reads).
    gdf = gpd.read_file(
        GDB,
        layer=LAYER,
        columns=["Unit_Nm", "Mang_Name", "Des_Tp", "State_Nm", "GIS_Acres"],
        where="Mang_Name = 'NPS'",
    )
    print(f"Loaded {len(gdf)} NPS proclamation features from GDB")

    found = 0
    missed: list[str] = []
    for park in get_parks():
        slug = park["slug"]
        names = _aliases_for(park["unit_name"])
        # PAD-US stores 'New River Gorge National Park and Preserve' under
        # that full string — our alias list already covers the known quirks.
        rows = gdf[gdf["Unit_Nm"].isin(names)]

        if rows.empty:
            missed.append(slug)
            continue

        # Union all matching features so a park with multiple polygons
        # (Saguaro East/West, Channel Islands archipelago) becomes a single
        # MultiPolygon feature.
        merged = unary_union(rows.geometry.values)
        simplified = merged.simplify(SIMPLIFY_M, preserve_topology=True)

        # Reproject the single merged geometry to WGS84 for the web.
        proj = gpd.GeoSeries([simplified], crs=gdf.crs).to_crs("EPSG:4326")
        geom = proj.iloc[0]

        total_acres = float(rows["GIS_Acres"].sum())
        feature = {
            "type": "Feature",
            "geometry": geom.__geo_interface__,
            "properties": {
                "slug": slug,
                "unit_name": park["unit_name"],
                "state": park["state"],
                "area_km2": round(total_acres * 0.00404686, 3),  # acres → km²
                "source": "PAD-US v4.1 Proclamation",
            },
        }
        fc = {"type": "FeatureCollection", "features": [feature]}
        (OUT_DIR / f"{slug}.geojson").write_text(json.dumps(fc, separators=(",", ":")))
        found += 1

    print(f"Wrote {found} real boundaries; {len(missed)} not matched: {missed}")


if __name__ == "__main__":
    main()
