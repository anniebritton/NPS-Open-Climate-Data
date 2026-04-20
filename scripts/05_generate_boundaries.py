"""
Generate approximate park-boundary GeoJSONs for the website.

Without access to Earth Engine / PAD-US in this environment, we render each
park as a circular polygon centred on its known centroid and scaled to its
known area. Real PAD-US polygons replace these once the EE export runs.

Writes:
- ``site/public/data/boundaries/<slug>.geojson`` — single-feature file
  consumed by the per-park Leaflet map.
- ``site/public/data/boundaries/all_parks.geojson`` — FeatureCollection
  with one feature per park, including the park's headline warming slope
  as a property. Consumed by the national overview map on the home page.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from nps_climate_data.geography import PARK_GEOGRAPHY
from nps_climate_data.parks import get_parks

CIRCLE_POINTS = 32
REPO = Path(__file__).resolve().parents[1]
SITE_DATA = REPO / "site" / "public" / "data"
OUT_DIR = SITE_DATA / "boundaries"
PARKS_JSON = SITE_DATA / "parks.json"


def circle_polygon(lat: float, lon: float, area_km2: float) -> list[list[list[float]]]:
    """Return a GeoJSON Polygon coordinate ring approximating a circle of
    the given area, centred on (lat, lon). Longitude spacing is scaled by
    cos(lat) so the shape reads as roughly round on a web-Mercator map."""
    radius_km = math.sqrt(max(area_km2, 0.05) / math.pi)
    # 1 deg latitude ~= 111.32 km
    dlat = radius_km / 111.32
    dlon = radius_km / (111.32 * max(math.cos(math.radians(lat)), 0.05))
    ring: list[list[float]] = []
    for i in range(CIRCLE_POINTS):
        theta = 2 * math.pi * i / CIRCLE_POINTS
        ring.append([lon + dlon * math.cos(theta), lat + dlat * math.sin(theta)])
    ring.append(ring[0])  # close
    return [ring]


def _load_headline_slopes() -> dict[str, dict]:
    """Pull each park's headline temp/precip slopes out of parks.json if it
    exists. Missing fields degrade gracefully to None."""
    if not PARKS_JSON.exists():
        return {}
    data = json.loads(PARKS_JSON.read_text())
    out: dict[str, dict] = {}
    for p in data.get("parks", []):
        ht = p.get("headline_trends") or {}
        tmean = ht.get("tmean_c") or {}
        prcp = ht.get("prcp_mm") or {}
        out[p["slug"]] = {
            "tmean_slope": tmean.get("slope_per_year"),
            "tmean_sig": tmean.get("significant_95"),
            "prcp_slope": prcp.get("slope_per_year"),
            "prcp_sig": prcp.get("significant_95"),
        }
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    slopes = _load_headline_slopes()

    features: list[dict] = []
    written = 0
    for park in get_parks():
        slug = park["slug"]
        geo = PARK_GEOGRAPHY.get(slug)
        if geo is None:
            print(f"  ! no geography for {slug}, skipping")
            continue
        lat, lon, area = geo
        coords = circle_polygon(lat, lon, area)
        headline = slopes.get(slug, {})

        props = {
            "slug": slug,
            "unit_name": park["unit_name"],
            "state": park["state"],
            "area_km2": area,
            "centroid": [lon, lat],
            "approximate": True,
            **headline,
        }

        single = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": coords},
                "properties": props,
            }],
        }
        (OUT_DIR / f"{slug}.geojson").write_text(json.dumps(single))
        features.append(single["features"][0])
        written += 1

    combined = {"type": "FeatureCollection", "features": features}
    (OUT_DIR / "all_parks.geojson").write_text(json.dumps(combined))
    print(f"Wrote {written} park boundaries + all_parks.geojson to {OUT_DIR}")


if __name__ == "__main__":
    main()
