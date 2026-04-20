"""
Fetch real park boundaries from the USGS PAD-US ArcGIS REST web services.

Runs in CI where network egress is open. For each of the 63 parks, hits
the PAD-US proclamation FeatureServer and writes a GeoJSON FeatureCollection
to ``site/public/data/boundaries/<slug>.geojson``. The circle-generator
(``05_generate_boundaries.py``) runs after this and only fills in gaps —
parks for which no real polygon was retrieved.

Env overrides:

    PADUS_SERVICE_URL   FeatureServer/MapServer base URL (default: PAD-US 4,
                        GAP Analysis Project REST service).
    PADUS_NAME_FIELD    Name field to match on (default: Unit_Nm).
    PADUS_MANAGER_FIELD Manager field for NPS filter (default: Mang_Name).

See: https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-web-services
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from nps_climate_data.parks import get_parks
from nps_climate_data.utils import PADUS_UNIT_ALIASES

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "site" / "public" / "data" / "boundaries"

DEFAULT_SERVICE = os.environ.get(
    "PADUS_SERVICE_URL",
    "https://gis1.usgs.gov/arcgis/rest/services/padus4/Proclamation_and_Other_Planning_Boundaries/FeatureServer/0",
)
NAME_FIELD = os.environ.get("PADUS_NAME_FIELD", "Unit_Nm")
MGR_FIELD = os.environ.get("PADUS_MANAGER_FIELD", "Mang_Name")
USER_AGENT = "NPS-Open-Climate-Data/1.0 (+https://github.com/anniebritton/NPS-Open-Climate-Data)"
TIMEOUT = 30


def _aliases_for(unit_name: str) -> list[str]:
    return PADUS_UNIT_ALIASES.get(unit_name, [unit_name])


def _where_clause(unit_name: str) -> str:
    names = _aliases_for(unit_name)
    quoted = ",".join("'" + n.replace("'", "''") + "'" for n in names)
    # Belt-and-braces NPS filter; some features may lack Mang_Name so we
    # OR to keep them eligible.
    return f"({NAME_FIELD} IN ({quoted})) AND ({MGR_FIELD} = 'NPS' OR {MGR_FIELD} IS NULL)"


def _query(service: str, unit_name: str) -> dict | None:
    params = {
        "where": _where_clause(unit_name),
        "outFields": NAME_FIELD,
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "geojson",
        # Server-side simplification keeps files small.
        "geometryPrecision": "4",
        "maxAllowableOffset": "0.002",
    }
    url = f"{service}/query?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read()
    except Exception as e:
        print(f"  ! {unit_name}: request failed ({e})", file=sys.stderr)
        return None
    try:
        obj = json.loads(body)
    except ValueError as e:
        print(f"  ! {unit_name}: non-JSON response ({e})", file=sys.stderr)
        return None
    if obj.get("error"):
        print(f"  ! {unit_name}: service error {obj['error']}", file=sys.stderr)
        return None
    feats = obj.get("features") or []
    if not feats:
        return None
    return obj


def _attach_slug_props(geo: dict, slug: str, unit_name: str, state: str) -> dict:
    for f in geo.get("features", []):
        props = f.setdefault("properties", {})
        props["slug"] = slug
        props["unit_name"] = unit_name
        props["state"] = state
        props["approximate"] = False
    return geo


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    service = DEFAULT_SERVICE
    print(f"Querying PAD-US: {service}")
    ok, miss = [], []
    for park in get_parks():
        slug = park["slug"]
        unit_name = park["unit_name"]
        geo = _query(service, unit_name)
        if geo is None:
            miss.append(slug)
            continue
        _attach_slug_props(geo, slug, unit_name, park["state"])
        (OUT_DIR / f"{slug}.geojson").write_text(json.dumps(geo))
        ok.append(slug)
        time.sleep(0.15)  # modest rate-limit courtesy

    print(f"\nPAD-US fetch: {len(ok)}/{len(get_parks())} parks resolved.")
    if miss:
        print(f"Missing (will fall back to circles): {', '.join(miss)}")
    # Don't fail CI — 05_generate_boundaries.py fills any gaps.
    return 0


if __name__ == "__main__":
    sys.exit(main())
