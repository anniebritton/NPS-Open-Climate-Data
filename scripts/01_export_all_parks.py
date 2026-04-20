"""Submit Earth Engine export tasks for all 63 US National Parks.

Tasks run serverlessly on GEE infrastructure and write per-park CSVs to
a Google Drive folder. Once submitted you can close the terminal — tasks
continue running on Google's servers.

Usage::

    # Authenticate once (stores credentials locally)
    earthengine authenticate

    # Submit tasks for all parks (returns immediately)
    python scripts/01_export_all_parks.py --drive-folder NPS_Climate_Data

    # Submit for a subset of parks
    python scripts/01_export_all_parks.py --slugs yellowstone glacier

    # Submit and block until all tasks finish (~2-4 hours for 63 parks)
    python scripts/01_export_all_parks.py --wait

Monitor running tasks at: https://code.earthengine.google.com/tasks

After tasks complete, download results with::

    python scripts/07_download_from_drive.py --drive-folder NPS_Climate_Data

End dates are EXCLUSIVE (Earth Engine filterDate convention).
"""

import argparse

import ee

from nps_climate_data.batch import submit_all_tasks, wait_for_tasks


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--start", default="1980-01-01",
                   help="Start date (inclusive). Default: 1980-01-01")
    p.add_argument("--end", default=None,
                   help="End date (exclusive). Default: today")
    p.add_argument("--drive-folder", default="NPS_Climate_Data",
                   help="Google Drive folder name for exported CSVs")
    p.add_argument("--slugs", nargs="*",
                   help="Optional subset of park slugs (default: all 63 parks)")
    p.add_argument("--wait", action="store_true",
                   help="Block and poll until all tasks complete")
    args = p.parse_args()

    ee.Initialize()
    task_infos = submit_all_tasks(
        drive_folder=args.drive_folder,
        start=args.start,
        end=args.end,
        slugs=args.slugs,
    )

    if args.wait and task_infos:
        wait_for_tasks(task_infos)


if __name__ == "__main__":
    main()
