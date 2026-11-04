"""
Download and load SWE products for the statewide pipeline.

Each loader returns an xarray.DataArray on the product's native grid, in
inches, with NaN for no data and the CRS set, ready for zonal.to_grid().

Fixes relative to src/download_data.py (the weekly Rio Grande report keeps
using that module unchanged):
  * HTTP errors raise instead of writing an HTML error page to a .tar file.
  * SNODAS masked-grid georeferencing switches at 2013-10-01 (the pre-2013
    masked grids are offset by half a cell; see the NSIDC G02158 user guide,
    'Masked data' extents -- verify the corner values below against it).
  * The SWE .dat file is found inside the tar by product code rather than a
    hard-coded name, and only files for the requested date are removed.
  * The UA SWE directory listing is cached per water year (backfill speed).
"""
import calendar
import gzip
import re
import tarfile
import tempfile
from datetime import date as _date
from functools import lru_cache
from pathlib import Path

import numpy as np
import requests
import rioxarray as rxr  # noqa: F401  (registers .rio accessor)
import xarray as xr
from rasterio.transform import from_bounds

from src import config as C

SNODAS_URL = "https://noaadata.apps.nsidc.org/NOAA/G02158/masked"
UA_URL = "https://climate.arizona.edu/data/UA_SWE/DailyData_800m"
MM_PER_IN = 25.4
TIMEOUT = 120

# SNODAS masked grid: 6935 x 3351 cells of 30 arc-seconds, big-endian int16, mm
SNODAS_COLS, SNODAS_ROWS = 6935, 3351
SNODAS_BOUNDS_NEW = (-124.73333333333333, 24.95, -66.94166666666667, 52.875)          # >= 2013-10-01
SNODAS_BOUNDS_OLD = (-124.73375, 24.949583333333333, -66.942083333333333, 52.874583333333333)  # < 2013-10-01
SNODAS_SWITCH = _date(2013, 10, 1)


def _to_inches(da, factor, crs=None, default_crs="EPSG:4326"):
    """Mask negatives, convert to inches and (re)write the CRS.

    CF netCDF files (UA SWE) carry their CRS in a grid_mapping variable that is
    referenced from the variable's encoding; arithmetic drops that link, so the
    CRS is captured first and written back explicitly afterwards.
    """
    crs = crs or da.rio.crs or default_crs
    out = (da.where(da >= 0) * factor).astype("float32")
    return out.rio.write_crs(crs)


class DataUnavailable(Exception):
    """Raised when a product has no file for the requested date."""


def _d(date):
    return _date(int(date[:4]), int(date[4:6]), int(date[6:8]))


def water_year(date):
    d = _d(date)
    return d.year + 1 if d.month >= 10 else d.year


# ---------------------------------------------------------------------------
# SNODAS
# ---------------------------------------------------------------------------
def snodas_path(date):
    return C.DATA_DIR / "SNODAS" / f"SNODAS_SWE_{date}.tif"


def download_snodas(date, keep_tif=True):
    """Download masked SNODAS SWE for date (YYYYMMDD) and write a GeoTIFF."""
    out = snodas_path(date)
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    d = _d(date)
    url = f"{SNODAS_URL}/{d.year}/{d.month:02d}_{calendar.month_abbr[d.month]}/SNODAS_{date}.tar"
    r = requests.get(url, timeout=TIMEOUT)
    if r.status_code == 404:
        raise DataUnavailable(f"SNODAS {date}: not in archive ({url})")
    r.raise_for_status()

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        tar_path = tmp / "snodas.tar"
        tar_path.write_bytes(r.content)
        with tarfile.open(tar_path) as tar:
            members = [m for m in tar.getmembers() if "ssmv11034tS" in m.name and m.name.endswith(".dat.gz")]
            if not members:
                raise DataUnavailable(f"SNODAS {date}: SWE file (code 1034) not found in tar")
            tar.extract(members[0], tmp)
            gz = tmp / members[0].name
        raw = gzip.decompress(gz.read_bytes())

    arr = np.frombuffer(raw, dtype=">i2").reshape(SNODAS_ROWS, SNODAS_COLS).astype("int16")
    bounds = SNODAS_BOUNDS_OLD if d < SNODAS_SWITCH else SNODAS_BOUNDS_NEW
    transform = from_bounds(*bounds, SNODAS_COLS, SNODAS_ROWS)
    da = xr.DataArray(arr, dims=("y", "x"))
    da = da.rio.write_transform(transform).rio.write_crs("EPSG:4326").rio.write_nodata(-9999)
    # rioxarray needs coordinates for later reprojection
    da = da.assign_coords(
        x=transform.c + transform.a * (np.arange(SNODAS_COLS) + 0.5),
        y=transform.f + transform.e * (np.arange(SNODAS_ROWS) + 0.5))
    if keep_tif:
        da.rio.to_raster(out, compress="deflate")
        return out
    return da


