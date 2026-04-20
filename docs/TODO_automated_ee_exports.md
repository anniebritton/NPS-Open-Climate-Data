# TODO: Automate EE exports via GitHub Actions (Option B)

Switch from one-off local exports (Option A) to a scheduled GitHub
Actions workflow that re-runs the Earth Engine pipeline on its own —
no local EE install needed, data stays fresh, site auto-redeploys.

## Pending from Option A

- [ ] **Clone the repo locally** and run the first real EE export:
      ```bash
      git clone https://github.com/anniebritton/NPS-Open-Climate-Data
      cd NPS-Open-Climate-Data
      pip install earthengine-api pandas numpy pyarrow
      pip install -e .
      earthengine authenticate
      # Smoke-test one park first:
      PYTHONPATH=. python scripts/01_export_all_parks.py \
          --start 2020-01-01 --end 2025-01-01 --slugs yellowstone
      # Then the full batch:
      PYTHONPATH=. python scripts/01_export_all_parks.py --start 1980-01-01
      PYTHONPATH=. python scripts/02_build_site_data.py
      ```
      Then commit `data/raw/` to a `data` branch (or attach Parquet to a
      GitHub Release) and point the deploy workflow at it.

## Prerequisites on your side

- [ ] **Create a Google Cloud project** (or reuse an existing one with
      Earth Engine access). Note the project ID.
- [ ] **Create a service account** in that project:
      `IAM & Admin → Service Accounts → + Create service account`.
      Name: e.g. `nps-climate-exporter`. Role: none needed at the GCP
      level; EE permissions are granted separately.
- [ ] **Register the service account with Earth Engine** at
      <https://signup.earthengine.google.com/#!/service_accounts>.
      Paste the service-account email (`...@<project>.iam.gserviceaccount.com`).
- [ ] **Create a JSON key** for the service account:
      `Service account → Keys → Add Key → JSON`. Download the file.
      ⚠️ Treat this file like a password — don't commit it, don't paste
      it anywhere public.
- [ ] **Add the key as a GitHub secret**:
      `Repo Settings → Secrets and variables → Actions → New repository secret`
      - Name: `EE_SERVICE_ACCOUNT_KEY`
      - Value: the entire contents of the JSON key file
- [ ] **Add a second secret for the service-account email** (optional
      but clearer):
      - Name: `EE_SERVICE_ACCOUNT_EMAIL`
      - Value: the `client_email` from the JSON key

## Prerequisites on the code side

- [ ] **Teach `core.py` to accept service-account credentials.** Currently
      the scripts call `ee.Initialize()`; add an optional path that uses
      `ee.ServiceAccountCredentials(email, key_file)` so the same script
      works both locally and in CI. A 10-line change in `scripts/01_export_all_parks.py`.
- [ ] **Write `.github/workflows/export.yml`.** It should:
      - Trigger on `workflow_dispatch` (manual) + monthly `schedule` (cron).
      - Install Python deps + `earthengine-api`.
      - Write `$EE_SERVICE_ACCOUNT_KEY` to a tempfile.
      - Run `scripts/01_export_all_parks.py` (full 1980-present, incremental
        — see next item).
      - Run `scripts/02_build_site_data.py` and `04_write_carbon.py`.
      - Commit the updated JSON summaries + gzipped daily CSVs to a
        dedicated `data` branch (keeps `main` clean).
      - Push, which triggers the existing `deploy.yml` via a
        `workflow_run` chain.
- [ ] **Make the export incremental.** A nightly full 1980-present batch
      is wasteful; add `--update` mode that only fetches the trailing
      window (e.g. last 400 days) and merges with the existing Parquet.
      Saves ~95% of EE compute on steady-state runs.
- [ ] **Budget guard.** Add a timeout per park (e.g. 20 min) and skip-on-fail
      so a single flaky park doesn't block the whole run.
- [ ] **Update `deploy.yml`** to pull data from the `data` branch
      instead of regenerating synthetic data.

## Risk / cost notes

- Earth Engine is free for research/non-commercial use, but service-account
  usage has quota. Monitor at
  <https://code.earthengine.google.com/tasks>.
- Service-account JSON keys never expire until rotated. Plan to rotate
  annually; revoke immediately if the secret leaks.
- GitHub Actions has 2000 free minutes/month on public repos → fine for
  a monthly full run + a daily incremental. A full 63-park 1980-present
  run in CI should be scheduled at most monthly.

## Nice-to-haves (after B is working)

- [ ] Push a per-park manifest with input checksums so we can tell which
      park series actually changed between runs.
- [ ] Publish Parquet files as GitHub Release assets (can exceed 100 MB,
      unlike repo files).
- [ ] Slack/email notification on export failures.
