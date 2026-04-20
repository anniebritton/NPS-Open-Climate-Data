"""Unit tests for batch chunking logic."""

from nps_climate_data.batch import _chunk_years


def test_chunk_years_exclusive_end():
    pairs = list(_chunk_years("1980-01-01", "1984-12-31", chunk=5))
    # One chunk covering 1980-1984 inclusive; EE end must be 1985-01-01 (exclusive)
    assert pairs == [("1980-01-01", "1985-01-01")]


def test_chunk_years_multiple_chunks():
    pairs = list(_chunk_years("1980-01-01", "1989-12-31", chunk=5))
    assert pairs == [
        ("1980-01-01", "1985-01-01"),
        ("1985-01-01", "1990-01-01"),
    ]


def test_chunk_years_partial_final_chunk():
    pairs = list(_chunk_years("1980-01-01", "1986-06-30", chunk=5))
    assert pairs[0] == ("1980-01-01", "1985-01-01")
    # Last pair covers 1985-1986, end exclusive = 1987-01-01
    assert pairs[-1] == ("1985-01-01", "1987-01-01")


def test_chunk_years_single_year():
    pairs = list(_chunk_years("2024-01-01", "2024-12-31", chunk=5))
    assert pairs == [("2024-01-01", "2025-01-01")]
