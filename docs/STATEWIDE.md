# SWEET statewide expansion

New modules sit beside the existing Rio Grande report code. `generate_report.py` and its modules are unchanged.

| File | Purpose |
|---|---|
| `src/config.py` | Domain rule, agreement rule (0.1 in, ≥2 products, zeros kept), grid, climatology period |
| `src/domain.py` | HUC8s intersecting NM plus the upstream RG/San Juan headwaters, with parent HUC6 and OSE grouping; selected HUC12s |
| `src/zonal.py` | Common EPSG:5070 500 m grid, rasterized HUC zones, agreement mask, vectorised basin and elevation-band statistics |
| `src/sources.py` | SNODAS / UA SWE / CU SWE download and load (fixed downloaders) |
| `src/run_daily.py` | Statewide run for one date to `data/stats/current/WY<yyyy>_{products,ensemble,elev}.parquet` plus agreement/ensemble rasters |
| `src/daily_update.py` | Unattended daily update: catch-up/retry, raw-file cleanup, page rebuild and publish |
| `generate_report.py` | Weekly Rio Grande report (unchanged), plus a guarded block at the end that adds the report date statewide and rebuilds the page (`UPDATE_STATEWIDE`) |
| `scripts/run_daily_update.bat` | Task Scheduler launcher for `src.daily_update` |
| `scripts/rollover_wy.py` | End of season: adds the completed WY to the history and rebuilds the climatology (no downloads) |
| `src/backfill.py` | One-time, resumable WY2004–2025 per-product history for SNODAS and UA SWE (optionally every Nth day) |
| `src/climatology.py` | Per-product day-of-WY median and percentiles |
| `src/build_web.py` + `web/template.html` | Self-contained map and chart page, `web/sweet_explorer.html` |
| `scripts/import_wy2026_report.py` | Loads the WY2026 weekly-report values (basin totals and HUC6 elevation bands) into the new format |
| `scripts/import_table3_summary.py` | Loads HUC8 elevation bands from the WY Table 3 summary CSV (`data/reports/WY2026_Summary_Table3.csv`) |
| `scripts/import_table3_reports.py` | Alternative: loads HUC8 bands from the per-date, per-product Table 3 CSVs in `reports/` |
| `scripts/fetch_wbd_additions.py` | Verifies against USGS WBD and downloads the Mancos HUC8 (`WBD_supplement/`) and the selected HUC12s (`WBD_HUC12/`) |
| `scripts/fetch_3dep_dem.py` | Downloads a USGS 3DEP DEM for the full domain to `data/dem_3dep_ft.tif` (100 m, feet) |
| `web/vendor/` | Local copies of Leaflet 1.9.4 and Plotly (basic) 2.35.2 with their licenses, used for the offline page |
| `scripts/check_sources.py` | Pre-flight test of the SNODAS/SWANN archives, with download and run-time estimates for the backfill |
| `HISTORICAL_DATA_GUIDE.md` | Step-by-step guide to loading the WY2004–2025 history (and CU SWE later) |
| `tests/` | Synthetic end-to-end, backfill/climatology and daily-update checks |

