"""
Load HUC8 elevation-band volumes from the WY Table 3 summary CSV
(e.g. WY_Summary_Table3.csv) into the statewide elevation table.

Input layout (wide, one column per HUC8 x band):
    row 1  HUC6 Basin      (name in the first column of each HUC6 block)
    row 2  HUC8 Subbasin   (name in the first column of each HUC8 block)
    row 3  Elevation Band  e.g. 9000-10000'
    then, per date: Ensemble Mean / Median / Min. / Max. Vol. (af),
    Min. Source, Max. Source, Mean / Median Volume Change

With three products, min, median and max are the three product values, so each
product's band volume is recovered from min/median/max + the listed sources
(as for the basin totals). HUC6 bands are then the sum of the included HUC8
bands per product, and every ensemble statistic is recomputed from the
product values, the same way the daily pipeline does it.

Writes data/stats/current/WY<yyyy>_elev.parquet, replacing rows for the
imported dates. These report values predate the agreement mask.

Usage:  python scripts/import_table3_summary.py WY_Summary_Table3.csv --wy 2026
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config as C                                              # noqa: E402
from src.zonal import ensemble_from_wide                                 # noqa: E402
from scripts.import_wy2026_report import NAME_TO_HUC, split_products     # noqa: E402

STATS = {"Ensemble Mean Vol. (af)": "mean", "Ensemble Median Vol. (af)": "median",
         "Ensemble Min. Vol. (af)": "min", "Ensemble Max. Vol. (af)": "max",
         "Min. Source": "min_src", "Max. Source": "max_src"}


def _num(x):
    try:
        return float(str(x).replace(",", ""))
    except ValueError:
        return np.nan


def read_summary(path):
    raw = pd.read_csv(path, header=None, dtype=str, encoding="utf-8-sig")
    huc8_names = raw.iloc[1, 2:].ffill()
    bands = raw.iloc[2, 2:].str.extract(r"(\d+)")[0].astype(int)
    cols = [(NAME_TO_HUC.get(n), b) for n, b in zip(huc8_names, bands)]
    unknown = sorted({n for n, (h, _) in zip(huc8_names, cols) if h is None or len(h) != 8})
    if unknown:
        raise SystemExit(f"Unknown HUC8 names in header: {unknown}")

    records, date = {}, None
    for r in range(3, len(raw)):
        if isinstance(raw.iat[r, 0], str) and raw.iat[r, 0].strip():
            date = pd.to_datetime(raw.iat[r, 0].strip())
        stat = STATS.get(str(raw.iat[r, 1]).strip())
        if stat is None or date is None:
            continue
        for k, (huc, lo) in enumerate(cols):
            v = raw.iat[r, k + 2]
            rec = records.setdefault((date, huc, lo), {})
            rec[stat] = v if stat.endswith("src") else _num(v)
    rows = []
    for (date, huc, lo), rec in records.items():
        if any(np.isnan(rec.get(s, np.nan)) for s in ("min", "median", "max")):
            continue
        vals = split_products(rec["min"], rec["median"], rec["max"],
                              rec.get("min_src") or "", rec.get("max_src") or "")
        for p, v in vals.items():
            rows.append(dict(date=date, huc=huc, band_lo_ft=lo, product=p, volume_af=v,
                             report_mean=rec["mean"]))
    return pd.DataFrame(rows)


def build(long):
    h8 = long.assign(level="huc8")
    h6 = (long.assign(huc=long["huc"].str[:6])
          .groupby(["date", "product", "huc", "band_lo_ft"], as_index=False)["volume_af"].sum()
          .assign(level="huc6"))
    both = pd.concat([h8, h6], ignore_index=True)
    wide = both.pivot_table(index=["date", "level", "huc", "band_lo_ft"], columns="product",
                            values="volume_af", aggfunc="first")
    ens = pd.concat([wide.add_prefix("vol_"), ensemble_from_wide(wide)], axis=1).reset_index()
    ens["source"] = "WY2026 weekly reports (Table 3 summary, pre-agreement-mask)"
    return ens


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--wy", type=int, required=True)
    a = ap.parse_args()
    long = read_summary(a.csv)

    # check: mean of the recovered product values vs the report's ensemble mean
    chk = long.groupby(["date", "huc", "band_lo_ft"]).agg(m=("volume_af", "mean"), r=("report_mean", "first"))
    print(f"Recovered products vs report ensemble mean: max |diff| = {(chk.m - chk.r).abs().max():.1f} af "
          f"({len(chk)} HUC8 x band x date values)")

    ens = build(long.drop(columns="report_mean"))
    out = C.STATS_DIR / "current" / f"WY{a.wy}_elev.parquet"
    if out.exists():
        old = pd.read_parquet(out)
        # compare derived HUC6 bands with any HUC6 bands already present (mock page payload)
        o6 = old[old.level == "huc6"].set_index(["date", "huc", "band_lo_ft"]).ens_mean_af
        n6 = ens[ens.level == "huc6"].set_index(["date", "huc", "band_lo_ft"]).ens_mean_af
        common = o6.index.intersection(n6.index)
        if len(common):
            print(f"HUC6 bands (sum of HUC8) vs previous HUC6 bands: max |diff| = "
                  f"{(o6[common] - n6[common]).abs().max():.1f} af over {len(common)} values")
        ens = pd.concat([old[~old["date"].isin(ens["date"].unique())], ens], ignore_index=True)
    ens.sort_values(["date", "level", "huc", "band_lo_ft"]).to_parquet(out, index=False)
    print(f"Imported {long['date'].nunique()} dates, {long['huc'].nunique()} HUC8s -> {out}")


if __name__ == "__main__":
    main()
