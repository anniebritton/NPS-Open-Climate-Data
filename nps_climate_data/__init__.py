"""nps_climate_data: climate data pipeline for US National Parks.

Top-level re-exports avoid importing ``earthengine-api`` until a user
actually asks for the EE-facing helpers, so offline analyses
(``nps_climate_data.analysis``, ``nps_climate_data.carbon``) stay usable
on environments without EE credentials.

The Zenodo download helpers (``fetch_archive``, ``fetch_summary``,
``fetch_daily``, ``fetch_boundary``) pull pre-computed outputs from
the published dataset (DOI 10.5281/zenodo.19823584) — no EE needed.
"""

from .parks import get_parks, get_park, NATIONAL_PARKS
from .download import (
    fetch_archive,
    fetch_summary,
    fetch_daily,
    fetch_boundary,
    cache_dir,
    ZENODO_DOI,
    DATASET_VERSION,
)


def get_data(*args, **kwargs):
    from .core import get_data as _f
    return _f(*args, **kwargs)


def get_park_data(*args, **kwargs):
    from .core import get_park_data as _f
    return _f(*args, **kwargs)


__all__ = [
    "get_data",
    "get_park_data",
    "get_parks",
    "get_park",
    "NATIONAL_PARKS",
    "fetch_archive",
    "fetch_summary",
    "fetch_daily",
    "fetch_boundary",
    "cache_dir",
    "ZENODO_DOI",
    "DATASET_VERSION",
]
