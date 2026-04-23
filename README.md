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

- **Run EE pipeline for the 4 redesignated parks.** Gateway Arch,
  Indiana Dunes, New River Gorge, and White Sands were skipped in the
  first full EE batch because EE's `USGS/GAP/PAD-US/v20` catalog
  pre-dates their 2018-2020 redesignations, so `get_park_boundary()`
  returned 0 features. Code fix has landed: `get_local_park_boundary`
  in `nps_climate_data/utils.py` reads the committed PAD-US 4.1
  GeoJSONs under `site/public/data/boundaries/`, and
  `batch.submit_park_tasks` falls back to it when the EE lookup misses.
  `pipeline.ipynb` also has a new **A2-missing** cell that targets just
  those four slugs. TODO: actually run the pipeline end-to-end
  (A1 → A2-missing → A3 → A4 → step 3 → step 4) so
  `data/raw/{gateway-arch,indiana-dunes,new-river-gorge,white-sands}/`
  and the corresponding site JSON under `site/public/data/parks/` are
  produced. Expect ~15-30 min of EE quota for the four tasks.
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
- **Time-series decomposition.** Current per-park analysis stops at
  annual/seasonal aggregates + Mann-Kendall / Theil-Sen. Add an STL (or
  equivalent) decomposition of the daily series into trend, seasonal,
  and residual components so users can see the annual cycle separately
  from the long-run trend. Decide where it surfaces on the park page
  (new chart block vs. optional toggle on the existing series).
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
- **Methodology page — interactive depth.** The page is no longer a
  wall of text: it has a pipeline diagram, sticky TOC, and numbered
  step cards. Still open: make the pipeline-diagram nodes clickable,
  with each expanding into a tiny visual of the data shape at that
  stage (daily raw → reduced mean → annual aggregate → trend line),
  and append an Acadia worked-example scrollytelling sequence at the
  bottom that walks through every step with real numbers.
- **Prettify variable names in the UI.** Raw canonical names with
  underscores (`tmean_c`, `prcp_mm`, `swe_mm`) leak into chart
  headers, dropdowns, and URLs. Map to display labels (e.g. "Mean
  temperature (°C)", "Precipitation (mm)") at the render layer while
  keeping the underscored slugs as stable data keys.
- **Disable click-through for parks with no data.** The 3 tiny-island
  parks (American Samoa, Dry Tortugas, Virgin Islands) render as
  markers on the overview map but their per-park pages 404 or show
  empty charts. Detect missing data at map-render time and either
  disable the marker link or route it to a "no data yet" stub that
  explains why.
- **Shorten time-series chart height.** Per-park charts are currently
  too tall — they push the trend summary below the fold. Tighten the
  chart aspect ratio so the headline slope is visible without
  scrolling.
- **Per-park chart polish.** (a) The chart titles ("Annual Mean
  Temperature", "Annual Precipitation") are too small to read at a
  glance — bump size and weight so the subject is immediately
  obvious. (b) The year-marker dots on the line charts are too small
  — enlarge them so individual years are easier to hit / read.
- **Darken body text site-wide.** Several surfaces use a medium gray
  on cream that reads as low-contrast — user reported having to paste
  a snippet into a Google Doc and re-color it to confirm legibility.
  Push body text to near-black (Rise Charcoal #1E1E1E) or the deepest
  brand blue (Deep Sea) wherever a lighter gray is currently in use.
- **Bump type sizes on the landing page.** The "Open Climate Data"
  wordmark and the top nav ("Parks, Methodology, …") both read as
  small. So does the park-name legend box beneath the map — and at
  larger size the category colors (two reds sit very close) would
  also be easier to tell apart.
- **Strengthen the hero wavy-lines graphic.** The decorative lines in
  the top-right of the landing page read as faint. Make them thicker
  / brighter / more saturated so they register as an intentional
  design element rather than background noise.
- **Add a color legend to the per-park annual bars.** The red/blue
  bar strip (warmer-than-reference vs cooler-than-reference year) has
  no inline key — users are inferring the encoding from the line
  chart below. Add a compact legend directly under the bar strip.
- **Color the methodology step numbers.** The large "1"–"7" numerals
  on the methodology page are rendered in low-contrast gray and
  easily missed. Recolor to an accent (Lava or Deep Sea) so each step
  reads as a clear anchor.
- **Make the landing-page map a headline component.** Currently a
  neutral-outline overview. Two directions worth exploring:
  a) fill each park by warming rate (reuse the trend-slope palette
     already used on per-park pages) — safer, and ties the map to the
     core story of the site;
  b) a schematic / transit-diagram-style rendering so the many
     tiny-footprint parks are legible at overview scale.
  Lean (a) unless (b) tests surprisingly well.
- **Map zoom doesn't respond to Ctrl + scroll-wheel.** Either wire up
  the expected zoom gesture or expose visible +/− controls (plus
  pinch-zoom on touch) so the map is actually explorable.
- **Label the park-card sparklines.** The mini trend lines on each
  park card aren't labeled, so it's not obvious what variable they
  show. Needs a very compact label (axis hint, tiny caption, or
  legend) — tbd whether there's room without crowding the card.
- **"Significant warming only" toggle dominates the Browse section.**
  Undecided — user likes the prominence but flagged it as possibly
  too big. Revisit if additional filter controls are added; otherwise
  leave as-is.

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
