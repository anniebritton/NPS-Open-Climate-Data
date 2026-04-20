"""Download completed EE export CSVs from Google Drive to data/raw/.

Run this after Earth Engine export tasks have completed (check status at
https://code.earthengine.google.com/tasks).

Requires Drive read access via Application Default Credentials. Run once
in your terminal before using this script::

    gcloud auth application-default login \\
        --scopes=https://www.googleapis.com/auth/drive.readonly,\\
                 https://www.googleapis.com/auth/cloud-platform

Also requires the Drive API client library::

    pip install google-api-python-client

Usage::

    # Download all parks from the default Drive folder
    python scripts/07_download_from_drive.py

    # Download a specific folder / output location
    python scripts/07_download_from_drive.py \\
        --drive-folder NPS_Climate_Data --out data

    # Download only a subset of parks
    python scripts/07_download_from_drive.py --slugs yellowstone glacier
"""

import argparse
from pathlib import Path

from nps_climate_data.batch import download_from_drive
from nps_climate_data.parks import get_parks


def _expand_stems(slugs: list[str]) -> list[str]:
    """Include base slug plus potential multipart stems."""
    stems = []
    for slug in slugs:
        stems.append(slug)
        for i in range(10):
            stems.append(f"{slug}_part-{i}")
    return stems


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--drive-folder", default="NPS_Climate_Data",
                   help="Google Drive folder name (must match what was used during export)")
    p.add_argument("--out", default="data",
                   help="Local root directory; CSVs go to <out>/raw/<slug>/")
    p.add_argument("--slugs", nargs="*",
                   help="Optional subset of park slugs to download")
    args = p.parse_args()

    stems = _expand_stems(args.slugs) if args.slugs else None
    download_from_drive(args.drive_folder, Path(args.out), stems=stems)


if __name__ == "__main__":
    main()