## Basin conventions
- **HUC8s:** all 81 reporting HUC8s (those that intersect NM, plus the upstream Rio Grande and San Juan headwaters) are reported whatever their snow amount.
- **HUC6 totals:** each is the sum of its included HUC8s. On the grid, HUC6 zones are derived from the HUC8 zones, so the sums are exact.
- **Partial HUC6s:** 10 of the 19 HUC6s extend beyond the included HUC8s, by more than 1% of their area (`PARTIAL_HUC6_FRAC`). Their totals are marked with * on the page, and `data/domain/huc6_lookup.csv` lists each one's coverage and excluded HUC8s.
- **Piedra (14080102):** derived as WBD HUC6 140801 minus its other six HUC8s. It is stored in `data/Shapefiles/WBD_supplement/`, and its area matches the WBD attributes to within 0.01 km².
- **Mancos (14080107):** downloaded from USGS WBD by `scripts/fetch_wbd_additions.py` to `data/Shapefiles/WBD_supplement/wbdhu8_mancos.shp` and listed in `EXTRA_HUC8`. With it, Upper San Juan (140801) is complete (100%, no longer partial). It has no OSE grouping; Table 2's San Juan grouping is unchanged.
- **HUC12s (HUC12 tab):** a hand-picked set in `data/Shapefiles/WBD_HUC12/wbdhu12_sweet.shp` (`C.WBD_HU12`), currently 8:

  | HUC12 | Name | HUC8 |
  |---|---|---|
  | 130202010102 | Headwaters Santa Fe River | 13020201 |
  | 140801010602 | Headwaters Navajo River | 14080101 |
  | 140801010302 | Headwaters Rio Blanco | 14080101 |
  | 130201020201 | Headwaters Rio Chama | 13020102 |
  | 140801010604 | Little Navajo River | 14080101 |
  | 140801010601 | East Fork Navajo River | 14080101 |
  | 130201020202 | Archuleta Creek | 13020102 |
  | 130201020203 | Wolf Creek | 13020102 |

  - The names are authoritative: `fetch_wbd_additions.py` finds each name's ID in WBD within its parent HUC8 (`HUC12_NAMES`) and writes the shapefile only when every name matches exactly one HUC12. The IDs in `data/domain/huc12_lookup.csv` are the confirmed ones.
  - Rasterized on the same 500 m grid as their own zone level. They are reported on their own and never added into HUC8/HUC6 totals.
  - With a few hundred pixels each, their boundary rasterization error is a few percent, versus under 2% for HUC8s (`tests/test_synthetic.py` allows 6% for HUC12s).
  - To add or remove HUC12s, edit `HUC12_NAMES` in the fetch script, re-run it, then `python -m src.domain`. Without the shapefile the page has no HUC12 tab.

## Elevation bands
- **Data:** ensemble SWE volume by 1000-ft band (`ELEV_BAND_FT`) for every HUC12, HUC8 and HUC6, computed inside the agreement mask like the basin totals. The band volumes add up exactly to each basin's volume (checked in `tests/test_synthetic.py`).
- **DEM:** `DEM_PATH` defaults to `data/dem_3dep_ft.tif`, the USGS 3DEP DEM written by `scripts/fetch_3dep_dem.py`.
  - It is fetched in EPSG:5070 at 100 m from The National Map's 3DEP ImageServer and converted from metres to feet.
  - The download is in about 25 cached tiles, a few hundred MB, and resumes if interrupted.
  - The DEM is averaged onto the 500 m grid, and bands are assigned by each pixel's mean elevation.
  - `run_daily` warns if the DEM covers less than 99% of the 81 HUC8s.
  - The Rio Grande report DEM (`data/dem.tif`, feet) is kept only for `generate_report.py`. The fetch script reports the median difference from it as a sanity check.
- **Page:** the "SWE volume by elevation band" chart sits under the SWE volume chart and follows the Date dropdown. It shows:
  - bars: ensemble mean;
  - whiskers: product min–max;
  - colour: change since the previous report.
- **WY2026 data:** the 18 Rio Grande HUC8s, 15 report dates, come from the Table 3 summary CSV.
  - Each product's band volume is recovered from min/median/max plus sources, within 0.7 af of the report mean.
  - HUC6 bands are HUC8 sums. They agree with the mock page's HUC6 bands within 3 af.
  - Band totals match basin totals within 4 af.
  - Import order: `import_wy2026_report.py` first, then `import_table3_summary.py`.

## Setup
1. Add `pyarrow` and `shapely>=2.1` to `environment.yml`, then update the environment:
   `conda env update -f setup/environment.yml`
2. Put the WBD extract in `data/Shapefiles/WBD_NM/` (`wbdhu8_a_nm.shp`, `wbdhu6_a_nm.shp`).
3. Put `WBDHU8_RG` in `data/Shapefiles/WBDHU8_RG/`. It supplies Rio Grande Headwaters, San Luis and Saguache.
4. Run `python scripts/fetch_wbd_additions.py` (needs access to hydro.nationalmap.gov). It checks every HUC name, ID and area against WBD and writes nothing on a mismatch. Piedra and Mancos then come from `data/Shapefiles/WBD_supplement/`, the HUC12s from `data/Shapefiles/WBD_HUC12/`.
5. Run `python -m src.domain`. It should report "81 HUC8s, 19 HUC6s (10 partial), 8 HUC12s".

