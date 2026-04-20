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
  01_export_all_parks.py # Run the EE batch export (needs credentials)
  02_build_site_data.py  # Build analysis summaries
  03_generate_demo_data.py # Synthetic data for demoing the site
  04_write_carbon.py     # Dump carbon.json for the site

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

## License

MIT. See `LICENSE`.
