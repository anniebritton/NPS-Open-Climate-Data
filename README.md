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

All 63 designated National Parks have raw daily series, annual /
seasonal aggregates, Mann–Kendall + Theil–Sen trend tests, and per-park
JSON summaries committed under `site/public/data/parks/`. Three small
island parks (American Samoa, Dry Tortugas, Virgin Islands) fall
outside the gridded land-only datasets and render with an "outside
land-grid coverage" badge instead of charts.

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
- **Full data QC pass.** Triple-check pipeline outputs against
  external sources — NOAA Climate at a Glance, NCEI USCRN, Gonzalez
  et al. (2018), NPS IRMA — for a sample of ~10 parks across climate
  zones. Verify unit conversions (Kelvin → °C, ERA5 evap sign),
  annual aggregation choices (sums vs means), and MK/Theil–Sen
  implementation. Deliverable: `docs/DATA_QC.md`.
- **Time-series decomposition.** Current per-park analysis stops at
  annual / seasonal aggregates + Mann–Kendall / Theil–Sen. Add an STL
  (or equivalent) decomposition of the daily series into trend,
  seasonal, and residual components so users can see the annual cycle
  separately from the long-run trend.
- **Methodology: data-shape visuals + worked example.** Pipeline-
  diagram nodes are now clickable section anchors. Still open:
  expand each step inline with a tiny visual of the data shape at
  that stage (daily raw → reduced mean → annual aggregate → trend
  line), and append an Acadia worked-example scrollytelling sequence
  at the bottom that walks through every step with real numbers.
- **Research-paper citations on park pages.** Add a "Further reading"
  section to each per-park page listing peer-reviewed papers about
  climate change in that specific park (citations only, no PDFs).
  Start from Gonzalez 2018; hand-curate the rest from Google Scholar
  + NPS IRMA. Store as `data/citations/<slug>.json` with BibTeX
  fields.
- **Hero ridges read faint.** The decorative ridge lines in the
  top-right of the landing page should be a touch thicker or more
  saturated so they register as an intentional design element rather
  than background noise.
- **Map zoom needs Ctrl+scroll polish.** The per-park map prompts for
  Ctrl+scroll, but the gesture sometimes feels unresponsive. Verify
  the wheel handler fires consistently across browsers, or expose
  visible +/− controls.
- **Label the park-card sparklines.** The mini trend line on each
  park tile isn't labelled. Needs a compact axis hint or legend if it
  fits without crowding the card.
- **`03_generate_demo_data.py` is deprecated.** The deployed site
  uses real committed data; the synthetic-data path remains for quick
  EE-free previews but is not part of the main flow.

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
  Python version, and whether you were running the Earth Engine batch
  or the `03_generate_demo_data.py` demo path.

Pull requests are welcome. For non-trivial changes, open an issue
first so we can agree on scope before you invest the time.

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
