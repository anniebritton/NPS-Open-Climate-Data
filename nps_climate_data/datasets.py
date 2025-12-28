# Dataset configurations ported from NPS-open-climate-data.js

DATASETS = [
    {
        "name": "DAYMET",
        "asset_id": "NASA/ORNL/DAYMET_V4",
        "bands": ["prcp", "srad", "swe", "tmax", "tmin", "vp"],
        "scale": 1000
    },
    {
        "name": "ERA5",
        "asset_id": "ECMWF/ERA5_LAND/DAILY_AGGR",
        "bands": [
            "temperature_2m",
            "temperature_2m_min",
            "temperature_2m_max",
            "v_component_of_wind_10m",
            "u_component_of_wind_10m",
            "snowmelt_sum",
            "snowfall_sum",
            "snow_cover",
            "snow_density",
            "snow_depth",
            "leaf_area_index_high_vegetation",
            "leaf_area_index_low_vegetation",
            "total_evaporation_sum",
            "potential_evaporation_sum"
        ],
        "scale": 11132
    }
]