def load_snodas(date, download=True):
    """SNODAS SWE (inches) on its native geographic grid."""
    path = snodas_path(date)
    if not path.exists():
        if not download:
            raise DataUnavailable(f"SNODAS {date}: {path} missing")
        download_snodas(date)
    # read fully and close the file, so it can be deleted afterwards (Windows locks open files)
    with rxr.open_rasterio(path, masked=True) as src:
        da = src.squeeze("band", drop=True).load()
        crs = src.rio.crs
    return _to_inches(da, 1 / MM_PER_IN, crs)


# ---------------------------------------------------------------------------
# UA SWE (SWANN), 800 m daily
# ---------------------------------------------------------------------------
def uaswe_path(date):
    return C.DATA_DIR / "UA_SWE" / f"UA_SWE_{date}.nc"


@lru_cache(maxsize=64)
def _ua_listing(wy):
    r = requests.get(f"{UA_URL}/WY{wy}/", timeout=TIMEOUT)
    if r.status_code == 404:
        return ()
    r.raise_for_status()
    return tuple(re.findall(r'href="([^"]+\.nc)"', r.text, flags=re.IGNORECASE))


def download_uaswe(date):
    out = uaswe_path(date)
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    wy = water_year(date)
    matches = [f for f in _ua_listing(wy) if date in f]
    if not matches:
        raise DataUnavailable(f"UA SWE {date}: no file in WY{wy} listing")
    r = requests.get(f"{UA_URL}/WY{wy}/{matches[0]}", timeout=TIMEOUT)
    r.raise_for_status()
    out.write_bytes(r.content)
    return out


def load_uaswe(date, download=True):
    """UA SWE (inches) on its native geographic grid."""
    path = uaswe_path(date)
    if not path.exists():
        if not download:
            raise DataUnavailable(f"UA SWE {date}: {path} missing")
        download_uaswe(date)
    # read fully and close the file, so it can be deleted afterwards (Windows locks open files)
    with xr.open_dataset(path, engine="netcdf4", decode_coords="all") as ds:
        da = ds["SWE"].squeeze(drop=True)
        da = da.rename({k: v for k, v in {"lon": "x", "lat": "y"}.items() if k in da.dims})
        da = da.rio.set_spatial_dims(x_dim="x", y_dim="y")
        crs = da.rio.crs
        da = da.load()
    return _to_inches(da, 1 / MM_PER_IN, crs)


# ---------------------------------------------------------------------------
# CU SWE (manual download; western US, metres)
# ---------------------------------------------------------------------------
def cuswe_path(date):
    return C.DATA_DIR / "CU_SWE" / f"{date}_raster.tif"


def load_cuswe(date, download=False):
    path = cuswe_path(date)
    if not path.exists():
        raise DataUnavailable(f"CU SWE {date}: {path} missing (manual download)")
    with rxr.open_rasterio(path, masked=True) as src:
        da = src.squeeze("band", drop=True).load()
        crs = src.rio.crs
    return _to_inches(da, 1000 / MM_PER_IN, crs)     # metres -> inches


LOADERS = {"SNODAS": load_snodas, "UA_SWE": load_uaswe, "CU_SWE": load_cuswe}


def cleanup(product, date):
    """Remove raw files for one date (used by the backfill)."""
    for p in {"SNODAS": [snodas_path(date)], "UA_SWE": [uaswe_path(date)]}.get(product, []):
        p.unlink(missing_ok=True)