## Run order
```
python scripts/fetch_wbd_additions.py           # once: Mancos HUC8 + selected HUC12s from USGS WBD
python -m src.domain                            # once, or when boundaries change
python scripts/fetch_3dep_dem.py                # once: statewide DEM for elevation bands
python tests/test_synthetic.py                  # optional sanity check (synthetic data)
python scripts/check_sources.py                 # before the backfill: test archives, estimate size/time
python -m src.backfill --product SNODAS         # one-time; resumable (add --every 3 to sample every 3rd day)
python -m src.backfill --product UA_SWE
python -m src.climatology
python -m src.daily_update --since 20261001     # first run of the season, then daily via Task Scheduler
python generate_report.py                       # weekly report; also updates the page
python scripts/rollover_wy.py --wy 2027         # after Sep 30: add the season to the history
# manual pieces, if needed:
python -m src.run_daily 20261215                # one date
python -m src.build_web --wy 2027 --offline     # rebuild both pages
```

## Changing the boundaries mid-season
Statistics are stored per basin, so new basins need their dates recomputed:
1. `python -m src.domain`. The grid cache rebuilds itself when the domain changes.
2. Move the current `data/stats/current/WY<yyyy>_*.parquet` files aside, then run `python -m src.daily_update --since <yyyy-1>1001`. `daily_update` only fills days without statistics.
3. History for the new basins needs the backfill and `python -m src.climatology` again. Without it they show the current year only.

## History on the page
- **Axis:** the Compare-with-history panels run over the full water year, Oct 1 – Sep 30. The SWEET ensemble chart zooms to the season's report dates (first to last report, lightly padded).
- **Compare with history:** one panel per product with a history (SNODAS, SWANN, and CU SWE once added). Each panel shows:
  - the WY2004–present **median** (dashed);
  - the **interquartile range**, 25th–75th percentile (shaded);
  - the **current water year** (solid line, no markers), in the product's colour, over the **whole season**, not just SWEET report dates. It comes from the daily run's unmasked per-product values, or from a backfill of the current year (`python -m src.backfill --product SNODAS --start-wy 2026 --end-wy 2026`, used for WY2026). With neither, it falls back to the report dates. Basins without a SWEET estimate still get this tab when they have current-year or history data.
  - The current year is never folded into its own median: `src.climatology` uses completed water years only, and past-year buttons stop at the year before the page's water year.
- **Water-year buttons** under the panels add up to 5 past years to every panel, each in its own colour. "Highest peak" and "Lowest peak" pick those years for the selected basin, and "Clear" removes them. The selection stays when you switch basins.
- **Sampling:** the history is sampled every 3rd day of the water year (`BACKFILL_EVERY_N_DAYS = 3`). Every year shares the same calendar days, and the rollover and climatology keep that grid. Past years are drawn on the current water year's calendar.
- **Page size:** the per-year series add roughly 3–4 MB for 81 HUC8s + 19 HUC6s (+ 8 HUC12s) × 22 years × 2 products, making the email version about 6 MB (under 2 MB zipped).

## Map metrics
- **SWE:** ensemble basin SWE volume on the selected date.
- **Change since previous week:** ensemble volume on the selected date minus the volume 7 days earlier. If that day is missing, the latest date 8–10 days earlier is used, and the legend names the two dates. With no estimate in that window the basin is greyed out.
- **% of median:** one entry per product (SNODAS, SWANN, CU SWE). An entry stays disabled until that product's climatology exists; CU SWE shows "no history yet".
- The SWEET ensemble chart draws lines only (no point markers), and the KPI card still shows the change since the previous date.

