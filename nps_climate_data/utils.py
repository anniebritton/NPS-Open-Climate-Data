import ee


# PAD-US Unit_Nm for Alaskan "NP and Preserve" parks differs from the
# shorthand "National Park" we use publicly. Same for a few other units.
# Values here are the exact string in PAD-US v20 proclamation (verified via
# NPS / USGS PAD-US data manual conventions).
PADUS_UNIT_ALIASES: dict[str, list[str]] = {
    "Denali National Park": ["Denali National Park and Preserve", "Denali National Park"],
    "Gates of the Arctic National Park": [
        "Gates of the Arctic National Park and Preserve",
        "Gates of the Arctic National Park",
    ],
    "Glacier Bay National Park": [
        "Glacier Bay National Park and Preserve",
        "Glacier Bay National Park",
    ],
    "Katmai National Park": ["Katmai National Park and Preserve", "Katmai National Park"],
    "Lake Clark National Park": [
        "Lake Clark National Park and Preserve",
        "Lake Clark National Park",
    ],
    "Wrangell-St. Elias National Park": [
        "Wrangell-St. Elias National Park and Preserve",
        "Wrangell-St. Elias National Park",
    ],
    "Hawaii Volcanoes National Park": [
        "Hawaii Volcanoes National Park",
        "Hawai'i Volcanoes National Park",
    ],
    "Haleakala National Park": ["Haleakala National Park", "Haleakalā National Park"],
}


def get_park_boundary(park_name: str) -> ee.FeatureCollection:
    """
    Retrieves park geometry from PAD-US v20 proclamation boundaries.

    Uses Unit_Nm (with per-park aliases for the Alaskan National Park &
    Preserve units and diacritic variants) and restricts to NPS-managed
    units so we don't accidentally pick up identically-named features from
    other agencies. Returns an ee.FeatureCollection which may contain
    multiple features for parks with disjoint sub-units (split downstream).
    """
    base = ee.FeatureCollection("USGS/GAP/PAD-US/v20/proclamation")
    names = PADUS_UNIT_ALIASES.get(park_name, [park_name])
    name_filter = ee.Filter.inList("Unit_Nm", names)
    # Most NPS units are tagged Mang_Name == 'NPS' in PAD-US; keep the
    # filter as a belt-and-braces check. The OR fallback keeps things
    # working even if an individual feature is missing the field.
    nps_filter = ee.Filter.Or(
        ee.Filter.eq("Mang_Name", "NPS"),
        ee.Filter.eq("Mang_Type", "FED"),
    )
    return base.filter(name_filter).filter(nps_filter)


def split_multipart_features(fc: ee.FeatureCollection, max_parts: int = 8) -> ee.FeatureCollection:
    """
    Split an NPS unit into its disjoint geometric components so that
    parks like Saguaro NP (two districts) or Channel Islands NP (five
    islands) produce one feature per connected polygon.

    Each resulting feature carries a 'part_index' property (0..N-1).
    If the unit is a single contiguous polygon, a single feature is
    returned with part_index=0.
    """
    geom = fc.geometry()
    # ee.Geometry.geometries() returns the list of individual geometries in
    # a GeometryCollection / MultiPolygon.
    parts = geom.geometries()
    n = ee.Number(parts.size()).min(max_parts)

    def _to_feature(i):
        i = ee.Number(i)
        g = ee.Geometry(parts.get(i))
        return ee.Feature(g, {"part_index": i})

    indices = ee.List.sequence(0, n.subtract(1))
    return ee.FeatureCollection(indices.map(_to_feature))


def union_geometry(fc: ee.FeatureCollection) -> ee.Geometry:
    """Return a single unioned geometry for a feature collection."""
    return fc.geometry()
