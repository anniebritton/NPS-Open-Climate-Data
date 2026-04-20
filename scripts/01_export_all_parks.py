"""Full batch export of daily climate data for every US National Park.

Requires Earth Engine credentials. Writes Parquet + CSV per park (and per
sub-unit for multipart parks) to ``data/raw/<slug>/``.

Usage::

    earthengine authenticate   # one-time
    python scripts/01_export_all_parks.py \
        --start 1980-01-01 --end 2025-01-01

End dates are EXCLUSIVE (Earth Engine semantics).
"""

import argparse

import ee

from nps_climate_data.batch import export_all


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="1980-01-01")
    p.add_argument("--end", default=None,
                   help="EXCLUSIVE upper bound; default = tomorrow")
    p.add_argument("--out", default="data")
    p.add_argument("--slugs", nargs="*", help="optional subset of park slugs")
    args = p.parse_args()

    ee.Initialize()
    export_all(args.out, start=args.start, end=args.end, slugs=args.slugs)


if __name__ == "__main__":
    main()
