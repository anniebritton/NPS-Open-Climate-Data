# NPS Open Climate Data

Pre-processed climate time series, trend tests, and a public website
covering every one of the 63 US National Parks. Built on
**DAYMET v4**, **ERA5-Land**, and **USGS PAD-US v20** via Google Earth
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
  02_build_site_data.py  # Build analysis summaries
  03_generate_demo_data.py # Synthetic data for demoing the site
  04_write_carbon.py     # Dump carbon.json for the site
  05_generate_boundaries.py # Merge headline slopes; fallback to circles
  06_extract_padus_from_gdb.py # Real polygons from local PAD-US 4.1 GDB
  07_download_from_drive.py # Pull completed EE exports from Google Drive

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
# 1. (Optional) Generate synthetic demo data to preview without EE:
python scripts/03_generate_demo_data.py

# Or run the real Earth Engine batch (slow; ~hours for all 63 parks):
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

## Data coverage

| Coverage | Datasets used |
| --- | --- |
| CONUS, Hawaii, Puerto Rico | DAYMET v4 + ERA5-Land |
| Alaska, American Samoa, Virgin Islands | ERA5-Land only |

Parks with disjoint geometry (Saguaro, Channel Islands, Kings Canyon,
etc.) are split by `ee.Geometry.geometries()` so each polygon gets its
own time series, in addition to the union-level summary.

## Known issues / Open items

- **Re-run EE pipeline with current PAD-US.** Four parks (Gateway
  Arch, Indiana Dunes, New River Gorge, White Sands) were skipped in
  the first full EE batch because their boundary lookup failed — they
  were redesignated as national parks 2018-2020. The underlying cause
  is likely that `nps_climate_data/utils.py` currently queries
  `USGS/GAP/PAD-US/v20` (EE catalog), which pre-dates those
  redesignations. We now have **PAD-US 4.1** locally (site/public/data/
  boundaries/ has all 63 real polygons). Options to fix:
  a) Point `utils.get_park_boundary()` at a newer PAD-US EE asset if
     one exists;
  b) Upload PAD-US 4.1 proclamation layer as an EE asset (one-time);
  c) Simplest — have `core.py` accept geometry directly from the
     committed GeoJSON files rather than querying EE for it.
  Then re-run the full batch (or just the 4 missing slugs) via
  `pipeline.ipynb` A2-full.
- **3 tiny-island parks have no temperature signal.** American Samoa,
  Dry Tortugas, and Virgin Islands fall inside ERA5-Land pixels that
  are sea-masked because the land fraction is too low for the ~11 km
  native grid, and DAYMET doesn't cover the offshore islands. The
  parks render on the overview map but their per-park temperature
  charts are empty. Fix options: pull from ERA5-Single-Levels (which
  isn't land-masked), nearest-neighbour an adjacent coastal pixel, or
  switch to MERRA-2.
- **Raw CSV download links will 404.** The gzipped per-park CSVs total
  ~134 MB, too large to commit. Per-park pages link to
  `/data/raw/<slug>/<slug>.csv.gz` but those files aren't shipped.
  Fix: host the CSVs on a GitHub Release or a static bucket and update
  the link target.
- **`03_generate_demo_data.py` is deprecated.** The deployed site now
  uses real committed data; the synthetic-data path in the notebook
  has been removed. The script still works for anyone who wants a
  quick preview without EE, but it's not part of the main flow.
- **Full data QC pass.** Triple-check pipeline outputs against
  external sources — NOAA Climate at a Glance, NCEI USCRN, Gonzalez
  et al. (2018), NPS IRMA — for a sample of ~10 parks across climate
  zones. Verify unit conversions (Kelvin → °C, ERA5 evap sign), annual
  aggregation choices (sums vs means), and MK/Theil-Sen implementation.
  Deliverable: `docs/DATA_QC.md`. Investigate the tiny-island null issue
  alongside.
- **Research-paper citations on park pages.** Add a "Further reading"
  section to each per-park page listing peer-reviewed papers about
  climate change in that specific park (citations only, no PDFs).
  Start from Gonzalez 2018 as a project-wide baseline; hand-curate per
  park from Google Scholar + NPS IRMA. Store as
  `data/citations/<slug>.json` with BibTeX fields.
- **Service-account EE credentials.** Provision an EE-registered
  Google Cloud service account in the `ee-annieresearch` project so
  Claude (or any unattended script) can submit batch tasks without
  interactive auth. Stash the key at `~/.config/gcloud/ee-service-account.json`,
  make `utils.py` prefer `ee.ServiceAccountCredentials` when
  `GOOGLE_APPLICATION_CREDENTIALS` is set.
- **Interactive methodology page.** Rebuild `/methodology` from a
  plain-text wall into a step-by-step pipeline walk-through: clickable
  nodes for load → filter → reduceRegion → canonicalise → aggregate →
  MK/Theil-Sen, each with a tiny visual of the data shape at that
  stage. Keep a worked example (Acadia) at the bottom as a
  scrollytelling sequence.

## Authors

- **Annie Britton** — project lead, analysis design, site
- **Ian Pritchard** — contributor

## Citing

> Britton, A., & Pritchard, I. (2026). *NPS Open Climate Data:
> Pre-processed climate trends for all US National Parks.* Derived from
> DAYMET v4 and ERA5-Land via Google Earth Engine, with boundaries from
> USGS PAD-US v20. MIT license.

## License

MIT. See `LICENSE`.
