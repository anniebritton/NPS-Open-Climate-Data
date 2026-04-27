# AGENTS.md

Repository-level instructions for any code-agent (Codex, Cursor,
Claude Code, etc.) operating on this codebase. Mirrors
[CLAUDE.md](CLAUDE.md) — read either, the content is interchangeable.

## Project at a glance

NPS Open Climate Data: pre-processed climate time series, trend tests,
monthly trend/seasonal decomposition, and a public Astro site covering
every one of the 63 US National Parks. Datasets: DAYMET v4, ERA5-Land,
USGS PAD-US 4.1. Pipeline runs through Google Earth Engine batch
tasks. CI rebuilds the site on every push to `main`.

For the user-facing description see [README.md](README.md). For
statistical methodology see the deployed `/methodology/` page or
`nps_climate_data/analysis.py`.

## Layout

```
nps_climate_data/  Python package (analysis + EE export + carbon)
scripts/           Numbered one-shot operational scripts
docs/              Design + QC docs (DATA_QC.md is auto-generated)
site/              Astro static site, deployed to GitHub Pages
tests/             pytest suite (no network / no EE required)
pipeline.ipynb     Notebook entry point (recommended)
```

`nps_climate_data/__init__.py` keeps EE imports lazy so analysis +
carbon helpers work without `earthengine-api` credentials.

## Conventions

- Conventional-ish commit prefixes: `feat(scope):`, `fix(scope):`,
  `style(site):`, `docs(scope):`, `chore:`. Add a *Co-Authored-By*
  trailer for agent-authored commits.
- Pipeline data stays in SI (Celsius, millimetres, Pascals); °C → °F
  conversion happens in the site render layer only.
- Per-park JSON shape (`headline_trends`, `trends`, `annual`,
  `stripes`, `decomposition[var]`, …) is load-bearing — Astro pages
  read these fields directly. Don't rename without updating consumers.
- The QC pass at `scripts/qc_pass.py` is calibrated against documented
  ERA5-Land / DAYMET quirks; widen its bands only after consulting the
  "Documented dataset characteristics" block in `docs/DATA_QC.md`.

## Running things

```bash
# Python tests (no network, no EE)
PYTHONPATH=. pytest tests/ --ignore=tests/test_basic.py

# Local site preview
cd site && npm install && npm run dev

# Static build (what CI runs)
cd site && npm run build

# Refresh docs/DATA_QC.md
PYTHONPATH=. python scripts/qc_pass.py
```

Pipeline scripts (`scripts/01_…` → `02_…` → `04_…`) need
`pandas`, `numpy`, `pyarrow`, and Earth Engine credentials. The
notebook (`pipeline.ipynb`) is the recommended end-to-end entry point.

## Don't commit

- `data/raw/` — gitignored; raw daily CSVs total ~134 MB.
- `data/site/` — gitignored; staging output of `02_build_site_data.py`.
  `site/public/data/parks/<slug>.json` *is* committed (the deployed
  site reads from it) — keep both in sync when regenerating.
- `site/public/data/carbon.json` — gitignored; regenerated in CI from
  the live commit count.
- Any new heavyweight dependencies for the analysis package. pandas +
  numpy is the deal; everything else should be optional.

## Pointers

- High-level: [README.md](README.md)
- Methodology: `/methodology/` + `nps_climate_data/analysis.py`
- Output audit: [docs/DATA_QC.md](docs/DATA_QC.md)
- Carbon: `/carbon/` + `nps_climate_data/carbon.py`
