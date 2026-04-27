# NPS Open Climate Data

Pre-processed climate time series, trend tests, and a public website
covering every one of the 63 US National Parks. Built on
**DAYMET v4**, **ERA5-Land**, and **USGS PAD-US 4.1** via Google Earth
Engine.

- 🌐 **Site:** <https://anniebritton.github.io/NPS-Open-Climate-Data/>
- 📦 **Python package:** `nps_climate_data`
- 📊 **Open data:** daily, annual, seasonal series + Mann-Kendall /
  Theil-Sen trend tables, per park
- ♻️ **Carbon transparent:** every build's footprint published on-site

## What's in this repo

```
nps_climate_data/        # Python package
  parks.py               # Registry of all 63 National Parks
  datasets.py            # DAYMET / ERA5 band configs (verified vs EE catalog)
  utils.py               # PAD-US boundary lookup + multipart-unit splitting
  core.py                # EE reduceRegion pipeline
  batch.py               # 5-year-chunked batch exporter for all parks
  analysis.py            # Unit canonicalisation, aggregates, MK + Theil-Sen
  summarize.py           # Builds site JSON from raw data
  carbon.py              # Footprint estimator (EE + local + Claude + hosting)

scripts/
  01_export_all_parks.py # Submit EE batch export tasks (needs credentials)
  02_build_site_data.py  # Build analysis summaries (incl. monthly decomp)
  04_write_carbon.py     # Dump carbon.json for the site
  05_generate_boundaries.py # Merge headline slopes; fallback to circles
  06_extract_padus_from_gdb.py # Real polygons from local PAD-US 4.1 GDB
  07_download_from_drive.py # Pull completed EE exports from Google Drive
  qc_pass.py             # Audit pipeline outputs → docs/DATA_QC.md

docs/
  DATA_QC.md             # Auto-generated audit of pipeline outputs

pipeline.ipynb           # End-to-end notebook (recommended entry point)
site/                    # Astro static site, deployed to GitHub Pages
tests/                   # pytest suite (no network / no EE required)
.github/workflows/       # CI + GH Pages deploy
```

## Python package usage

```bash
pip install -e .
earthengine authenticate   # one-time

python -c "import ee; ee.Initialize(); \
  import nps_climate_data as nps; \
  df = nps.get_data('Yellowstone National Park', '2020-01-01', '2025-01-01'); \
  print(df.head())"
```

All dates are Earth-Engine-style: `filterDate(start, end)` treats `end`
as **exclusive**, matching EE semantics. The package accepts and passes
through ISO date strings unmodified.

## Building the site end-to-end

```bash
# 1. Run the Earth Engine batch (slow; ~hours for all 63 parks):
earthengine authenticate
python scripts/01_export_all_parks.py --start 1980-01-01

# 2. Aggregate, run trend tests, write site JSON:
python scripts/02_build_site_data.py
python scripts/04_write_carbon.py

# 3. Copy data into the site's public/ dir:
mkdir -p site/public/data && cp -r data/site/* site/public/data/
mkdir -p site/public/data/raw
for d in data/raw/*/; do
  slug=$(basename "$d"); mkdir -p site/public/data/raw/$slug
  cp "$d"*.csv site/public/data/raw/$slug/
  gzip -f site/public/data/raw/$slug/*.csv
done

# 4. Build and preview locally:
cd site && npm install && npm run dev
```

GitHub Actions (`.github/workflows/deploy.yml`) rebuilds and publishes
the site on every push to `main`.

## Tests

```bash
pip install numpy pandas pytest pyarrow
PYTHONPATH=. pytest tests/ --ignore=tests/test_basic.py
```

The suite covers:

- DAYMET/ERA5 unit conversions (Kelvin, meters, ECMWF sign convention)
- Canonical-variable schema matches the declared EE bands
- 5-year chunking respects `filterDate`'s exclusive end
- Mann-Kendall detects trends and rejects flat series
- Theil-Sen matches the slope of an exact line
- Carbon estimator scales with inputs
- An EE stub-integration test confirms `merge()` is called per extra
  dataset and `filterDate(..., end)` is passed an exclusive end

For end-to-end output validation (range checks, aggregation arithmetic
recompute, MK/Theil-Sen consistency, external warming benchmarks for
20 parks across climate zones), run:

```bash
PYTHONPATH=. python scripts/qc_pass.py
```

It rewrites [`docs/DATA_QC.md`](docs/DATA_QC.md) with the latest audit.

## Downloading the data

