"""
End-of-season rollover: add a completed water year to the history and rebuild
the climatology, with no downloads.

The daily run (src.run_daily) already stores each product's unmasked basin
statistics in data/stats/current/WY<yyyy>_products.parquet. This script copies
the SNODAS and UA SWE rows of that season into data/stats/hist/<PRODUCT>/,
in the same format as the backfill (sampled on the same every-Nth-day grid,
BACKFILL_EVERY_N_DAYS), then reruns src.climatology. Each season
therefore extends the historical record by one year automatically.

Rows imported from the weekly reports (prototype data, 'source' column) are
skipped: they are not daily statewide statistics. A season is only rolled
over if it has at least --min-days processed days per product.

Usage (after Sep 30):  python scripts/rollover_wy.py --wy 2027
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config as C            # noqa: E402
from src import climatology            # noqa: E402
from src.climatology import dowy        # noqa: E402

HIST_COLS = ["date", "product", "level", "huc", "mean_in", "median_in",
             "volume_af", "snow_area_km2", "valid_area_km2"]


def rollover(wy, min_days=150, force=False):
    src = C.STATS_DIR / "current" / f"WY{wy}_products.parquet"
    if not src.exists():
        raise SystemExit(f"{src} not found")
    df = pd.read_parquet(src)
    if "source" in df:
        df = df[df["source"].isna() | ~df["source"].astype(str).str.contains("report", case=False)]
    df = df[(~df["masked"]) & df["product"].isin(C.CLIM_PRODUCTS)]
    n = C.BACKFILL_EVERY_N_DAYS
    if n > 1:   # keep the history on the same every-Nth-day grid as the backfill
        k = dowy(df["date"])
        df = df[(k == k) & ((k - 1) % n == 0)]
        min_days = int(min_days / n)
    done = []
    for product, g in df.groupby("product"):
        n = g["date"].nunique()
        out = C.STATS_DIR / "hist" / product / f"WY{wy}.parquet"
        if n < min_days:
            print(f"{product} WY{wy}: only {n} daily-run days (< {min_days}); not added to history")
            continue
        if out.exists() and not force:
            print(f"{product} WY{wy}: already in history ({out}); use --force to replace")
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        g[[c for c in HIST_COLS if c in g]].to_parquet(out, index=False)
        print(f"{product} WY{wy}: {n} days added to history -> {out}")
        done.append(product)
    for product in done:
        climatology.build(product, last_wy=wy)
    return done


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--wy", type=int, required=True)
    ap.add_argument("--min-days", type=int, default=150)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    rollover(a.wy, a.min_days, a.force)
