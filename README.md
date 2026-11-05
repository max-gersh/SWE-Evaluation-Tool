# SWE Evaluation Tool (SWEET)

**[➜ Open the live SWEET Explorer](https://max-gersh.github.io/SWE-Evaluation-Tool/)**

SWEET produces near-real-time ensemble estimates of snow water equivalent (SWE) volume for New Mexico watersheds by combining three gridded SWE products. It was developed by the New Mexico Office of the State Engineer (OSE), Hydrology Bureau. The repository contains:

- **Statewide daily ensemble and the SWEET Explorer.** An interactive map and chart page covering every HUC8 that intersects New Mexico, plus the upstream Rio Grande and San Juan headwaters in Colorado.
- **Weekly Rio Grande report.** Figures and tables for the northern Rio Grande Basin in Colorado and New Mexico; the original SWEET product.

---

## SWE products

| Product | Source | Access |
|---|---|---|
| SNODAS | NOAA NOHRSC, distributed by NSIDC ([G02158](https://noaadata.apps.nsidc.org/NOAA/G02158/)) | Automatic download |
| SWANN (UA SWE) | University of Arizona ([UA_SWE](https://climate.arizona.edu/data/UA_SWE/)) | Automatic download |
| CU SWE | University of Colorado | Manual download (OneDrive), saved as `data/CU_SWE/YYYYMMDD_raster.tif` |

## Method

- **Common grid:** all products are resampled to a common 500 m grid (EPSG:5070).
- **Agreement mask:** a pixel is counted only where at least 2 products show SWE ≥ 0.1 in. Zeros from the remaining product are kept in the ensemble mean.
- **Reported values:** SWE **volume in acre-feet** per basin, as the ensemble mean with the product median, minimum and maximum, plus each product's own volume.
- **Two-product days:** on days without a CU SWE raster, the ensemble uses SNODAS and SWANN only, and both must agree. The page marks these days "· 2 products".
- **Elevation bands:** ensemble volume by 1,000-ft band for every basin, from a USGS 3DEP DEM. Band volumes sum exactly to the basin total.
- **History:** each product is compared only with its own record, which runs WY2004–present (SNODAS begins in WY2004). The record is sampled every 3rd day of the water year and summarized as a day-of-water-year median and interquartile range.

## Reporting domain

| Level | Count | Notes |
|---|---|---|
| HUC8 | 81 | Every HUC8 intersecting NM, plus the upstream Rio Grande and San Juan headwaters, reported whatever its snow amount |
| HUC6 | 19 | Sum of the included HUC8s. The 10 HUC6s that extend beyond the domain are marked * on the page |
| HUC12 | 8 | Selected headwater HUC12s (Rio Chama, Santa Fe, Navajo/Blanco), reported on their own and never added into HUC8/HUC6 totals |

Partial-HUC6 coverage is listed in `data/domain/huc6_lookup.csv`, and the HUC12 IDs in `data/domain/huc12_lookup.csv`.

## SWEET Explorer

The Explorer is a single self-contained HTML page with HUC6, HUC8 and HUC12 tabs. It shows:

- **Map:** SWE volume, change since the previous week, or % of median for each product, on any date.
- **SWE chart:** the ensemble for the current water year, with the product range.
- **Elevation-band chart:** ensemble volume by 1,000-ft band, with the product min–max and the change since the previous report.
- **Compare with history:** for each product, its median and interquartile range, the current year, and up to 5 selectable past water years ("Highest peak" and "Lowest peak" shortcuts).
- **Panel buttons:** full screen, PNG and CSV downloads.

Two versions are built:

- `web/sweet_explorer.html` loads Leaflet and Plotly from a CDN. This is the version hosted on GitHub Pages.
- `web/sweet_explorer_offline.html` has both libraries built in and works without internet access. It's [downloadable from the site](https://max-gersh.github.io/SWE-Evaluation-Tool/sweet_explorer_offline.html). Open it in Chrome, Edge or Firefox; it won't run in the Outlook preview pane.

---

## Setup

SWEET is written in Python and runs on Windows. Run the commands below in Anaconda Prompt or a VS Code terminal.

1. **Clone the repository**
   ```
   cd directory_name
   git clone https://github.com/max-gersh/SWE-Evaluation-Tool.git nm_swe
   cd nm_swe
   ```
2. **Add conda-forge to your channels**
   ```
   conda config --add channels conda-forge
   ```
3. **Create the environment** (about 3 GB)
   ```
   conda env create -f setup/environment.yml
   ```
   To install it to a specific location, add `--prefix /full/path/to/env/nm_swe`.
4. **Activate and verify**
   ```
   conda activate nm_swe
   conda env list
   ```
5. **Optional: VS Code interpreter**
   Ctrl + Shift + P → *Python: Select Interpreter* → `nm_swe`.
6. **Git**, needed for publishing the page. If Git isn't installed system-wide:
   ```
   conda install -c conda-forge git
   ```

### Data not included in the repository

Raw rasters and DEMs are excluded by `.gitignore` because of their size. The code downloads or rebuilds most of them; the exceptions are noted in the table.

| Item | How to get it |
|---|---|
| SNODAS, SWANN rasters | Downloaded automatically, and deleted after processing |
| CU SWE rasters | Manual download to `data/CU_SWE/YYYYMMDD_raster.tif` |
| Statewide DEM (`data/dem_3dep_ft.tif`) | `python scripts/fetch_3dep_dem.py` |
| Mancos HUC8 and selected HUC12 boundaries | `python scripts/fetch_wbd_additions.py` |
| Statewide WBD extract (`data/Shapefiles/WBD_NM/`) | USGS Watershed Boundary Dataset |

---

## First-time statewide setup

```
python scripts/fetch_wbd_additions.py           # Mancos HUC8 + selected HUC12s from USGS WBD
python -m src.domain                            # expect: 81 HUC8s, 19 HUC6s (10 partial), 8 HUC12s
python scripts/fetch_3dep_dem.py                # statewide DEM for elevation bands
python tests/test_synthetic.py                  # optional sanity check on synthetic data
python scripts/check_sources.py                 # test the archives; estimate backfill size and time
python -m src.backfill --product SNODAS --every 3   # one-time WY2004–present history; resumable
python -m src.backfill --product UA_SWE --every 3
python -m src.climatology                       # per-product medians and percentiles
python -m src.daily_update --since 20261001     # fill the current season from Oct 1
```

The backfill downloads each day, computes basin statistics and deletes the raster, so only small tables are kept. See [`docs/HISTORICAL_DATA_GUIDE.md`](docs/HISTORICAL_DATA_GUIDE.md) for details, including how to add CU SWE history.

## Routine operation

### Daily (unattended)

```
python -m src.daily_update
```

- **Catch-up and retry:** processes every season day (Oct 1–Jul 31) in the last 10 days that has no statistics yet, so missed days are caught up and late-posted files are retried.
- **CU SWE:** used whenever its raster exists for the date.
- **Cleanup:** deletes raw SNODAS and SWANN files after processing, unless a `reports/<date>` folder exists for that date.
- **Publishing:** rebuilds both Explorer pages, copies them to `PUBLISH_DIR`, and pushes them to GitHub Pages.
- **Log:** `data/logs/daily_update.log`.

To schedule it with Windows Task Scheduler, edit the paths in `scripts/run_daily_update.bat`, then register it once:
```
schtasks /Create /TN "SWEET daily update" /TR "C:\path\to\nm_swe\scripts\run_daily_update.bat" /SC DAILY /ST 10:00
```
The task must run under the account that holds the GitHub sign-in.

### Weekly Rio Grande report

1. Download the latest CU SWE raster to `data/CU_SWE/YYYYMMDD_raster.tif`.
2. Set the report date near the top of `generate_report.py`. CU SWE data must exist for that date.
3. Run `python generate_report.py`.

The run also adds the report date to the statewide statistics and rebuilds the Explorer. Set `UPDATE_STATEWIDE = False` to skip that step. A statewide error never affects the report outputs.

Outputs go to `reports/YYYY-MM-DD/`:
- `figures/`: overview and difference maps, SWE-by-elevation plots
- `pdf_tables/`: SWE summary tables for each product and the ensemble
- `csv_tables/`: the same tables as CSV
- `pkl/`: intermediate files for the difference maps

### End of season (after Sep 30)

```
python scripts/rollover_wy.py --wy 2027
```

This adds the completed season to the history from the daily-run tables and recomputes the medians. No downloads are needed.

### Manual pieces

```
python -m src.run_daily 20261215              # one date
python -m src.build_web --wy 2027 --offline   # rebuild both pages
```

---

## Publishing (GitHub Pages)

The Explorer is served from the `gh-pages` branch, which holds only the two HTML files, an `index.html` redirect and `.nojekyll`. `PUBLISH_DIR` in `src/config.py` points to a local clone of that branch. Each daily run replaces the branch's single commit and force-pushes it, so the page never builds up history in the repository. Code changes go to `main` as usual.

## Repository layout

| Path | Purpose |
|---|---|
| `generate_report.py` | Weekly Rio Grande report, plus the statewide update block |
| `src/config.py` | Domain, agreement rule, grid, climatology and publishing settings |
| `src/domain.py` | Reporting basins (HUC8/HUC6/HUC12) and lookups |
| `src/zonal.py` | 500 m grid, agreement mask, basin and elevation-band statistics |
| `src/sources.py` | SNODAS / SWANN / CU SWE download and load |
| `src/run_daily.py` | Statewide statistics for one date |
| `src/daily_update.py` | Unattended daily update, cleanup and publishing |
| `src/backfill.py`, `src/climatology.py` | Historical record and per-product medians |
| `src/build_web.py`, `web/template.html` | Builds the Explorer pages |
| `web/vendor/` | Leaflet and Plotly copies (with licenses) for the offline page |
| `scripts/` | WBD and DEM fetches, source checks, Task Scheduler launcher, season rollover, WY2026 report imports |
| `tests/` | Synthetic end-to-end, backfill/climatology and daily-update checks |
| `data/stats/`, `data/climatology/`, `data/domain/` | Statistics tables, medians and basin lookups (small files, tracked) |
| `docs/` | Detailed statewide and historical-data documentation |

## Documentation

- [`docs/STATEWIDE.md`](docs/STATEWIDE.md): statewide design, basin conventions, elevation bands, page features, and changing boundaries mid-season
- [`docs/HISTORICAL_DATA_GUIDE.md`](docs/HISTORICAL_DATA_GUIDE.md): loading the WY2004–present history, and adding CU SWE history

## Optional: Climate Data Store (CDS) API for ERA5

1. Create an account at https://cds.climate.copernicus.eu/ and log in.
2. Click your name (top right) → *Your Profile*.
3. Copy the two lines for `url` and `key` under *API key*.
4. Paste them into a text file named `.cdsapi` in your home directory (usually `C:\Users\<username>`). Never commit this file.

---

## Background

SWEET was developed in response to the *Rio Grande River Basin Needs Assessment Report* (July 2022) as a two-year project (WY2025–WY2026). It began with 18 Rio Grande HUC8s and expanded statewide in WY2027. The original code was developed with the [Rittger Lab Group](https://github.com/RittgerLabGroup/nm_swe).

Planned work includes validation against Airborne Snow Observatory (ASO) data, CU SWE history, and possibly additional SWE products.

**Contact:** Max Gersh, P.H., New Mexico Office of the State Engineer, Hydrology Bureau
