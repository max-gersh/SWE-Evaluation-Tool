"""
Convert the WY2026 weekly-report values (sweet_basin_explorer_offline_v2.html
payload) into the statewide statistics format, so the web prototype can be
built before the daily pipeline has run for a full season.

The payload holds ensemble mean/median/min/max volumes with the min/max source.
With three products, min, median and max are the three product values, so each
product's volume is recovered exactly: min -> min_source, max -> max_source,
median -> the remaining product (ties handled via the listed sources).

These values predate the agreement mask, so they are written as both the
masked and unmasked rows and flagged with source='WY2026 weekly report'.

HUC6 rows are not taken from the report's HUC6 totals: they are rebuilt as the
sum of the included HUC8 product volumes (the statewide convention), and the
ensemble statistics are recomputed from those sums. The script prints the
difference from the report's own HUC6 totals as a check.

Usage: python scripts/import_wy2026_report.py path/to/sweet_basin_explorer_offline_v2.html
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config as C  # noqa: E402

PRODUCTS = ["SNODAS", "UA_SWE", "CU_SWE"]
NAME_TO_HUC = {
    # HUC8
    "Rio Grande Headwaters": "13010001", "Alamosa-Trinchera": "13010002",
    "San Luis": "13010003", "Saguache": "13010004", "Conejos": "13010005",
    "Upper Rio Grande": "13020101", "Rio Chama": "13020102",
    "Rio Grande-Santa Fe": "13020201", "Jemez": "13020202",
    "Rio Grande-Albuquerque": "13020203", "Rio Puerco": "13020204",
    "Arroyo Chico": "13020205", "North Plains": "13020206", "Rio San Jose": "13020207",
    "Plains of San Agustin": "13020208", "Rio Salado": "13020209",
    "Jornada Del Muerto": "13020210", "Elephant Butte Reservoir": "13020211",
    # HUC6 totals
    "Rio Grande Headwaters Total": "130100", "Upper Rio Grande Total": "130201",
    "Rio Grande-Elephante Butte Total": "130202", "Rio Grande-Elephant Butte Total": "130202",
}


def split_products(mn, md, mx, min_src, max_src):
    """Recover the three product values from min/median/max + sources."""
    vals = {}
    lo = [s.strip() for s in min_src.split(",")] if min_src else []
    hi = [s.strip() for s in max_src.split(",")] if max_src else []
    for p in lo:
        vals[p] = mn
    for p in hi:
        vals.setdefault(p, mx)
    for p in PRODUCTS:
        vals.setdefault(p, md)
    return vals


def main(html_path):
    s = Path(html_path).read_text(encoding="utf-8")
    data = json.loads(re.search(r'id="data-payload"[^>]*>(.*?)</script>', s, re.S).group(1))
    rows, report_huc6, check = [], {}, []
    for name, d in data.items():
        huc = NAME_TO_HUC[name]
        for i, md_str in enumerate(d["dates"]):
            m, dd = md_str.split("/")
            date = pd.Timestamp(f"{2026 if int(m) < 10 else 2025}-{m}-{dd}")
            if len(huc) == 6:                      # report total: kept only for the check
                report_huc6[(huc, date)] = d["mean"][i]
                continue
            mn, md, mx, mean = d["min"][i], d["median"][i], d["max"][i], d["mean"][i]
            vals = split_products(mn, md, mx, d["min_source"][i], d["max_source"][i])
            check.append(abs(np.mean(list(vals.values())) - mean))
            for p, v in vals.items():
                rows.append(dict(date=date, product=p, level="huc8", huc=huc, volume_af=float(v)))
    print(f"Reconstruction check: max |mean(products) - reported mean| = {max(check):.1f} af "
          f"(payload values are rounded to 1 af)")

    h8 = pd.DataFrame(rows)
    h6 = (h8.assign(huc=h8["huc"].str[:6]).groupby(["date", "product", "huc"], as_index=False)["volume_af"].sum()
          .assign(level="huc6"))
    prod = pd.concat([h8, h6], ignore_index=True)

    ens_rows = []
    for (date, level, huc), g in prod.groupby(["date", "level", "huc"]):
        v = dict(zip(g["product"], g["volume_af"]))
        arr = np.array(list(v.values()))
        src = lambda t: ", ".join(p for p, x in v.items() if np.isclose(x, t, atol=0.5))
        ens_rows.append(dict(date=date, level=level, huc=huc, ens_mean_af=arr.mean(),
                             ens_median_af=float(np.median(arr)), ens_min_af=arr.min(), ens_max_af=arr.max(),
                             min_source=src(arr.min()), max_source=src(arr.max()),
                             n_products=len(arr), reported=bool(arr.max() > 0), source="WY2026 weekly report"))
    ens = pd.DataFrame(ens_rows)
    e6 = ens[ens.level == "huc6"].set_index(["huc", "date"])["ens_mean_af"]
    diffs = [abs(e6[k] - v) for k, v in report_huc6.items() if k in e6.index]
    print(f"HUC6 = sum of HUC8s vs report HUC6 totals: max |diff| = {max(diffs):,.0f} af over {len(diffs)} values")

    prod = pd.concat([prod.assign(masked=False), prod.assign(masked=True)], ignore_index=True)
    prod["source"] = "WY2026 weekly report"
    rows = prod
    out = C.STATS_DIR / "current"
    out.mkdir(parents=True, exist_ok=True)
    rows.to_parquet(out / "WY2026_products.parquet", index=False)
    ens.to_parquet(out / "WY2026_ensemble.parquet", index=False)
    print(f"Wrote {len(rows)} product rows and {len(ens_rows)} ensemble rows to {out}")

    # elevation bands: the payload holds HUC6-level ensemble mean/median per
    # 1000-ft band (no per-product values, so no min/max). HUC8 bands come from
    # the reports' Table 3 CSVs via scripts/import_table3_reports.py.
    m = re.search(r'id="elevation-payload"[^>]*>(.*?)</script>', s, re.S)
    if m and (out / "WY2026_elev.parquet").exists() and \
            (pd.read_parquet(out / "WY2026_elev.parquet").level == "huc8").any():
        print("WY2026_elev.parquet already holds HUC8 bands (Table 3 import); left unchanged")
        m = None
    if m:
        el = json.loads(m.group(1))
        erows = []
        for name, d in el.items():
            huc = NAME_TO_HUC.get(name + " Total") or NAME_TO_HUC[name]
            if len(huc) != 6:
                huc = NAME_TO_HUC[name + " Total"]
            lows = [int(b.split("-")[0]) for b in d["bands"]]
            for md_str in d["dates"]:
                mth, dd = md_str.split("/")
                date = pd.Timestamp(f"{2026 if int(mth) < 10 else 2025}-{mth}-{dd}")
                ser = d["series"][md_str]
                for lo, mean, med in zip(lows, ser["mean"], ser["median"]):
                    erows.append(dict(date=date, level="huc6", huc=huc, band_lo_ft=lo,
                                      ens_mean_af=mean, ens_median_af=med, ens_min_af=np.nan,
                                      ens_max_af=np.nan, min_source=None, max_source=None,
                                      source="WY2026 weekly report (HUC6 bands)"))
        pd.DataFrame(erows).to_parquet(out / "WY2026_elev.parquet", index=False)
        print(f"Wrote {len(erows)} elevation-band rows (HUC6 only) to {out / 'WY2026_elev.parquet'}")


if __name__ == "__main__":
    main(sys.argv[1])
