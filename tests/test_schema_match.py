"""
Guard against drift between what EE returns and what our canonicaliser
looks for. Every source column listed in analysis.CANONICAL must be
constructible from a (dataset prefix, band) pair declared in
``datasets.DATASETS``.
"""

import numpy as np
import pandas as pd

from nps_climate_data import analysis as A
from nps_climate_data.datasets import DATASETS


def _available_columns() -> set[str]:
    cols: set[str] = set()
    for ds in DATASETS:
        for b in ds["bands"]:
            cols.add(f"{ds['name']}_{b}")
    return cols


def test_every_canonical_source_is_declared():
    available = _available_columns()
    missing = []
    for canon, sources in A.CANONICAL.items():
        for col, _unit in sources:
            if col not in available:
                missing.append(f"{canon} <- {col}")
    assert not missing, f"Canonical mapping refers to undeclared bands: {missing}"


def test_every_canonical_variable_is_reachable_for_a_park():
    """For each canonical variable, at least one dataset that provides it is
    included in the default dataset list."""
    available = _available_columns()
    for canon, sources in A.CANONICAL.items():
        assert any(c in available for c, _ in sources), canon


def test_evaporation_passthrough_positive_mm():
    # Server-side transforms (datasets.py) sign-flip ECMWF evaporation and
    # convert m → mm before the data ever lands in a CSV, so canonicalise()
    # passes positive mm/day through unchanged.
    df = pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=3, freq="D"),
        "ERA5_total_evaporation_sum": [1.0, 2.0, 3.0],
        "ERA5_potential_evaporation_sum": [2.0, 4.0, 6.0],
    })
    c = A.canonicalise(df)
    assert np.allclose(c["aet_mm"], [1.0, 2.0, 3.0])
    assert np.allclose(c["pet_mm"], [2.0, 4.0, 6.0])


def test_era5_precip_passthrough_mm():
    # As above: raw ERA5 precipitation arrives in mm after the EE-side
    # transform; canonicalise() does not re-scale.
    df = pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=3, freq="D"),
        "ERA5_total_precipitation_sum": [1.0, 10.0, 25.0],
    })
    c = A.canonicalise(df)
    assert np.allclose(c["prcp_mm"], [1.0, 10.0, 25.0])
