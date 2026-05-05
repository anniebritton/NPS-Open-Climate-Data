"""One-shot migration: bring legacy raw CSVs in line with the current schema.

Applies the same transforms the EE pipeline now applies server-side:

  * coalesces duplicate-date rows (legacy exports stored two rows per date,
    one per dataset, each with NaN for the other's bands)
  * converts ERA5 temperatures K → °C, water-flux bands m → mm, and
    sign-flips evaporation to positive mm/day

Operates in-place on every CSV under ``data/raw/<slug>/``. After running
once, the raw archive matches what fresh exports produce — no need to
re-run the multi-hour EE pipeline just for the unit / dedup change.

    PYTHONPATH=. python scripts/08_migrate_raw_units.py
    PYTHONPATH=. python scripts/08_migrate_raw_units.py --root data --dry-run
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from nps_climate_data.datasets import DATASETS


def _transform_map() -> dict[str, tuple[str, float]]:
    """Flatten dataset-prefixed band names → (op, value) for every transform."""
    out: dict[str, tuple[str, float]] = {}
    for ds in DATASETS:
        prefix = ds["name"] + "_"
        for band, t in (ds.get("transforms") or {}).items():
            out[prefix + band] = t
    return out


def _is_legacy_kelvin(df: pd.DataFrame) -> bool:
    """Heuristic: legacy ERA5 temperature_2m_max column has values > 100°C
    (i.e. still in Kelvin). New exports are already in °C and never exceed
    that range on Earth's surface."""
    for col in ("ERA5_temperature_2m_max", "ERA5_temperature_2m"):
        if col in df.columns and df[col].dropna().gt(100).any():
            return True
    return False


def migrate_csv(path: Path, transforms: dict[str, tuple[str, float]]) -> dict:
    df = pd.read_csv(path)
    n_before = len(df)
    legacy = _is_legacy_kelvin(df)

    if "date" in df.columns and df["date"].duplicated().any():
        df = df.groupby("date", as_index=False).max(numeric_only=True)
    n_after_dedup = len(df)

    converted_cols: list[str] = []
    if legacy:
        for col, (op, val) in transforms.items():
            if col not in df.columns:
                continue
            if op == "subtract":
                df[col] = df[col] - val
            elif op == "multiply":
                df[col] = df[col] * val
            converted_cols.append(col)

    df.to_csv(path, index=False)
    return {
        "rows_before": n_before,
        "rows_after": n_after_dedup,
        "converted_cols": converted_cols,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", default="data", help="data root containing raw/<slug>/")
    p.add_argument("--dry-run", action="store_true", help="report only, don't write")
    args = p.parse_args()

    raw_root = Path(args.root) / "raw"
    if not raw_root.exists():
        raise SystemExit(f"No raw data directory at {raw_root}")

    transforms = _transform_map()
    csvs = sorted(raw_root.glob("*/*.csv"))
    print(f"Found {len(csvs)} raw CSV file(s) under {raw_root}")

    total_dropped = 0
    n_migrated = 0
    n_already_clean = 0
    for csv in csvs:
        df = pd.read_csv(csv)
        legacy = _is_legacy_kelvin(df)
        dup = "date" in df.columns and df["date"].duplicated().any()
        if not legacy and not dup:
            n_already_clean += 1
            continue
        if args.dry_run:
            print(f"  would migrate: {csv.relative_to(raw_root.parent)} "
                  f"(legacy_units={legacy}, dup_dates={dup})")
            continue
        result = migrate_csv(csv, transforms)
        dropped = result["rows_before"] - result["rows_after"]
        total_dropped += dropped
        n_migrated += 1
        print(f"  ✓ {csv.relative_to(raw_root.parent)}: "
              f"rows {result['rows_before']} → {result['rows_after']} "
              f"(-{dropped}), converted {len(result['converted_cols'])} ERA5 col(s)")

    if args.dry_run:
        print("\nDry run complete — no files written.")
    else:
        print(f"\nMigrated {n_migrated} file(s); "
              f"{n_already_clean} already clean. "
              f"Coalesced {total_dropped} duplicate row(s) total.")


if __name__ == "__main__":
    main()
