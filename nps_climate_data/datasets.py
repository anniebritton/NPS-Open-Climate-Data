"""
Climate dataset definitions for Google Earth Engine.

DAYMET v4 (CONUS + HI + PR): ~1km, 1980-present, daily.
ERA5-Land daily aggregated: ~11km, 1950-present, daily, global (used for AK
and the territorial parks not covered by DAYMET).
"""

DATASETS = [
    {
        "name": "DAYMET",
        "asset_id": "NASA/ORNL/DAYMET_V4",
        "bands": ["prcp", "srad", "swe", "tmax", "tmin", "vp"],
        "scale": 1000,
        "coverage": "CONUS_HI_PR",
        "start": "1980-01-01",
        # DAYMET ships in human-readable units already (°C, mm, W/m², kg/m², Pa).
        "transforms": {},
    },
    {
        "name": "ERA5",
        "asset_id": "ECMWF/ERA5_LAND/DAILY_AGGR",
        # Band names verified against the EE Data Catalog listing. Flow
        # (accumulated) bands use the '_sum' suffix; everything else is a
        # daily mean of the underlying hourly band.
        "bands": [
            "temperature_2m",
            "temperature_2m_min",
            "temperature_2m_max",
            "total_precipitation_sum",
            "v_component_of_wind_10m",
            "u_component_of_wind_10m",
            "snowmelt_sum",
            "snowfall_sum",
            "snow_cover",
            "snow_depth",
            "total_evaporation_sum",
            "potential_evaporation_sum",
        ],
        "scale": 11132,
        "coverage": "GLOBAL",
        "start": "1950-01-01",
        # Apply server-side so raw exports are unit-consistent with DAYMET:
        # temperatures in °C, water-flux bands in mm, evaporation flipped
        # positive (ECMWF convention is negative-into-surface).
        "transforms": {
            "temperature_2m":            ("subtract",  273.15),
            "temperature_2m_min":        ("subtract",  273.15),
            "temperature_2m_max":        ("subtract",  273.15),
            "total_precipitation_sum":   ("multiply",  1000.0),
            "snowmelt_sum":              ("multiply",  1000.0),
            "snowfall_sum":              ("multiply",  1000.0),
            "snow_depth":                ("multiply",  1000.0),
            "total_evaporation_sum":     ("multiply", -1000.0),
            "potential_evaporation_sum": ("multiply", -1000.0),
        },
    },
]


# Parks outside DAYMET coverage (Alaska, American Samoa, Virgin Islands)
# fall back to ERA5-only.
ERA5_ONLY_PARKS = {
    "denali",
    "gates-of-the-arctic",
    "glacier-bay",
    "katmai",
    "kenai-fjords",
    "kobuk-valley",
    "lake-clark",
    "wrangell-st-elias",
    "american-samoa",
    "virgin-islands",
}


def datasets_for_park(slug: str) -> list[dict]:
    if slug in ERA5_ONLY_PARKS:
        return [d for d in DATASETS if d["name"] == "ERA5"]
    return DATASETS
