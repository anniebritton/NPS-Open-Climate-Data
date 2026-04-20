"""Unit tests for the analysis module. No network / Earth Engine needed."""

import math

import numpy as np
import pandas as pd
import pytest

from nps_climate_data import analysis as A


def _daily_frame(years=(1980, 2023), tmax=None, tmin=None, prcp=None, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.date_range(f"{years[0]}-01-01", f"{years[1]}-12-31", freq="D")
    n = len(dates)
    doy = dates.dayofyear
    # seasonal cycle + warming trend
    warming = (dates.year - years[0]) * 0.03  # +0.03 C/yr baseline
    t_season = -10 + 20 * np.sin((doy - 80) / 365 * 2 * np.pi)
    base_max = t_season + 8 + warming + rng.normal(0, 2, n)
    base_min = t_season - 2 + warming * 0.8 + rng.normal(0, 2, n)
    precip = np.maximum(0, rng.gamma(0.7, 3.0, n) - 0.5)

    df = pd.DataFrame({
        "date": dates,
        "DAYMET_tmax": base_max if tmax is None else tmax,
        "DAYMET_tmin": base_min if tmin is None else tmin,
        "DAYMET_prcp": precip if prcp is None else prcp,
    })
    return df


def test_canonicalise_daymet_columns():
    df = _daily_frame()
    c = A.canonicalise(df)
    assert "tmax_c" in c.columns
    assert "tmin_c" in c.columns
    assert "prcp_mm" in c.columns
    # tmean derived when missing
    assert "tmean_c" in c.columns
    assert np.allclose(c["tmean_c"], (c["tmax_c"] + c["tmin_c"]) / 2)


def test_canonicalise_era5_kelvin_conversion():
    dates = pd.date_range("2020-01-01", periods=3, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "ERA5_temperature_2m_max": [273.15, 283.15, 293.15],
        "ERA5_temperature_2m_min": [263.15, 273.15, 283.15],
    })
    c = A.canonicalise(df)
    assert np.allclose(c["tmax_c"], [0, 10, 20])
    assert np.allclose(c["tmin_c"], [-10, 0, 10])


def test_canonicalise_daymet_wins_over_era5():
    dates = pd.date_range("2020-01-01", periods=3, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "DAYMET_tmax": [5.0, 10.0, np.nan],
        "ERA5_temperature_2m_max": [278.15, 288.15, 298.15],  # 5, 15, 25 C
    })
    c = A.canonicalise(df)
    # Where DAYMET is NaN, ERA5 should fill in
    assert c["tmax_c"].iloc[0] == 5.0
    assert c["tmax_c"].iloc[1] == 10.0
    assert c["tmax_c"].iloc[2] == pytest.approx(25.0)


def test_annual_aggregation_sums_precip_and_averages_temp():
    df = _daily_frame(years=(2000, 2001))
    c = A.canonicalise(df)
    ann = A.annual(c)
    assert set(ann["year"]) == {2000, 2001}
    # Precip is summed
    manual_sum = c.loc[c["date"].dt.year == 2000, "prcp_mm"].sum()
    assert math.isclose(ann.loc[ann["year"] == 2000, "prcp_mm"].iloc[0], manual_sum, rel_tol=1e-6)
    # Tmean is averaged
    manual_mean = c.loc[c["date"].dt.year == 2000, "tmean_c"].mean()
    assert math.isclose(ann.loc[ann["year"] == 2000, "tmean_c"].iloc[0], manual_mean, rel_tol=1e-6)


def test_annual_drops_short_years():
    # Only 3 days of data - should be dropped by >=330 threshold
    dates = pd.date_range("2005-01-01", periods=3, freq="D")
    df = pd.DataFrame({"date": dates, "DAYMET_tmax": [1.0, 2.0, 3.0], "DAYMET_tmin": [0.0, 1.0, 2.0]})
    c = A.canonicalise(df)
    ann = A.annual(c)
    assert ann.empty


def test_seasonal_djf_crosses_year_boundary():
    # Dec 2020 should aggregate with Jan-Feb 2021 under the 2021 water-season
    dates = pd.date_range("2020-12-01", "2021-02-28", freq="D")
    df = pd.DataFrame({"date": dates,
                       "DAYMET_tmax": np.ones(len(dates)) * 5.0,
                       "DAYMET_tmin": np.ones(len(dates)) * -5.0})
    c = A.canonicalise(df)
    seas = A.seasonal(c)
    djf = seas[(seas["season"] == "DJF") & (seas["year"] == 2021)]
    assert not djf.empty
    assert djf["tmean_c"].iloc[0] == pytest.approx(0.0)


def test_mann_kendall_detects_strong_trend():
    df = _daily_frame()
    ann = A.annual(A.canonicalise(df))
    t = A.trend(ann, "tmean_c")
    assert t is not None
    # Our fixture warms ~0.03 C/yr (plus some from tmin slope of 0.8x) so
    # expect a positive, highly significant slope.
    assert t.slope_per_year > 0.01
    assert t.p_value < 0.01
    assert t.significant_95


def test_mann_kendall_flat_series():
    ann = pd.DataFrame({"year": list(range(1980, 2021)), "tmean_c": [10.0] * 41})
    t = A.trend(ann, "tmean_c")
    assert t is not None
    assert abs(t.slope_per_year) < 1e-9
    # flat -> not significant
    assert not t.significant_95


def test_theil_sen_matches_known_line():
    # y = 2x + 1, exact
    ann = pd.DataFrame({"year": list(range(2000, 2021)),
                        "tmean_c": [2 * y + 1 for y in range(2000, 2021)]})
    t = A.trend(ann, "tmean_c")
    assert t is not None
    assert t.slope_per_year == pytest.approx(2.0)


def test_anomalies_reference_period():
    ann = pd.DataFrame({"year": list(range(1980, 2021)),
                        "tmean_c": [float(y - 2000) for y in range(1980, 2021)]})
    anom = A.anomalies(ann, ref=(1981, 2010))
    # ref mean of (1981..2010 - 2000) values = mean(-19..10) = -4.5
    ref_mean = sum(range(-19, 11)) / 30.0
    assert anom["tmean_c_anom"].iloc[0] == pytest.approx(ann["tmean_c"].iloc[0] - ref_mean)


def test_climate_stripes_shape():
    df = _daily_frame(years=(2000, 2010))
    ann = A.annual(A.canonicalise(df))
    stripes = A.climate_stripes(ann, "tmean_c")
    assert len(stripes) == ann.shape[0]
    for s in stripes:
        assert {"year", "value", "z"}.issubset(s)
