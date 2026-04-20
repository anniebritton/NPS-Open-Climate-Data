"""
Batch export driver for all 63 US National Parks.

Task-based (default)
--------------------
Submits ``ee.batch.Export.table.toDrive`` tasks — serverless, async.
Tasks run on GEE infrastructure; you can close the terminal once they
are submitted. Use ``submit_all_tasks`` / ``wait_for_tasks``, then
``download_from_drive`` to pull the CSVs back locally.

Interactive (legacy)
--------------------
``export_all`` / ``export_park`` pull data synchronously via
``getInfo``. Kept for small ad-hoc queries; not suitable for the
full 1980-present range (response-size limits require chunking, which
makes large runs fragile and slow).
"""

from __future__ import annotations

import io
import time
import traceback
from pathlib import Path

import pandas as pd

from .datasets import datasets_for_park
from .parks import get_parks


# ── Task-based export (serverless, async) ────────────────────────────────────

def submit_park_tasks(
    park: dict,
    drive_folder: str,
    start: str,
    end: str | None = None,
) -> list[dict]:
    """Submit EE export tasks for one park.

    Returns a list of dicts with keys ``slug``, ``stem``, ``task``.
    Multipart parks (e.g. Saguaro, Channel Islands) produce one task
    per sub-unit.
    """
    import datetime
    import ee
    from .utils import get_park_boundary, split_multipart_features
    from .core import make_export_task

    if end is None:
        end = datetime.date.today().isoformat()

    slug = park["slug"]
    ds = datasets_for_park(slug)
    scale = min(d["scale"] for d in ds)

    aoi_fc = get_park_boundary(park["unit_name"])
    if aoi_fc.size().getInfo() == 0:
        print(f"  SKIP {slug}: not found in PAD-US")
        return []

    task_infos: list[dict] = []

    if park["multipart"]:
        parts = split_multipart_features(aoi_fc).getInfo()["features"]
        for i, feat in enumerate(parts):
            geom = ee.Geometry(feat["geometry"])
            stem = f"{slug}_part-{i}"
            desc = f"nps-{stem}"[:100]
            task = make_export_task(
                park_name=park["unit_name"],
                start_date=start,
                end_date=end,
                geom=geom,
                scale=scale,
                datasets=ds,
                description=desc,
                drive_folder=drive_folder,
                file_prefix=stem,
            )
            task.start()
            task_infos.append({"slug": slug, "stem": stem, "task": task})
            print(f"  submitted: {desc}")
    else:
        desc = f"nps-{slug}"[:100]
        task = make_export_task(
            park_name=park["unit_name"],
            start_date=start,
            end_date=end,
            geom=aoi_fc.geometry(),
            scale=scale,
            datasets=ds,
            description=desc,
            drive_folder=drive_folder,
            file_prefix=slug,
        )
        task.start()
        task_infos.append({"slug": slug, "stem": slug, "task": task})
        print(f"  submitted: {desc}")

    return task_infos


def submit_all_tasks(
    drive_folder: str = "NPS_Climate_Data",
    start: str = "1980-01-01",
    end: str | None = None,
    slugs: list[str] | None = None,
) -> list[dict]:
    """Submit EE export tasks for all (or a subset of) parks.

    Returns the full list of task-info dicts so you can pass them to
    ``wait_for_tasks`` if you want to block until completion.
    """
    if end is None:
        end = pd.Timestamp.utcnow().strftime("%Y-%m-%d")

    parks = get_parks()
    if slugs:
        parks = [p for p in parks if p["slug"] in set(slugs)]

    all_tasks: list[dict] = []
    for park in parks:
        print(f"[{park['slug']}] submitting...")
        try:
            tasks = submit_park_tasks(park, drive_folder, start, end)
            all_tasks.extend(tasks)
        except Exception:
            traceback.print_exc()

    n = len(all_tasks)
    print(f"\nSubmitted {n} task{'s' if n != 1 else ''}.")
    print("Monitor at: https://code.earthengine.google.com/tasks")
    return all_tasks


def wait_for_tasks(task_infos: list[dict], poll_interval: int = 30) -> None:
    """Poll EE task status until every task has completed or failed."""
    pending = list(task_infos)
    while pending:
        still_pending = []
        for info in pending:
            state = info["task"].status()["state"]
            if state in ("COMPLETED", "FAILED", "CANCELLED"):
                mark = "✓" if state == "COMPLETED" else "✗"
                print(f"  {mark} {info['stem']}: {state}")
            else:
                still_pending.append(info)
        if still_pending:
            print(
                f"  {len(still_pending)} tasks still running — "
                f"checking again in {poll_interval}s..."
            )
            time.sleep(poll_interval)
        pending = still_pending
    print("All tasks finished.")