The full versioned dataset lives on **Zenodo**:
[`10.5281/zenodo.19823584`](https://doi.org/10.5281/zenodo.19823584)
(MIT-licensed). Four archives are available so you can pick the
subset you need:

- `nps-open-climate-data-v1.0.0-all.zip` (178 MB) — everything below
- `nps-open-climate-data-v1.0.0-daily.zip` (150 MB) — raw daily CSVs
  (gzipped) per park, in DAYMET / ERA5 native units
- `nps-open-climate-data-v1.0.0-summary.zip` (24 MB) — per-park
  summary JSONs (annual + seasonal + decomposition + trends), plus
  `parks.json` index
- `nps-open-climate-data-v1.0.0-boundaries.zip` (3 MB) — PAD-US 4.1
  polygons in WGS84

### Programmatic access (Python)

```python
import nps_climate_data as nps

df  = nps.fetch_daily("yellowstone")     # raw daily DataFrame
sj  = nps.fetch_summary("yellowstone")   # summary JSON dict
geo = nps.fetch_boundary("yellowstone")  # parsed GeoJSON
arc = nps.fetch_archive("boundaries")    # path to extracted dir
```

Archives are downloaded once and cached under
`~/.cache/nps_climate_data/` (override with `NPS_CLIMATE_DATA_CACHE`).
Pass `force=True` to refresh.

### Per-format usage hints

```bash
# Unzip any archive — extracts to nps-open-climate-data-v1.0.0/
unzip nps-open-climate-data-v1.0.0-summary.zip

# Daily CSVs are gzipped; pandas auto-detects, or decompress manually:
gunzip daily/yellowstone/yellowstone.csv.gz
python -c "import pandas as pd; print(pd.read_csv('daily/yellowstone/yellowstone.csv.gz').head())"

# Summary JSONs are plain JSON; load with any parser
python -c "import json; print(json.load(open('summary/yellowstone.json'))['headline_trends'])"

# GeoJSON boundaries open in geopandas, QGIS, Mapbox, Leaflet, etc.
python -c "import geopandas as gpd; print(gpd.read_file('boundaries/yellowstone.geojson'))"
```

## Data coverage

All 63 designated National Parks have raw daily series, annual /
seasonal aggregates, Mann–Kendall + Theil–Sen trend tests, monthly
trend / seasonal-cycle decomposition, and per-park JSON summaries
committed under `site/public/data/parks/`. Three small island parks
(American Samoa, Dry Tortugas, Virgin Islands) fall outside the
gridded land-only datasets and render with an "outside land-grid
coverage" badge instead of charts.

| Coverage | Datasets used |
| --- | --- |
| CONUS, Hawaii, Puerto Rico | DAYMET v4 + ERA5-Land |
| Alaska, American Samoa, Virgin Islands | ERA5-Land only |

Parks with disjoint geometry (Saguaro, Channel Islands, Kings Canyon,
etc.) are split by `ee.Geometry.geometries()` so each polygon gets its
own time series, in addition to the union-level summary.

## Open items

- **Raw CSV download links will 404.** The gzipped per-park CSVs total
  ~134 MB, too large to commit. Per-park pages link to
  `/data/raw/<slug>/<slug>.csv.gz` but those files aren't shipped.
  Fix: host the CSVs on a GitHub Release or a static bucket and update
  the link target.
- **Tiny-island temperature signal.** American Samoa, Dry Tortugas,
  and Virgin Islands fall inside ERA5-Land pixels that are sea-masked
  because the land fraction is too low for the ~11 km native grid,
  and DAYMET doesn't cover the offshore islands. The site labels them
  honestly ("outside land-grid coverage") but a real fix would pull
  from ERA5-Single-Levels (which isn't land-masked),
  nearest-neighbour an adjacent coastal pixel, or switch to MERRA-2.

## Reporting issues

Bug reports, data questions, and feature requests all go on GitHub:
**<https://github.com/anniebritton/NPS-Open-Climate-Data/issues>**

Before opening a new issue, please
[search existing issues](https://github.com/anniebritton/NPS-Open-Climate-Data/issues?q=is%3Aissue)
to avoid duplicates. When you [file a new one](https://github.com/anniebritton/NPS-Open-Climate-Data/issues/new),
the more of the following you can include, the faster it gets resolved:

- **Site bug** — the page URL, your browser + OS, and a screenshot or
  the browser console output.
- **Data / trend question** — the park slug and variable (e.g.
  `yellowstone`, `tmean_c`), plus a link to the per-park page.
- **Pipeline / reproducibility** — the exact command that failed, your
  Python version, and which step of `pipeline.ipynb` you were on.

Pull requests are welcome. For non-trivial changes, open an issue
first so we can agree on scope before you invest the time.

## Authors

- **Annie Britton** — project lead, analysis design, site. Applied
  scientist working across climate science, remote sensing, and AI.
  Senior Manager, AI Solutions at Quantum Rise; previously Lead
  Scientist at Earth Finance and Climate Engine, with research at
  Johns Hopkins and NASA DEVELOP.
  [GitHub](https://github.com/anniebritton) ·
  [LinkedIn](https://www.linkedin.com/in/annebritton/)
- **Ian Pritchard** — contributor. Data-systems engineer with a
  planetary-science background (MSc, Western — automated lunar crater
  detection). Principal Data System Developer at VRIFY; previously
  Head of Data Engineering at Earth Finance and VP, Data Engineering
  at Climate Engine.
  [GitHub](https://github.com/ipritchard) ·
  [LinkedIn](https://www.linkedin.com/in/give-me-data/)

## Citing

> Britton, A., & Pritchard, I. (2026). *NPS Open Climate Data v1.0.0:
> Pre-processed climate trends for all 63 US National Parks* [Data set].
> Zenodo. https://doi.org/10.5281/zenodo.19823584

Per-park citation strings (Plain / BibTeX / APA) are also available on
each park page and on the [For Researchers](https://anniebritton.github.io/NPS-Open-Climate-Data/researchers/)
page.

## License

MIT. See `LICENSE`.
