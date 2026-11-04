"""Backfill loop + climatology on a mocked loader (3 water years x a few days)."""
import sys
from pathlib import Path
from unittest import mock
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config as C, backfill, climatology, sources

# calendar checks
d = climatology.dowy(pd.to_datetime(["2023-10-01", "2024-09-30", "2024-02-28", "2024-02-29", "2024-03-01", "2023-03-01"]))
print("dowy:", d)
assert d[0] == 1 and d[1] == 365 and np.isnan(d[3]) and d[4] == d[5] == d[2] + 1

snodas_da = sources.load_snodas("20990115", download=False)   # synthetic 10 in field from test_synthetic
def fake_loader(date):
    if date.endswith("0103"):
        raise sources.DataUnavailable(f"SNODAS {date}: not in archive")
    scale = int(date[:4]) - 2003           # WY-dependent: 1x, 2x, 3x
    return snodas_da * scale

with mock.patch.object(C, "STATS_DIR", C.DATA_DIR / "stats_test"), \
     mock.patch.object(C, "CLIM_DIR", C.DATA_DIR / "clim_test"), \
     mock.patch.object(C, "SEASON_START", (1, 1)), mock.patch.object(C, "SEASON_END", (1, 4)), \
     mock.patch.object(C, "CLIM_END_WY", 2006), \
     mock.patch.dict(sources.LOADERS, {"SNODAS": fake_loader}), \
     mock.patch("src.sources.cleanup"):
    # season Jan 1-4 of calendar year wy-1 -> dates 2003-01..2005-01, scales 0,1,2 -> use wy 2005..2007
    backfill.backfill("SNODAS", 2004, 2006)
    backfill.backfill("SNODAS", 2004, 2006)   # resume: everything skipped
    clim = climatology.build("SNODAS")
row = clim[(clim.huc == "13060003") & (clim.level == "huc8")].iloc[0]
print(row[["dowy", "median", "p10", "p90", "min", "max", "n_years"]].to_dict())
assert row["n_years"] == 3 and np.isclose(row["median"], (row["min"] + row["max"]) / 2)
print("BACKFILL/CLIMATOLOGY CHECKS PASSED")