## Full screen and downloads
The map, the SWE chart and the elevation-band chart each have three buttons (map: bottom right; charts: top right of their panel):
- **Full screen** — fills the screen with that panel (Esc or the button again to exit). Where the browser blocks true full screen, the panel fills the window instead.
- **PNG** — a 2x image with a title (basin, HUC code, date or water year) on a white background. The map image includes basin shading, state and city labels and the legend.
- **CSV** — the data behind the view, UTF-8 with a BOM so Excel opens it cleanly:
  - map: every basin at the current level for the selected date (metric shown, ensemble mean/median/min/max, change since the previous week with the date it is measured from, each product's volume, % of median when available), with `parent_huc6` and `parent_huc8` columns;
  - SWE chart (ensemble tab only; the history tab has full screen and PNG but no CSV): one row per report date with the ensemble statistics and each product;
  - elevation chart: every report date and 1000-ft band for the basin, not just the selected date.

Downloads work in the hosted and offline pages; the Claude artifact preview blocks them.

## Keeping the page current
- **Weekly report.** Running `generate_report.py` as usual now also adds the report date statewide and rebuilds both pages. It reuses the SNODAS, SWANN and CU SWE files the report just downloaded. Set `UPDATE_STATEWIDE = False` to skip this. The block is wrapped so a statewide error never affects the report outputs.
- **Daily, unattended.** `python -m src.daily_update` does the following:
  - It processes every season day (Oct 1–Jul 31) from the last `LOOKBACK_DAYS` (10) through yesterday that has no statistics yet. Missed days are therefore caught up, and days whose files were not posted yet are retried on the next run.
  - CU SWE is used whenever `data/CU_SWE/<date>_raster.tif` exists. Other days are 2-product ensembles (SNODAS + SWANN, both must agree), marked "· 2 products" in the page's Date list and noted under the chart.
  - After each day it deletes the raw SNODAS and SWANN files, unless a `reports/<date>` folder exists. Daily rasters older than `KEEP_RASTER_DAYS` (14) are also deleted, so only the statistics tables accumulate: a few MB per season.
  - It rebuilds `web/sweet_explorer.html` and `web/sweet_explorer_offline.html` and copies them to `PUBLISH_DIR` if one is set in `src/config.py`.
  - It logs to `data/logs/daily_update.log`.
- **Task Scheduler.** Edit the two paths in `scripts/run_daily_update.bat`, then register it once:
  `schtasks /Create /TN "SWEET daily update" /TR "C:\path\to\nm_swe\scripts\run_daily_update.bat" /SC DAILY /ST 10:00`
  The computer must be on and the network drive reachable at that time. Missed days are caught up at the next run, within `LOOKBACK_DAYS`.
- **First season start-up.** Run `python -m src.daily_update --since 20261001` once to fill every day from Oct 1.
- **History.** The one-time backfill (WY2004–2025) downloads one day at a time, computes the statistics, and deletes the file. `--every 3` (or `BACKFILL_EVERY_N_DAYS`) samples every 3rd day, cutting the download about 3×. The median and percentile curves are then interpolated between sampled days. After that, history never needs downloading again: after Sep 30, `python scripts/rollover_wy.py --wy 2027` adds the completed season from the daily-run tables and recomputes the medians. The page's history period (e.g. WY2004–WY2027) comes from the data. Rows imported from the weekly reports are never rolled into the history.

## Sharing the page
- `web/sweet_explorer.html` loads Leaflet and Plotly from jsDelivr, so viewers need internet access. Use it for web hosting such as drought.nm.gov.
- `web/sweet_explorer_offline.html`, written with `--offline`, has both libraries built in from `web/vendor/` and makes no network requests. It is about 2.6 MB and falls back to a system font.
- Mail filters often block `.html` attachments, so send the offline file zipped. Recipients must save it and open it in Chrome, Edge or Firefox; it will not run in the Outlook preview pane.

## Things to verify on first real runs
- **SNODAS masked-grid corners before 2013-10-01** (`SNODAS_BOUNDS_OLD` in `src/sources.py`). Already checked against NSIDC's documentation; overlay one pre-2013 grid on the HUCs as a visual check.
- **UA SWE files for older water years.** Check that the WY folder listing still matches the date-in-filename rule.
- **3DEP DEM.** After the fetch, check the reported median difference against `data/dem.tif`. It should be within a few tens of feet.
- **CU SWE nodata and units.** The loader assumes metres with negative values as nodata, the same as the current loader.
- **HUC12 names.** `fetch_wbd_additions.py` prints each name's WBD ID next to the originally supplied ID; a name that is not found or is ambiguous lists candidates and blocks the HUC12 write.
