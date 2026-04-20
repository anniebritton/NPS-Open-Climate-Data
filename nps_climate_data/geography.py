"""
Centroid + approximate-area table for all 63 US National Parks.

Used to generate approximate boundary GeoJSONs for the website when real
PAD-US polygons aren't available locally (e.g. in CI before the EE export
has run). Areas (km^2) and centroids are public values from USGS / NPS
reports, rounded. Real polygons from PAD-US replace these at production
export time; the downstream map code reads whatever lives in
``site/public/data/boundaries/`` without caring about provenance.
"""

from __future__ import annotations

# slug -> (latitude, longitude, approximate area in km^2)
PARK_GEOGRAPHY: dict[str, tuple[float, float, float]] = {
    "acadia": (44.35, -68.22, 198),
    "american-samoa": (-14.25, -170.68, 35),
    "arches": (38.73, -109.59, 310),
    "badlands": (43.86, -102.34, 982),
    "big-bend": (29.25, -103.25, 3242),
    "biscayne": (25.48, -80.21, 700),
    "black-canyon-of-the-gunnison": (38.57, -107.72, 124),
    "bryce-canyon": (37.59, -112.19, 145),
    "canyonlands": (38.20, -109.93, 1366),
    "capitol-reef": (38.37, -111.27, 979),
    "carlsbad-caverns": (32.18, -104.44, 189),
    "channel-islands": (34.01, -119.42, 1009),
    "congaree": (33.79, -80.78, 107),
    "crater-lake": (42.94, -122.10, 741),
    "cuyahoga-valley": (41.28, -81.56, 133),
    "death-valley": (36.50, -117.10, 13793),
    "denali": (63.33, -150.50, 24585),
    "dry-tortugas": (24.63, -82.87, 262),
    "everglades": (25.28, -80.90, 6107),
    "gates-of-the-arctic": (67.78, -153.30, 30448),
    "gateway-arch": (38.63, -90.19, 0.3),
    "glacier": (48.75, -113.75, 4101),
    "glacier-bay": (58.67, -136.90, 13287),
    "grand-canyon": (36.05, -112.14, 4926),
    "grand-teton": (43.79, -110.68, 1254),
    "great-basin": (38.98, -114.30, 312),
    "great-sand-dunes": (37.73, -105.51, 434),
    "great-smoky-mountains": (35.68, -83.53, 2114),
    "guadalupe-mountains": (31.92, -104.87, 349),
    "haleakala": (20.72, -156.17, 134),
    "hawaii-volcanoes": (19.38, -155.20, 1348),
    "hot-springs": (34.52, -93.05, 22),
    "indiana-dunes": (41.65, -87.05, 61),
    "isle-royale": (48.10, -88.55, 2314),
    "joshua-tree": (33.88, -115.90, 3218),
    "katmai": (58.50, -155.00, 19122),
    "kenai-fjords": (59.92, -149.65, 2711),
    "kings-canyon": (36.80, -118.55, 1870),
    "kobuk-valley": (67.55, -159.28, 7085),
    "lake-clark": (60.42, -153.42, 16308),
    "lassen-volcanic": (40.49, -121.51, 431),
    "mammoth-cave": (37.19, -86.10, 215),
    "mesa-verde": (37.18, -108.49, 212),
    "mount-rainier": (46.85, -121.75, 956),
    "new-river-gorge": (37.88, -81.07, 285),
    "north-cascades": (48.70, -121.20, 2043),
    "olympic": (47.80, -123.60, 3734),
    "petrified-forest": (34.91, -109.81, 895),
    "pinnacles": (36.49, -121.18, 107),
    "redwood": (41.30, -124.00, 562),
    "rocky-mountain": (40.34, -105.69, 1076),
    "saguaro": (32.25, -110.80, 371),
    "sequoia": (36.49, -118.57, 1636),
    "shenandoah": (38.53, -78.35, 802),
    "theodore-roosevelt": (46.97, -103.45, 285),
    "virgin-islands": (18.34, -64.73, 60),
    "voyageurs": (48.50, -92.88, 883),
    "white-sands": (32.78, -106.17, 592),
    "wind-cave": (43.62, -103.48, 137),
    "wrangell-st-elias": (61.71, -142.98, 33682),
    "yellowstone": (44.60, -110.50, 8983),
    "yosemite": (37.83, -119.50, 3081),
    "zion": (37.30, -113.05, 593),
}


def centroid(slug: str) -> tuple[float, float] | None:
    g = PARK_GEOGRAPHY.get(slug)
    return (g[0], g[1]) if g else None


def area_km2(slug: str) -> float | None:
    g = PARK_GEOGRAPHY.get(slug)
    return g[2] if g else None
