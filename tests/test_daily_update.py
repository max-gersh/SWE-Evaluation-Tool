"""
Daily-update cycle on mocked products, in a temporary data/web folder.

Fake 'today' = 2099-01-15 (look-back 5 days: Jan 10-14).
  SNODAS for Jan 12 is 'not posted yet' on the first run, then appears.
  CU SWE exists only for Jan 13 (other days are 2-product ensembles).
Checks: catch-up, retry, raw-file cleanup (kept for a report date), page
rebuild + publish, 2-product marking, rollover into history + climatology,
and every-Nth-day backfill sampling with interpolated climatology.
"""
import json, re, shutil, sys, tempfile
from datetime import date
from pathlib import Path
from unittest import mock

import numpy as np, pandas as pd, xarray as xr, rioxarray  # noqa
from rasterio.transform import from_bounds

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config as C, sources, daily_update, backfill, climatology   # noqa: E402
import scripts.rollover_wy as rollover                                      # noqa: E402

class FakeDate(date):
    @classmethod
    def today(cls): return date(2099, 1, 15)

def field(inches):
    tr = from_bounds(-113, 30, -99, 39, 700, 450)
    da = xr.DataArray(np.full((450, 700), inches, "float32"), dims=("y", "x"))
    return da.rio.write_transform(tr).rio.write_crs("EPSG:4326").assign_coords(
        x=tr.c + tr.a * (np.arange(700) + .5), y=tr.f + tr.e * (np.arange(450) + .5))

posted = {"20990112": False}
def snodas(d):
    if not posted.get(d, True): raise sources.DataUnavailable(f"SNODAS {d}: not posted")
    sources.snodas_path(d).parent.mkdir(parents=True, exist_ok=True); sources.snodas_path(d).write_bytes(b"x")
    return field(10.0)
def uaswe(d):
    sources.uaswe_path(d).parent.mkdir(parents=True, exist_ok=True); sources.uaswe_path(d).write_bytes(b"x")
    return field(8.0)
def cuswe(d):
    if d != "20990113": raise sources.DataUnavailable(f"CU SWE {d}: missing")
    return field(12.0)

def main():
    tmp = Path(tempfile.mkdtemp())
    web = tmp / "web"; shutil.copytree(C.WEB_DIR / "vendor", web / "vendor")
    shutil.copy(C.WEB_DIR / "template.html", web / "template.html")
    (tmp / "reports" / "2099-01-14").mkdir(parents=True)             # a weekly report date
    patches = [mock.patch.object(daily_update, "date", FakeDate),
               mock.patch.object(C, "STATS_DIR", tmp / "stats"), mock.patch.object(C, "CLIM_DIR", tmp / "clim"),
               mock.patch.object(C, "WEB_DIR", web), mock.patch.object(C, "PUBLISH_DIR", tmp / "published"),
               mock.patch.object(C, "DATA_DIR", tmp / "data"), mock.patch.object(C, "BASE_DIR", tmp),
               mock.patch.object(C, "DEM_PATH", tmp / "no_dem.tif"), mock.patch.object(C, "LOOKBACK_DAYS", 5),
               mock.patch.object(daily_update, "LOG", tmp / "daily_update.log"),
               mock.patch.dict(sources.LOADERS, {"SNODAS": snodas, "UA_SWE": uaswe, "CU_SWE": cuswe})]
    for p in patches: p.start()
    try:
        n1 = daily_update.update()
        print("run 1 processed", n1, "| pending after:", daily_update.pending_dates())
        assert n1 == 4 and daily_update.pending_dates() == ["20990112"]
        posted["20990112"] = True
        n2 = daily_update.update()
        print("run 2 processed", n2, "| pending after:", daily_update.pending_dates())
        assert n2 == 1 and daily_update.pending_dates() == []

        raw = sorted(p.name for p in (tmp / "data").rglob("*_2099011*") if p.is_file())
        print("raw files left:", raw)
        assert all("20990114" in r for r in raw) and len(raw) == 2    # only the report date kept

        html = (tmp / "published" / "sweet_explorer_offline.html").read_text(encoding="utf-8")
        d = json.loads(re.search(r'id="sweet-data" type="application/json">(.*?)</script>', html, re.S).group(1))
        print("page dates:", d["meta"]["dates"], "| products per date:", [len(p) for p in d["meta"]["dateProducts"]])
        assert d["meta"]["dates"] == [f"2099-01-{k}" for k in range(10, 15)]
        assert [len(p) for p in d["meta"]["dateProducts"]] == [2, 2, 2, 3, 2]
        e = pd.read_parquet(tmp / "stats/current/WY2099_ensemble.parquet")
        v = e[(e.huc == "13060003") & (e.level == "huc8")].set_index("date").ens_mean_af
        print("13060003 ensemble mean: 2-product day %.0f af, 3-product day %.0f af (ratio %.3f, expected 1.111)"
              % (v["2099-01-10"], v["2099-01-13"], v["2099-01-13"] / v["2099-01-10"]))
        assert abs(v["2099-01-13"] / v["2099-01-10"] - 10 / 9) < 1e-3   # mean(10,8,12) / mean(10,8)

        done = rollover.rollover(2099, min_days=3)
        cl = pd.read_parquet(tmp / "clim/SNODAS_clim.parquet")
        print("rollover:", done, "| climatology WYs:", cl.wy_first.iloc[0], "-", cl.wy_last.iloc[0])
        assert done == ["SNODAS", "UA_SWE"] and cl.wy_last.iloc[0] == 2099
    finally:
        for p in patches: p.stop()
        shutil.rmtree(tmp, ignore_errors=True)

    # every-Nth-day backfill sampling + interpolation onto every day
    ds = list(backfill.season_dates(2005, every=3))
    k = climatology.dowy(pd.to_datetime(ds))
    assert set(np.diff(k[~np.isnan(k)])) == {3.0}
    df = pd.DataFrame({"level": "huc8", "huc": "x", "dowy": [1, 4, 7], "median": [0., 30., 60.], "n_years": [3, 3, 3]})
    f = climatology._fill_days(df)
    print("every-3rd-day sampling: first dowy", k[:4], "| interpolated median days 1-7:", f["median"].tolist())
    assert f["median"].tolist() == [0, 10, 20, 30, 40, 50, 60]
    print("ALL DAILY-UPDATE CHECKS PASSED")

if __name__ == "__main__":
    main()
