"""
Daily statewide run: all available products -> agreement mask -> statistics.

Appends to data/stats/current/WY<yyyy>_products.parquet (per product, masked
and unmasked), WY<yyyy>_ensemble.parquet and WY<yyyy>_elev.parquet (ensemble
by 1000-ft elevation band, needs C.DEM_PATH), replacing any rows already
present for the date, and writes the agreement-count and ensemble-mean
rasters to data/rasters/<date>/ for later map overlays.

Usage:  python -m src.run_daily 20260315
"""
import sys
import warnings

import numpy as np
import pandas as pd
import rioxarray  # noqa: F401
import xarray as xr

from src import config as C
from src import sources, zonal
from src.domain import load_domain


def _append(path, df, date):
    if path.exists():
        old = pd.read_parquet(path)
        df = pd.concat([old[old["date"] != pd.Timestamp(date)], df], ignore_index=True)
    df.sort_values(["date"], kind="stable").to_parquet(path, index=False)


def _write_raster(arr, grid, path, dtype):
    da = xr.DataArray(arr.astype(dtype), dims=("y", "x"))
    da = da.rio.write_transform(grid.transform).rio.write_crs(grid.crs)
    path.parent.mkdir(parents=True, exist_ok=True)
    da.rio.to_raster(path, compress="deflate", tiled=True)


def run(date):
    huc8, huc6 = load_domain()
    grid = zonal.build_grid(huc8, huc6)

    grids = {}
    for product in C.PRODUCTS:
        try:
            grids[product] = zonal.to_grid(sources.LOADERS[product](date), grid)
        except sources.DataUnavailable as e:
            warnings.warn(str(e))
    if len(grids) < C.MIN_AGREEMENT:
        raise RuntimeError(f"{date}: only {list(grids)} available; need {C.MIN_AGREEMENT} for the ensemble")

    bands = None
    if C.DEM_PATH.exists():
        bands = zonal.build_bands(grid)
        cov = zonal.dem_coverage(grid, bands)
        if cov < 0.99:
            warnings.warn(f"DEM covers {cov:.0%} of the domain; elevation bands omit the rest. "
                          "Use a statewide DEM (C.DEM_PATH).")
    else:
        warnings.warn(f"No DEM at {C.DEM_PATH}; elevation-band statistics skipped.")

    prod, ens, elev, count = zonal.daily_stats(grids, grid, date, bands)

    wy = sources.water_year(date)
    out = C.STATS_DIR / "current"
    out.mkdir(parents=True, exist_ok=True)
    _append(out / f"WY{wy}_products.parquet", prod, date)
    _append(out / f"WY{wy}_ensemble.parquet", ens, date)
    if elev is not None:
        _append(out / f"WY{wy}_elev.parquet", elev, date)

    # rasters: agreement count and ensemble mean SWE inside the mask
    mask = count >= C.MIN_AGREEMENT
    stack = np.stack([zonal.apply_threshold(a) for a in grids.values()])
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        ens_swe = np.where(mask, np.nanmean(stack, axis=0), np.nan)
    rdir = C.DATA_DIR / "rasters" / date
    _write_raster(count, grid, rdir / "agreement_count.tif", "int8")
    _write_raster(ens_swe, grid, rdir / "ensemble_mean_in.tif", "float32")

    n_rep = int(ens.loc[ens.level == "huc8", "reported"].sum())
    n12 = len(grid.codes.get("huc12", []))
    n12_rep = int(ens.loc[ens.level == "huc12", "reported"].sum())
    print(f"{date}: products {list(grids)}; {n_rep} HUC8s reported"
          + (f", {n12_rep} of {n12} HUC12s" if n12 else ""))
    return prod, ens, elev


if __name__ == "__main__":
    run(sys.argv[1])
