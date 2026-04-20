"""
Geography table must cover all 63 parks, with plausible US lat/lon and
positive area. The circle-polygon generator must produce a closed ring
of the right arity.
"""

from nps_climate_data.geography import PARK_GEOGRAPHY
from nps_climate_data.parks import NATIONAL_PARKS

# Copy of the helper from scripts/05_generate_boundaries.py — kept inline
# so tests don't need to import a script module.
import math


def _circle(lat, lon, area_km2, n=32):
    radius_km = math.sqrt(max(area_km2, 0.05) / math.pi)
    dlat = radius_km / 111.32
    dlon = radius_km / (111.32 * max(math.cos(math.radians(lat)), 0.05))
    ring = []
    for i in range(n):
        theta = 2 * math.pi * i / n
        ring.append([lon + dlon * math.cos(theta), lat + dlat * math.sin(theta)])
    ring.append(ring[0])
    return ring


def test_geography_covers_every_park():
    slugs = {slug for _, _, slug in NATIONAL_PARKS}
    missing = slugs - set(PARK_GEOGRAPHY)
    assert not missing, f"Geography table missing: {missing}"


def test_latitudes_and_longitudes_plausible():
    for slug, (lat, lon, area) in PARK_GEOGRAPHY.items():
        # US + territories span roughly -14.5..71 lat, -170..-64 lon.
        assert -15 <= lat <= 72, f"{slug} lat out of range"
        assert -171 <= lon <= -64, f"{slug} lon out of range"
        assert area > 0, f"{slug} area not positive"


def test_circle_polygon_is_closed():
    ring = _circle(44.6, -110.5, 8983)
    assert ring[0] == ring[-1], "polygon ring not closed"
    assert len(ring) == 33, "expected 32+1 points"
