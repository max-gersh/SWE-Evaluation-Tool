"""
Zonal SWE statistics on a common equal-area grid.

Core ideas
----------
* Every product is resampled (nearest neighbour) onto one EPSG:5070 grid, so
  the per-pixel agreement test compares like with like and the HUC zones are
  rasterized once and reused every day.
* Zones are integer rasters (index into the HUC code list), so statistics for
  all basins come from a few vectorised passes instead of one clip per basin.
* Snow presence: SWE >= SNOW_THRESHOLD_IN. Values below the threshold are set
  to 0 before any statistic is computed, for history and current year alike.
* Agreement mask: pixel kept where >= MIN_AGREEMENT products report snow.
  Inside the mask each product's own value is used, including 0.

Units: SWE in inches in, statistics out in inches / acre-feet / km2.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd
import rasterio.features
from affine import Affine
from rasterio.enums import Resampling

from src import config as C

M3_PER_AF = 1233.48183754752
M_PER_IN = 0.0254
LEVELS = ("huc8", "huc6", "huc12")


# ---------------------------------------------------------------------------
# Grid and zones
# ---------------------------------------------------------------------------
@dataclass
class Grid:
    transform: Affine
    width: int
    height: int
    crs: str
    zones: dict      # level -> int32 array (index into codes, -1 = outside)
    codes: dict      # level -> list of HUC codes

    @property
    def levels(self):
        """Levels with at least one zone, in reporting order."""
        return [lv for lv in LEVELS if lv in self.zones and len(self.codes.get(lv, []))]

    @property
    def pixel_area_m2(self):
        return abs(self.transform.a * self.transform.e)

    @property
    def shape(self):
        return (self.height, self.width)


def build_grid(huc8, huc6, res=C.GRID_RES_M, pad=C.GRID_PAD_M, cache=True, huc12=None):
    """Build the analysis grid covering the domain and rasterize HUC zones.

    huc8/huc6: GeoDataFrames in C.CRS_ANALYSIS with 'HUC8'/'HUC6' columns.
    huc12: optional selected HUC12s ('HUC12' column); None loads them from the
    domain (src.domain.load_huc12), so every caller gets the HUC12 level.
    Zone assignment uses pixel centres (all_touched=False), so adjacent HUCs
    never share a pixel and no pixel is double counted. HUC6 zones are the
    union of their HUC8 zones (HUC6 total = sum of included HUC8s). HUC12
    zones are rasterized on their own and are not part of any HUC8/HUC6 total.
    """
    if huc12 is None:
        from src.domain import load_huc12
        huc12 = load_huc12()
    # the cache is keyed on the domain itself, so editing boundaries never
    # reuses stale zones
    import hashlib
    key = hashlib.sha1("|".join(
        f"{c}:{a:.0f}" for gdf, col in ((huc8, "HUC8"), (huc6, "HUC6"), (huc12, "HUC12"))
        for c, a in zip(gdf[col].astype(str), gdf.geometry.area)).encode()).hexdigest()[:10]
    cache_path = C.DOMAIN_DIR / f"grid_{res}m_{key}.npz"
    if cache:
        for old in C.DOMAIN_DIR.glob(f"grid_{res}m*.npz"):
            if old != cache_path:
                old.unlink()
    if cache and cache_path.exists():
        z = np.load(cache_path, allow_pickle=True)
        lv = [l for l in LEVELS if f"zones_{l}" in z.files]
        return Grid(Affine(*z["transform"]), int(z["width"]), int(z["height"]),
                    str(z["crs"]),
                    {l: z[f"zones_{l}"] for l in lv},
                    {l: [str(c) for c in z[f"codes_{l}"]] for l in lv})

    xmin, ymin, xmax, ymax = huc6.total_bounds
    xmin, ymin = np.floor((xmin - pad) / res) * res, np.floor((ymin - pad) / res) * res
    xmax, ymax = np.ceil((xmax + pad) / res) * res, np.ceil((ymax + pad) / res) * res
    width, height = int((xmax - xmin) / res), int((ymax - ymin) / res)
    transform = Affine(res, 0, xmin, 0, -res, ymax)

    # HUC8 zones from the polygons; HUC6 zones are derived from them so that a
    # HUC6 total is exactly the sum of its included HUC8 totals.
    codes = {"huc8": list(huc8["HUC8"].astype(str)), "huc6": list(huc6["HUC6"].astype(str))}
    z8 = rasterio.features.rasterize(
        ((geom, i) for i, geom in enumerate(huc8.geometry)), out_shape=(height, width),
        transform=transform, fill=-1, dtype="int32", all_touched=False)
    parent = np.array([codes["huc6"].index(c[:6]) for c in codes["huc8"]] + [-1], dtype="int32")
    zones = {"huc8": z8, "huc6": parent[z8]}   # index -1 maps to the trailing -1
    if len(huc12):
        codes["huc12"] = list(huc12["HUC12"].astype(str))
        zones["huc12"] = rasterio.features.rasterize(
            ((geom, i) for i, geom in enumerate(huc12.geometry)), out_shape=(height, width),
            transform=transform, fill=-1, dtype="int32", all_touched=False)

    grid = Grid(transform, width, height, C.CRS_ANALYSIS, zones, codes)
    if cache:
        C.DOMAIN_DIR.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache_path, transform=np.array(transform)[:6],
                            width=width, height=height, crs=C.CRS_ANALYSIS,
                            **{f"zones_{l}": zones[l] for l in zones},
                            **{f"codes_{l}": np.array(codes[l]) for l in zones})
    return grid


def to_grid(da, grid):
    """Resample a georeferenced DataArray (inches, NaN = no data) onto the grid.

    Nearest neighbour: the analysis grid (500 m) is at or finer than every
    product, so no values are averaged across the snow line.
    """
    out = da.rio.reproject(grid.crs, shape=grid.shape, transform=grid.transform,
                           resampling=Resampling.nearest, nodata=np.nan)
    return out.values.astype("float32")


# ---------------------------------------------------------------------------
# Elevation bands
# ---------------------------------------------------------------------------
def build_bands(grid, dem_path=None, band_ft=None, cache=True):
    """Elevation-band index for every grid pixel (-1 = no DEM).

    band index b covers [b*band_ft, (b+1)*band_ft) feet. The DEM is averaged
    onto the 500 m grid, so each pixel's band is its mean elevation.
    """
    import hashlib
    import rioxarray as rxr
    dem_path = dem_path or C.DEM_PATH
    band_ft = band_ft or C.ELEV_BAND_FT
    st = dem_path.stat()
    key = hashlib.sha1(f"{dem_path}|{st.st_size}|{st.st_mtime}|{grid.shape}|{grid.transform}|"
                       f"{band_ft}|{C.DEM_UNITS}".encode()).hexdigest()[:10]
    cache_path = C.DOMAIN_DIR / f"bands_{key}.npz"
    if cache and cache_path.exists():
        return np.load(cache_path)["bands"]
    dem = rxr.open_rasterio(dem_path, masked=True).squeeze("band", drop=True)
    g = dem.rio.reproject(grid.crs, shape=grid.shape, transform=grid.transform,
                          resampling=Resampling.average, nodata=np.nan).values.astype("float64")
    if C.DEM_UNITS == "m":
        g = g * 3.28084
    bands = np.where(np.isnan(g) | (g < -1000), -1, np.floor(np.maximum(g, 0) / band_ft)).astype("int32")
    if cache:
        for old in C.DOMAIN_DIR.glob("bands_*.npz"):
            old.unlink()
        np.savez_compressed(cache_path, bands=bands)
    return bands


def dem_coverage(grid, bands):
    """Share of domain pixels (in any HUC8) that have a DEM value."""
    inside = grid.zones["huc8"] >= 0
    return float((bands[inside] >= 0).mean())


def elev_stats(swe, grid, bands, band_ft=None):
    """Volume per (zone, elevation band) for one SWE field (inches, thresholded).

    Every band that holds at least one pixel of the zone is listed (volume 0
    where there is no snow), so the chart shows the basin's full elevation range.
    """
    band_ft = band_ft or C.ELEV_BAND_FT
    K = int(bands.max()) + 1
    px = grid.pixel_area_m2
    frames = []
    for level in grid.levels:
        z = grid.zones[level]
        ok = (z >= 0) & (bands >= 0)
        key = (z[ok].astype("int64") * K + bands[ok])
        v = swe[ok]
        valid = ~np.isnan(v)
        n = len(grid.codes[level]) * K
        cnt = np.bincount(key, minlength=n)
        tot = np.bincount(key[valid], weights=v[valid], minlength=n)
        idx = np.nonzero(cnt)[0]
        frames.append(pd.DataFrame({
            "level": level, "huc": np.asarray(grid.codes[level])[idx // K],
            "band_lo_ft": (idx % K) * band_ft,
            "volume_af": tot[idx] * M_PER_IN * px / M3_PER_AF,
            "band_area_km2": cnt[idx] * px / 1e6}))
    return pd.concat(frames, ignore_index=True)


def elev_ensemble(grids, grid, bands, mask, date):
    """Per-product masked volume by elevation band, and their ensemble."""
    rows = []
    for product, arr in grids.items():
        swe = apply_threshold(arr)
        swe = np.where(mask, swe, np.where(np.isnan(swe), np.nan, 0.0)).astype("float32")
        df = elev_stats(swe, grid, bands)
        df["product"] = product
        rows.append(df)
    long = pd.concat(rows, ignore_index=True)
    area = long.groupby(["level", "huc", "band_lo_ft"])["band_area_km2"].first()
    wide = long.pivot_table(index=["level", "huc", "band_lo_ft"], columns="product",
                            values="volume_af", aggfunc="first")
    ens = ensemble_from_wide(wide)
    ens = pd.concat([wide.add_prefix("vol_"), ens], axis=1)
    ens["band_area_km2"] = area
    ens = ens.reset_index()
    ens.insert(0, "date", pd.Timestamp(date))
    return ens


# ---------------------------------------------------------------------------
# Masks
# ---------------------------------------------------------------------------
def apply_threshold(swe, thr=C.SNOW_THRESHOLD_IN):
    """Set trace SWE (< thr) to 0; keep NaN (no data) as NaN."""
    return np.where(np.isnan(swe), np.nan, np.where(swe >= thr, swe, 0.0)).astype("float32")


def agreement_count(grids, thr=C.SNOW_THRESHOLD_IN):
    """Number of products reporting snow (SWE >= thr) in each pixel."""
    count = np.zeros(next(iter(grids.values())).shape, dtype="int8")
    for arr in grids.values():
        count += (np.nan_to_num(arr, nan=0.0) >= thr).astype("int8")
    return count


# ---------------------------------------------------------------------------
# Zonal statistics
# ---------------------------------------------------------------------------
def zonal_stats(swe, zones, codes, pixel_area_m2, snow_thr=C.SNOW_THRESHOLD_IN):
    """Statistics of one SWE field (inches, thresholded) for every zone.

    mean_in / median_in: over all valid pixels in the zone (zeros included)
    volume_af          : sum(SWE) * pixel area
    snow_area_km2      : area with SWE >= threshold
    valid_area_km2     : area with data (excludes open-water / no-data pixels)
    """
    z = zones.ravel()
    v = swe.ravel()
    inside = z >= 0
    z, v = z[inside], v[inside]
    valid = ~np.isnan(v)
    n = len(codes)

    cnt = np.bincount(z[valid], minlength=n).astype(float)
    tot = np.bincount(z[valid], weights=v[valid], minlength=n)
    snow = np.bincount(z[valid], weights=(v[valid] >= snow_thr), minlength=n)

    px_km2 = pixel_area_m2 / 1e6
    with np.errstate(invalid="ignore", divide="ignore"):
        mean_in = np.where(cnt > 0, tot / cnt, np.nan)
    median_in = (pd.Series(v[valid]).groupby(z[valid]).median()
                 .reindex(range(n)).to_numpy())
    volume_af = tot * M_PER_IN * pixel_area_m2 / M3_PER_AF

    return pd.DataFrame({
        "huc": codes, "mean_in": mean_in, "median_in": median_in,
        "volume_af": volume_af, "snow_area_km2": snow * px_km2,
        "valid_area_km2": cnt * px_km2,
    })


def stats_all_levels(swe, grid):
    frames = []
    for level in grid.levels:
        df = zonal_stats(swe, grid.zones[level], grid.codes[level], grid.pixel_area_m2)
        df.insert(0, "level", level)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def product_stats(grids, grid, date, masked=False, mask=None):
    """Long table of per-product statistics (unmasked or inside the agreement mask)."""
    rows = []
    for product, arr in grids.items():
        swe = apply_threshold(arr)
        if masked:
            # outside the agreement mask SWE is not counted (0); no-data stays NaN
            swe = np.where(mask, swe, np.where(np.isnan(swe), np.nan, 0.0)).astype("float32")
        df = stats_all_levels(swe, grid)
        df.insert(0, "product", product)
        rows.append(df)
    out = pd.concat(rows, ignore_index=True)
    out.insert(0, "masked", masked)
    out.insert(0, "date", pd.Timestamp(date))
    return out


def ensemble_from_wide(wide):
    """Ensemble mean/median/min/max (+ min/max source) across product columns."""
    products = list(wide.columns)
    vals = wide.to_numpy(dtype=float)
    with np.errstate(all="ignore"), __import__("warnings").catch_warnings():
        __import__("warnings").simplefilter("ignore", RuntimeWarning)
        ens = pd.DataFrame({
            "ens_mean_af": np.nanmean(vals, axis=1),
            "ens_median_af": np.nanmedian(vals, axis=1),
            "ens_min_af": np.nanmin(vals, axis=1),
            "ens_max_af": np.nanmax(vals, axis=1),
            "n_products": np.sum(~np.isnan(vals), axis=1),
        }, index=wide.index)

    def _src(row_vals, target):
        return ", ".join(p for p, x in zip(products, row_vals)
                         if not np.isnan(x) and np.isclose(x, target, rtol=1e-6, atol=0.5))
    ens["min_source"] = [_src(r, t) for r, t in zip(vals, ens["ens_min_af"])]
    ens["max_source"] = [_src(r, t) for r, t in zip(vals, ens["ens_max_af"])]
    return ens


def ensemble_stats(masked_stats, grid, mask, date):
    """Ensemble of per-product basin volumes inside the agreement mask."""
    px_km2 = grid.pixel_area_m2 / 1e6
    agree_area = pd.concat([
        pd.DataFrame({"level": level, "huc": grid.codes[level],
                      "agree_area_km2": np.bincount(
                          grid.zones[level][mask & (grid.zones[level] >= 0)],
                          minlength=len(grid.codes[level])) * px_km2})
        for level in grid.levels], ignore_index=True)

    wide = masked_stats.pivot_table(index=["level", "huc"], columns="product",
                                    values="volume_af", aggfunc="first")
    ens = ensemble_from_wide(wide)
    ens = ens.reset_index().merge(agree_area, on=["level", "huc"], how="left")
    ens["reported"] = ens["agree_area_km2"] >= C.MIN_REPORT_AREA_KM2
    ens.insert(0, "date", pd.Timestamp(date))
    return ens


def daily_stats(grids, grid, date, bands=None):
    """All statistics for one date.

    grids: dict product -> 2-D array on `grid` (inches, NaN = no data).
    bands: optional elevation-band array from build_bands().
    Returns (product_table, ensemble_table, elevation_table or None, agreement_count).
    """
    count = agreement_count(grids)
    mask = count >= C.MIN_AGREEMENT
    unmasked = product_stats(grids, grid, date, masked=False)
    masked = product_stats(grids, grid, date, masked=True, mask=mask)
    ens = ensemble_stats(masked, grid, mask, date)
    elev = elev_ensemble(grids, grid, bands, mask, date) if bands is not None else None
    return pd.concat([unmasked, masked], ignore_index=True), ens, elev, count
