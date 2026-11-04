"""
Download a USGS 3DEP DEM covering the full SWEET domain (all 80 HUC8s) and
write it in feet for the elevation bands.

Source: USGS 3DEP Elevation ImageServer (The National Map), exportImage,
        values in metres, requested directly in EPSG:5070 (the SWEET grid CRS)
Output: data/dem_3dep_ft.tif  (EPSG:5070, int16 feet, nodata -32768)

The domain extent is taken from data/domain/domain.gpkg (run src.domain
first). The DEM is fetched in tiles (<= 8000 px per side is the service
limit; 2000 px tiles are used) and tiles are cached in data/dem_tiles/, so an
interrupted run resumes. Tiles that do not touch the domain are skipped.

Resolution: 100 m by default. src.zonal.build_bands averages the DEM onto
the 500 m analysis grid, so 100 m gives 25 samples per grid cell.

If an older DEM exists at data/dem.tif, the script reports the elevation
difference where the two overlap (a unit/datum sanity check).

Usage:  python scripts/fetch_3dep_dem.py [--res 100]
Then set DEM_PATH = DATA_DIR / "dem_3dep_ft.tif" in src/config.py (default).
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
import requests
from rasterio.transform import from_origin
from rasterio.windows import Window
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config as C                      # noqa: E402
from src.domain import load_domain               # noqa: E402

URL = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"
TILE_PX = 2000
FT_PER_M = 3.28084
NODATA = -32768


def fetch_tile(bbox, px, path, retries=4):
    params = dict(bbox=",".join(f"{v:.1f}" for v in bbox), bboxSR=5070, imageSR=5070,
                  size=f"{px},{px}", format="tiff", pixelType="F32", noData=-9999,
                  interpolation="RSP_BilinearInterpolation", f="image")
    for k in range(retries):
        try:
            r = requests.get(URL, params=params, timeout=300)
            r.raise_for_status()
            if not r.content[:4] in (b"II*\x00", b"MM\x00*"):
                raise ValueError(f"not a GeoTIFF: {r.content[:200]!r}")
            path.write_bytes(r.content)
            return
        except Exception as e:  # noqa: BLE001
            if k == retries - 1:
                raise
            print(f"  retry {k + 1} for {path.name}: {e}")
            time.sleep(10 * (k + 1))


def main(res):
    huc8, huc6 = load_domain()
    dom = huc8.geometry.union_all().buffer(5000)
    xmin, ymin, xmax, ymax = huc6.total_bounds
    pad = C.GRID_PAD_M
    xmin, ymin = np.floor((xmin - pad) / res) * res, np.floor((ymin - pad) / res) * res
    xmax, ymax = np.ceil((xmax + pad) / res) * res, np.ceil((ymax + pad) / res) * res
    W, H = int((xmax - xmin) / res), int((ymax - ymin) / res)
    tile_m = TILE_PX * res
    tiles_dir = C.DATA_DIR / "dem_tiles"
    tiles_dir.mkdir(parents=True, exist_ok=True)
    out = C.DATA_DIR / "dem_3dep_ft.tif"
    profile = dict(driver="GTiff", width=W, height=H, count=1, dtype="int16", nodata=NODATA,
                   crs="EPSG:5070", transform=from_origin(xmin, ymax, res, res),
                   compress="deflate", predictor=2, tiled=True, blockxsize=512, blockysize=512,
                   BIGTIFF="IF_SAFER")
    nx, ny = int(np.ceil(W / TILE_PX)), int(np.ceil(H / TILE_PX))
    print(f"DEM grid {W} x {H} px at {res} m; {nx * ny} tiles of {TILE_PX} px")
    with rasterio.open(out, "w", **profile) as dst:
        n = 0
        for ty in range(ny):
            for tx in range(nx):
                x0, y1 = xmin + tx * tile_m, ymax - ty * tile_m
                bbox = (x0, y1 - tile_m, x0 + tile_m, y1)
                if not dom.intersects(box(*bbox)):
                    continue
                tpath = tiles_dir / f"t_{res}m_{ty:02d}_{tx:02d}.tif"
                if not tpath.exists():
                    fetch_tile(bbox, TILE_PX, tpath)
                with rasterio.open(tpath) as src:
                    z = src.read(1).astype("float64")
                    nd = src.nodata
                bad = ~np.isfinite(z) | (z < -500) | (z > 9000) | ((nd is not None) & (z == nd))
                ft = np.where(bad, NODATA, np.round(z * FT_PER_M)).astype("int16")
                w = min(TILE_PX, W - tx * TILE_PX)
                h = min(TILE_PX, H - ty * TILE_PX)
                dst.write(ft[:h, :w], 1, window=Window(tx * TILE_PX, ty * TILE_PX, w, h))
                n += 1
                print(f"  tile {ty},{tx} written ({n})")
    print(f"Wrote {out}")
    compare(out)


def compare(new_path, old_path=None):
    """Elevation difference vs an existing DEM where both cover (sanity check)."""
    old_path = old_path or C.DATA_DIR / "dem.tif"
    if not Path(old_path).exists():
        return
    import rioxarray as rxr
    from rasterio.enums import Resampling
    new = rxr.open_rasterio(new_path, masked=True).squeeze("band", drop=True)
    old = rxr.open_rasterio(old_path, masked=True).squeeze("band", drop=True)
    new_c = new.rio.reproject(new.rio.crs, resolution=1000, resampling=Resampling.average)
    old_on_new = old.rio.reproject_match(new_c, resampling=Resampling.average)
    d = (new_c - old_on_new).values
    d = d[np.isfinite(d)]
    if d.size:
        print(f"vs {Path(old_path).name} ({C.DEM_UNITS}): median diff {np.median(d):+.0f} ft, "
              f"95th pct |diff| {np.percentile(np.abs(d), 95):.0f} ft over {d.size} km2 "
              "(large values suggest a unit mismatch)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", type=float, default=100.0, help="DEM resolution in metres (default 100)")
    main(ap.parse_args().res)
