"""Stdlib-only helpers for fetching the Zenodo-hosted dataset.

The full versioned dataset lives on Zenodo
(DOI: ``10.5281/zenodo.19823584``). This module pulls + caches each
archive locally so callers don't have to deal with HTTP, gzip, or
unzip plumbing themselves.

Cache location: ``$XDG_CACHE_HOME/nps_climate_data/`` if set, else
``~/.cache/nps_climate_data/``. Override with the
``NPS_CLIMATE_DATA_CACHE`` environment variable. Subsequent calls are
served from disk; pass ``force=True`` to re-download.

Public surface (re-exported from the package root)::

    nps.fetch_archive("summary")          → Path to extracted dir
    nps.fetch_summary("yellowstone")      → dict
    nps.fetch_daily("yellowstone")        → pandas.DataFrame
    nps.fetch_boundary("yellowstone")     → dict (parsed GeoJSON)

Pandas is only imported when ``fetch_daily`` is actually called, so
that environments without pandas still get the JSON / GeoJSON helpers.
"""

from __future__ import annotations

import gzip
import json
import os
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Literal

ZENODO_RECORD = "19823584"
ZENODO_DOI = "10.5281/zenodo.19823584"
DATASET_VERSION = "v1.0.0"
_BASE_URL = f"https://zenodo.org/records/{ZENODO_RECORD}/files"
_ROOT_DIR = f"nps-open-climate-data-{DATASET_VERSION}"

ArchiveKind = Literal["all", "daily", "summary", "boundaries"]

ARCHIVE_FILES: dict[str, str] = {
    "all":        f"nps-open-climate-data-{DATASET_VERSION}-all.zip",
    "daily":      f"nps-open-climate-data-{DATASET_VERSION}-daily.zip",
    "summary":    f"nps-open-climate-data-{DATASET_VERSION}-summary.zip",
    "boundaries": f"nps-open-climate-data-{DATASET_VERSION}-boundaries.zip",
}


def cache_dir() -> Path:
    """Return the local cache directory, creating it if needed."""
    override = os.environ.get("NPS_CLIMATE_DATA_CACHE")
    if override:
        root = Path(override)
    else:
        xdg = os.environ.get("XDG_CACHE_HOME")
        root = Path(xdg) if xdg else Path.home() / ".cache"
        root = root / "nps_climate_data"
    root.mkdir(parents=True, exist_ok=True)
    return root


def fetch_archive(kind: ArchiveKind = "summary", *, force: bool = False) -> Path:
    """Download a Zenodo archive and return the path to the extracted root.

    Parameters
    ----------
    kind : "all" | "daily" | "summary" | "boundaries"
        Which subset to fetch. The "all" archive is a superset of the
        other three; the smaller ones are faster if you only need part
        of the data.
    force : bool
        If True, re-download and re-extract even if the cache already
        has the files.

    Returns
    -------
    Path
        The directory containing the extracted archive (the
        ``nps-open-climate-data-vX.Y.Z/`` folder). Sub-paths follow
        ``daily/<slug>/<file>.csv.gz``, ``summary/<slug>.json``,
        ``boundaries/<slug>.geojson``.
    """
    if kind not in ARCHIVE_FILES:
        raise ValueError(f"kind must be one of {sorted(ARCHIVE_FILES)}; got {kind!r}")

    cache = cache_dir()
    extract_root = cache / f"{_ROOT_DIR}-{kind}"
    if extract_root.exists() and any(extract_root.iterdir()) and not force:
        return extract_root

    zip_path = cache / ARCHIVE_FILES[kind]
    if not zip_path.exists() or force:
        url = f"{_BASE_URL}/{ARCHIVE_FILES[kind]}?download=1"
        # urllib.request follows the Zenodo redirect to S3.
        urllib.request.urlretrieve(url, zip_path)

    # Extract under a kind-specific dir so multiple archives can coexist.
    if extract_root.exists():
        # force=True path; rebuild from scratch to avoid stale files.
        import shutil
        shutil.rmtree(extract_root)
    extract_root.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_root)
    return extract_root


def _content_root(extract_root: Path) -> Path:
    """Resolve `<extract_root>/<archive top-level dir>` if the zip has one,
    otherwise return ``extract_root`` unchanged."""
    candidate = extract_root / _ROOT_DIR
    return candidate if candidate.is_dir() else extract_root


def fetch_summary(slug: str, *, force: bool = False) -> dict[str, Any]:
    """Return the per-park summary JSON for ``slug``."""
    root = _content_root(fetch_archive("summary", force=force))
    path = root / "summary" / f"{slug}.json"
    if not path.is_file():
        raise FileNotFoundError(f"No summary in archive for slug {slug!r}: {path}")
    return json.loads(path.read_text())


def fetch_boundary(slug: str, *, force: bool = False) -> dict[str, Any]:
    """Return the parsed PAD-US 4.1 boundary GeoJSON for ``slug``."""
    root = _content_root(fetch_archive("boundaries", force=force))
    path = root / "boundaries" / f"{slug}.geojson"
    if not path.is_file():
        raise FileNotFoundError(f"No boundary in archive for slug {slug!r}: {path}")
    return json.loads(path.read_text())


def fetch_daily(slug: str, *, force: bool = False):
    """Return a pandas DataFrame of the raw daily series for ``slug``.

    Multipart parks (Saguaro, Channel Islands, etc.) ship one CSV per
    polygon; this function concatenates them with a ``part`` column so
    callers can group / filter as needed.
    """
    import pandas as pd  # imported lazily so JSON-only callers don't pay

    root = _content_root(fetch_archive("daily", force=force))
    park_dir = root / "daily" / slug
    if not park_dir.is_dir():
        raise FileNotFoundError(f"No daily archive for slug {slug!r}: {park_dir}")
    csvs = sorted(park_dir.glob("*.csv.gz"))
    if not csvs:
        raise FileNotFoundError(f"No .csv.gz files under {park_dir}")
    frames = []
    for csv in csvs:
        with gzip.open(csv, "rb") as f:
            df = pd.read_csv(f)
        df["part"] = csv.stem.replace(".csv", "")
        frames.append(df)
    if len(frames) == 1:
        return frames[0].drop(columns="part")
    return pd.concat(frames, ignore_index=True)


__all__ = [
    "ZENODO_DOI",
    "ZENODO_RECORD",
    "DATASET_VERSION",
    "ARCHIVE_FILES",
    "cache_dir",
    "fetch_archive",
    "fetch_summary",
    "fetch_boundary",
    "fetch_daily",
]
