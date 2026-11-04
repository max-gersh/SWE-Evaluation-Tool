"""
Historical backfill of per-product basin statistics (for the climatology).

For every day in the season window of each water year, download one product,
resample to the analysis grid, compute unmasked per-product statistics for all
HUC8 and HUC6 zones, append them, and delete the raw file. Each product is
compared only with its own history, so no agreement mask is applied here.

Output: data/stats/hist/<PRODUCT>/WY<yyyy>.parquet (one row per date x zone)
The run is resumable: finished water years are skipped, and a partial file
is checkpointed every 20 days.

Usage (from the repository root):
    python -m src.backfill --product SNODAS
    python -m src.backfill --product UA_SWE --start-wy 2004 --end-wy 2025
    python -m src.backfill --product SNODAS --every 3     # every 3rd day
"""
import argparse
import time
from datetime import date, timedelta

import pandas as pd

from src import config as C
from src import sources, zonal
from src.domain import load_domain

CHECKPOINT_EVERY = 20


def season_dates(wy, every=1):
    """Season days of a water year; with every > 1, only days whose day of water
    year (365-day calendar) is 1, 1+every, 1+2*every, ... so all years sample
    the same calendar days."""
    from src.climatology import dowy
    start = date(wy - 1, *C.SEASON_START)
    end = date(wy, *C.SEASON_END)
    d = start
    while d <= end:
        k = dowy([d])[0]
        if every == 1 or (k == k and (int(k) - 1) % every == 0):
            yield d.strftime("%Y%m%d")
        d += timedelta(days=1)


def backfill(product, start_wy=C.CLIM_START_WY, end_wy=C.BACKFILL_END_WY, keep_raw=False,
             every=C.BACKFILL_EVERY_N_DAYS):
    huc8, huc6 = load_domain()
    grid = zonal.build_grid(huc8, huc6)
    loader = sources.LOADERS[product]
    out_dir = C.STATS_DIR / "hist" / product
    out_dir.mkdir(parents=True, exist_ok=True)
    missing_log = out_dir / "missing_dates.csv"

    for wy in range(start_wy, end_wy + 1):
        final = out_dir / f"WY{wy}.parquet"
        partial = out_dir / f"WY{wy}.partial.parquet"
        if final.exists():
            print(f"{product} WY{wy}: done, skipping")
            continue
        frames = [pd.read_parquet(partial)] if partial.exists() else []
        done = set(frames[0]["date"].dt.strftime("%Y%m%d")) if frames else set()
        t0, n_new = time.time(), 0

        for d in season_dates(wy, every):
            if d in done:
                continue
            try:
                arr = zonal.to_grid(loader(d), grid)
            except sources.DataUnavailable as e:
                with open(missing_log, "a", encoding="utf-8") as f:
                    f.write(f"{d},{e}\n")
                print(f"  missing: {e}")
                continue
            swe = zonal.apply_threshold(arr)
            df = zonal.stats_all_levels(swe, grid)
            df.insert(0, "product", product)
            df.insert(0, "date", pd.Timestamp(d))
            frames.append(df)
            n_new += 1
            if not keep_raw:
                sources.cleanup(product, d)
            if n_new % CHECKPOINT_EVERY == 0:
                pd.concat(frames, ignore_index=True).to_parquet(partial, index=False)
                print(f"  {product} {d}: {n_new} days, {(time.time() - t0) / n_new:.1f} s/day")

        if frames:
            pd.concat(frames, ignore_index=True).to_parquet(final, index=False)
        partial.unlink(missing_ok=True)
        print(f"{product} WY{wy}: {n_new} new days written to {final}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--product", required=True, choices=C.PRODUCTS,
                    help="SNODAS / UA_SWE download automatically; CU_SWE reads local files "
                         "data/CU_SWE/<YYYYMMDD>_raster.tif (never deleted)")
    ap.add_argument("--start-wy", type=int, default=C.CLIM_START_WY)
    ap.add_argument("--end-wy", type=int, default=C.BACKFILL_END_WY)
    ap.add_argument("--every", type=int, default=C.BACKFILL_EVERY_N_DAYS,
                    help="sample every Nth day of the season (default from config)")
    ap.add_argument("--keep-raw", action="store_true", help="keep downloaded files")
    a = ap.parse_args()
    backfill(a.product, a.start_wy, a.end_wy, a.keep_raw, a.every)
