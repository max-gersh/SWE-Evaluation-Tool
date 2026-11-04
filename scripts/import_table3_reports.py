"""
Load HUC8 elevation-band volumes from the weekly Rio Grande reports' Table 3
CSVs into the statewide elevation table, so HUC8 elevation charts can be shown
for dates before the statewide daily run.

Reads   reports/<YYYY-MM-DD>/csv_tables/table3_<PRODUCT>_<YYYYMMDD>.csv
        for PRODUCT in SNODAS, UA_SWE, CU_SWE (the per-product tables; the
        ensemble table is recomputed so HUC6 rows can be derived exactly)
Writes  data/stats/current/WY<yyyy>_elev.parquet, replacing rows for the
        imported dates (HUC8 rows + HUC6 rows = sum of the included HUC8s)

These report tables predate the agreement mask (per-product, unmasked).

Usage:  python scripts/import_table3_reports.py path/to/reports --wy 2026
"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config as C                                     # noqa: E402
from src.zonal import ensemble_from_wide                        # noqa: E402
from scripts.import_wy2026_report import NAME_TO_HUC            # noqa: E402

PRODUCTS = ["SNODAS", "UA_SWE", "CU_SWE"]
PAT = re.compile(r"table3_(SNODAS|UA_SWE|CU_SWE)_(\d{8})\.csv$")


def read_reports(reports_dir):
    rows = []
    for f in sorted(Path(reports_dir).glob("*/csv_tables/table3_*.csv")):
        m = PAT.search(f.name)
        if not m:
            continue
        product, date = m.group(1), pd.Timestamp(m.group(2))
        df = pd.read_csv(f, encoding="utf-8-sig")
        for name, band, vol in zip(df["HUC8 Subbasin"], df["Elevation Band (ft.)"], df["Estimated Volume (af)"]):
            huc = NAME_TO_HUC.get(name)
            if huc is None or len(huc) != 8:
                print(f"  skipped unknown HUC8 name {name!r} in {f.name}")
                continue
            lo = int(re.match(r"\s*(\d+)", str(band)).group(1))          # e.g. "9000-10000'"
            rows.append(dict(date=date, product=product, huc=huc, band_lo_ft=lo, volume_af=float(vol)))
    if not rows:
        raise SystemExit(f"No table3_<product>_<date>.csv files under {reports_dir}")
    return pd.DataFrame(rows)


def build(long):
    h8 = long.assign(level="huc8")
    h6 = (long.assign(huc=long["huc"].str[:6])
          .groupby(["date", "product", "huc", "band_lo_ft"], as_index=False)["volume_af"].sum(min_count=1)
          .assign(level="huc6"))
    both = pd.concat([h8, h6], ignore_index=True)
    wide = both.pivot_table(index=["date", "level", "huc", "band_lo_ft"], columns="product",
                            values="volume_af", aggfunc="first")
    ens = pd.concat([wide.add_prefix("vol_"), ensemble_from_wide(wide)], axis=1).reset_index()
    ens["source"] = "WY weekly reports (Table 3, pre-agreement-mask)"
    return ens


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("reports_dir")
    ap.add_argument("--wy", type=int, required=True)
    a = ap.parse_args()
    long = read_reports(a.reports_dir)
    ens = build(long)
    out = C.STATS_DIR / "current" / f"WY{a.wy}_elev.parquet"
    if out.exists():
        old = pd.read_parquet(out)
        ens = pd.concat([old[~old["date"].isin(ens["date"].unique())], ens], ignore_index=True)
    ens.sort_values(["date", "level", "huc", "band_lo_ft"]).to_parquet(out, index=False)
    n8 = ens.loc[ens.level == "huc8", "huc"].nunique()
    print(f"Imported {long['date'].nunique()} report dates, {n8} HUC8s -> {out}")


if __name__ == "__main__":
    main()
