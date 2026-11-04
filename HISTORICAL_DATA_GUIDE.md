# Loading the SNODAS and SWANN history (WY2004–WY2025)

This is a one-time job. It gives each product its own record, which drives the page's "Compare with history" view and the "% of median" maps.

For every day, the backfill downloads that product's grid, computes the statistics for all 80 HUC8s and 19 HUC6s on the SWEET grid, and **deletes the file**. Only small tables are kept: about 1 MB per product per water year. The download volume is unavoidable, but nothing large is ever stored.

| | SNODAS | SWANN (UA SWE) |
|---|---|---|
| Source | NSIDC G02158, masked archive (open HTTPS, no login) | University of Arizona, `DailyData_800m/WY<yyyy>/` |
| Record used | WY2004–WY2025 (the archive starts 30 Sep 2003) | WY2004–WY2025, the same years as SNODAS so the two are comparable |
| Days | Oct 1 – Jul 31, every 3rd day: about 2,240 days | same |
| File size | 1.2–35 MB per day (NSIDC) | measured in step 3 |

The same scripts, `generate_report.py`, already download from both servers, so the office network should allow them.

---

## Step 1 — Put the code in place and update the environment
1. Unzip `sweet_statewide.zip` at the repo root.
2. Add `pyarrow` and `shapely>=2.1` to `setup/environment.yml` and run:
   `conda env update -f setup/environment.yml`
3. Activate the environment: `conda activate nm_swe`

## Step 2 — Build the basin grid
```
python -m src.domain
```
Expected output: `Domain: 80 HUC8s, 19 HUC6s (11 partial)`.

Do this before the backfill: the history is computed per basin, and adding a basin later means redoing it.

## Step 3 — Test both archives (about 5 minutes)
```
python scripts/check_sources.py
```
This downloads 5 SNODAS days and 3 SWANN days, processes them, deletes them, and prints:
- `ok` or `FAILED` for each test day, with file size, download time and processing time;
- the SWE volume over the 80 HUC8s and over the Rio Grande Headwaters. It should be sensible for 1 March and near zero for 1 October;
- an **estimate of total download volume and hours** for every day and for every 3rd day.

It also writes `data/logs/check_sources/snodas_20130301.png` and `snodas_20140301.png`. Look at them: the snow should sit on the mountains inside the HUC8 outlines in both. They fall on either side of the 2013 grid change.

**Send me the printed output and the two PNGs.** I'll confirm everything looks right before you start the long run.

## Step 4 — Sampling: every 3rd day (the default)
- The history is sampled every 3rd day of the water year (Oct 1, Oct 4, Oct 7, …), set by `BACKFILL_EVERY_N_DAYS = 3` in `src/config.py`.
- The pre-check prints the resulting download and time next to the every-day estimate. The 3-day figure is the one that applies.
- The medians, the interquartile range and each historical year's line are all drawn on these days. Every year shares the same calendar days, so years compare directly.
- The end-of-season rollover keeps completed seasons on the same 3-day grid.

## Step 5 — Run the backfill
Open **two** terminals (both `conda activate nm_swe`, both in the repo root) so the products run side by side:
```
python -m src.backfill --product SNODAS
python -m src.backfill --product UA_SWE
```
While it runs:
- **Progress:** a line every 20 processed days (`20 days, 1.9 s/day`), then `WY2004: 102 new days written`.
- **Resuming:** if it stops (reboot, network drop, Ctrl-C), run the **same command** again. Finished years are skipped, and a partly finished year resumes from its last checkpoint.
- **Missing days:** days the archive doesn't have are logged to `data/stats/hist/<PRODUCT>/missing_dates.csv` and skipped. NSIDC lists known SNODAS gaps in `G02158_missing_files.txt`.
- **Keep the PC awake:** set Windows *Power & sleep* to "Never" for the duration. Or run a few years at a time:
  `python -m src.backfill --product SNODAS --start-wy 2004 --end-wy 2010`

### Step 5b — Fill the whole WY2026 season for the current-year line
The **Compare with history** panels draw the current water year across the whole season, not only on SWEET report dates. For WY2026, which had no daily run, fill it with the same backfill (about 100 days per product at every 3rd day):
```
python -m src.backfill --product SNODAS --start-wy 2026 --end-wy 2026
python -m src.backfill --product UA_SWE --start-wy 2026 --end-wy 2026
```
- It writes `data/stats/hist/<PRODUCT>/WY2026.parquet`. `build_web` picks it up for the current-year line; until then the line falls back to the report dates.
- While WY2026 is the page's current year it is **not** counted in the median/IQR or offered as a past-year button. Once WY2026 has ended, `python -m src.climatology` includes it (period WY2004–WY2026), so no rollover is needed for WY2026.
- From WY2027 on, the daily run covers every season day, so the current-year line fills in by itself.

## Step 6 — Check the output
- `data/stats/hist/SNODAS/` and `data/stats/hist/UA_SWE/` should each hold 22 files, `WY2004.parquet` … `WY2025.parquet`, and no `.partial` files.
- Open `missing_dates.csv` in each folder. A handful of dates is normal. Whole months missing means a problem.

## Step 7 — Build the medians
```
python -m src.climatology
```
Expected output: `SNODAS: climatology from 22 water years` and the same for `UA_SWE`. It writes `data/climatology/SNODAS_clim.parquet` and `UA_SWE_clim.parquet`.

## Step 8 — Rebuild the page
```
python -m src.build_web --wy 2026 --offline
```
Open `web/sweet_explorer_offline.html` and check:
- a basin's **Compare with history** tab shows one panel per product, each with the historical median, the interquartile range (25th–75th percentile) and the current year;
- the water-year buttons under the panels add individual past years to every panel (up to 5);
- **Map shows** lists "% of median — SNODAS / SWANN (UA)" as available;
- the footer reads "WY2004–WY2025".

## Step 9 — Send me the results for checking
Zip `data/climatology/` and `data/stats/hist/`, together about 50–100 MB. I'll check:
- the SNODAS series across the October 2013 grid change, for a jump;
- SNODAS against SWANN, and peak volumes against your past Rio Grande reports;
- the gaps.

I'll then republish the page with the history in it.

---

## Adding CU SWE history later
CU SWE is read from local files and never downloaded or deleted by the code.

1. **Save the files.** Put the historical rasters in `data/CU_SWE/` as `<YYYYMMDD>_raster.tif`, the same format as your weekly CU SWE files: GeoTIFF, SWE in metres. If the history arrives in another format (netCDF, one file per year, different units), send me one file and I'll adapt the loader.
2. **Process them.**
   `python -m src.backfill --product CU_SWE`
   Days without a file are simply logged as missing.
3. **Turn on the CU SWE history.** In `src/config.py`, set `CLIM_PRODUCTS = ["SNODAS", "UA_SWE", "CU_SWE"]`. Then run `python -m src.climatology` and rebuild the page. "CU SWE" becomes selectable under "Compare with history".
4. **Optional: a historical SWEET ensemble.** Once all three records overlap, the historical SWEET ensemble can be computed with the same ≥2-product agreement rule, giving an ensemble median to compare the current season against. It needs a combined backfill pass over the three products; I can add that when the CU data is in hand.

## After the backfill: keeping the history current
Nothing else is ever downloaded for the history. After each season (after Sep 30), run:
```
python scripts/rollover_wy.py --wy 2027
```
It adds the completed season from the daily-run tables and recomputes the medians. The page's period then extends automatically (WY2004–WY2027).
