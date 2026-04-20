"""Dump the carbon-footprint estimate to a JSON the site can import.

Pulls git metadata so the estimate actually moves between merges: Claude
token usage scales with commit count (rough proxy for dev session work),
and a ``build_info`` block records the commit, timestamp, and which
source any boundary data came from (PAD-US vs circle fallback)."""

import datetime as dt
import json
import subprocess
from pathlib import Path

from nps_climate_data.carbon import estimate

REPO = Path(__file__).resolve().parents[1]

# Per-commit Claude-session token budget, averaged across the project.
# Real sessions vary wildly; this is an honest order-of-magnitude scale.
CLAUDE_IN_PER_COMMIT = 50_000
CLAUDE_OUT_PER_COMMIT = 10_000
CLAUDE_IN_BASELINE = 300_000   # initial build work prior to first commit
CLAUDE_OUT_BASELINE = 60_000


def _git(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=REPO, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return ""


def _boundary_sources() -> dict:
    """Count how many per-park boundaries are real vs circle approximations."""
    real = approx = 0
    bdir = REPO / "site" / "public" / "data" / "boundaries"
    for path in bdir.glob("*.geojson"):
        if path.name == "all_parks.geojson":
            continue
        try:
            obj = json.loads(path.read_text())
            feats = obj.get("features") or []
            if feats and any((f.get("properties") or {}).get("approximate") for f in feats):
                approx += 1
            elif feats:
                real += 1
        except Exception:
            continue
    return {"real_padus_polygons": real, "circle_approximations": approx}


def main():
    commits = _git("rev-list", "--count", "HEAD") or "0"
    try:
        n_commits = int(commits)
    except ValueError:
        n_commits = 0

    claude_in = CLAUDE_IN_BASELINE + n_commits * CLAUDE_IN_PER_COMMIT
    claude_out = CLAUDE_OUT_BASELINE + n_commits * CLAUDE_OUT_PER_COMMIT

    b = estimate(claude_input_tokens=claude_in, claude_output_tokens=claude_out)
    payload = b.to_dict()
    payload["build_info"] = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "commit": _git("rev-parse", "--short", "HEAD") or "unknown",
        "commit_count": n_commits,
        "claude_input_tokens": claude_in,
        "claude_output_tokens": claude_out,
        "boundary_sources": _boundary_sources(),
    }

    out = REPO / "site" / "public" / "data" / "carbon.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    print(
        f"Wrote {out}: {n_commits} commits, "
        f"{payload['total_build_g']:.1f} gCO2e total build."
    )


if __name__ == "__main__":
    main()