def download_from_drive(
    drive_folder: str,
    out_root: Path | str,
    stems: list[str] | None = None,
    quota_project: str | None = None,
) -> None:
    """Download completed export CSVs from Google Drive to ``out_root/raw/``.

    Requires Application Default Credentials with Drive read access.
    Before calling this, run once in your terminal::

        gcloud auth application-default login \\
            --scopes=https://www.googleapis.com/auth/drive.readonly,\\
                     https://www.googleapis.com/auth/cloud-platform

    Parameters
    ----------
    drive_folder:
        The Drive folder name used when tasks were submitted
        (default ``"NPS_Climate_Data"``).
    out_root:
        Local root; CSVs land at ``out_root/raw/<slug>/<stem>.csv``.
    stems:
        Optional allowlist of file stems (e.g. ``["yellowstone",
        "saguaro_part-0"]``). Downloads everything if ``None``.
    """
    try:
        import google.auth
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload
    except ImportError as exc:
        raise ImportError(
            "google-api-python-client is required for Drive downloads.\n"
            "Install it: pip install google-api-python-client"
        ) from exc

    out_root = Path(out_root)

    try:
        creds, detected_project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
        # ADC credentials obtained without --billing-project don't carry a
        # quota project, which causes a 403. Apply one if available.
        qp = quota_project or detected_project
        if qp and hasattr(creds, "with_quota_project"):
            creds = creds.with_quota_project(qp)
    except Exception as exc:
        raise RuntimeError(
            "Google credentials not found. Run:\n"
            "  gcloud auth application-default login \\\n"
            "    --scopes=https://www.googleapis.com/auth/drive.readonly,"
            "https://www.googleapis.com/auth/cloud-platform"
        ) from exc

    service = build("drive", "v3", credentials=creds)

    # Locate the Drive folder
    q = (
        f"name='{drive_folder}' and "
        "mimeType='application/vnd.google-apps.folder' and trashed=false"
    )
    folders = service.files().list(q=q, fields="files(id,name)").execute().get("files", [])
    if not folders:
        raise ValueError(
            f"Drive folder '{drive_folder}' not found. "
            "Check the name and that tasks have completed."
        )
    folder_id = folders[0]["id"]

    # List CSV files in the folder
    q = f"'{folder_id}' in parents and name contains '.csv' and trashed=false"
    files = (
        service.files()
        .list(q=q, fields="files(id,name,size)", pageSize=500)
        .execute()
        .get("files", [])
    )
    if not files:
        print(f"No CSV files found in Drive folder '{drive_folder}'.")
        return

    for file_info in files:
        name = file_info["name"]
        stem = name.removesuffix(".csv")
        slug = stem.split("_part-")[0]

        if stems and stem not in stems:
            continue

        out_dir = out_root / "raw" / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / name

        request = service.files().get_media(fileId=file_info["id"])
        with io.FileIO(str(out_path), "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

        size_mb = int(file_info.get("size", 0)) / 1e6
        print(f"  ✓ {name} ({size_mb:.1f} MB) → {out_path}")

    print(f"\nDownload complete. Raw CSVs in {out_root / 'raw'}/")


# ── Interactive / legacy export ───────────────────────────────────────────────
# Use these for small ad-hoc queries or debugging. For full 1980-present
# runs, prefer the task-based functions above.

def _chunk_years(start: str, end: str, chunk: int = 5):
    """Yield (start, end) ISO date pairs in ``chunk``-year windows."""
    s = pd.Timestamp(start).year
    last_year = pd.Timestamp(end).year
    y = s
    while y <= last_year:
        y_end = min(y + chunk - 1, last_year)
        yield f"{y}-01-01", f"{y_end + 1}-01-01"
        y = y_end + 1


def _fetch_range(park_name, start, end, scale, datasets, geom):
    from .core import get_data
    frames = []
    for s, e in _chunk_years(start, end, chunk=5):
        df = get_data(park_name, s, e, scale=scale, datasets=datasets, aoi_geom=geom)
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"])
    return out.drop_duplicates("date").sort_values("date").reset_index(drop=True)


def _write(df: pd.DataFrame, out_dir: Path, stem: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / f"{stem}.csv", index=False)
    try:
        df.to_parquet(out_dir / f"{stem}.parquet", index=False)
    except Exception as exc:
        print(f"  parquet write failed ({exc}); csv written")


def export_park(park: dict, out_root: Path, start: str, end: str) -> list[Path]:
    """Interactive export for one park. Returns list of files written."""
    import ee
    from .utils import get_park_boundary, split_multipart_features

    slug = park["slug"]
    ds = datasets_for_park(slug)
    scale = min(d["scale"] for d in ds)
    park_dir = out_root / "raw" / slug
    written: list[Path] = []

    aoi_fc = get_park_boundary(park["unit_name"])
    if aoi_fc.size().getInfo() == 0:
        print(f"  SKIP {slug}: not found in PAD-US")
        return written

    if park["multipart"]:
        parts = split_multipart_features(aoi_fc).getInfo()["features"]
        for i, feat in enumerate(parts):
            geom = ee.Geometry(feat["geometry"])
            df = _fetch_range(park["unit_name"], start, end, scale, ds, geom)
            stem = f"{slug}_part-{i}"
            _write(df, park_dir, stem)
            written.append(park_dir / f"{stem}.parquet")
    else:
        df = _fetch_range(park["unit_name"], start, end, scale, ds, aoi_fc.geometry())
        _write(df, park_dir, slug)
        written.append(park_dir / f"{slug}.parquet")
    return written


def export_all(
    out_root: str | Path = "data",
    start: str = "1980-01-01",
    end: str | None = None,
    slugs: list[str] | None = None,
) -> None:
    """Interactive export for all parks. Prefer ``submit_all_tasks`` for
    production runs — this function blocks for hours and is sensitive to
    network interruptions."""
    out = Path(out_root)
    if end is None:
        end = pd.Timestamp.utcnow().strftime("%Y-%m-%d")
    parks = get_parks()
    if slugs:
        parks = [p for p in parks if p["slug"] in set(slugs)]

    for park in parks:
        print(f"[{park['slug']}] starting interactive export")
        t0 = time.time()
        try:
            export_park(park, out, start, end)
            print(f"[{park['slug']}] done in {time.time() - t0:.0f}s")
        except Exception:
            print(f"[{park['slug']}] FAILED:")
            traceback.print_exc()
