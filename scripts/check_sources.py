"""
Pre-flight check before the historical backfill.

Downloads a handful of test days from each archive, processes them exactly as
the backfill does, and reports:
  * whether each archive answers and which file was matched,
  * file size, download time and processing time per day,
  * a sanity figure per day (SWE volume over all 80 HUC8s, and the
    Rio Grande Headwaters HUC6),
  * an estimate of total download volume and run time for the full backfill
    (every day, and every 3rd day),
and writes quick-look maps (PNG) of SNODAS just before and after the
2013-10-01 grid change with the HUC8 outlines, for a visual alignment check.

Test files are deleted afterwards. Output: data/logs/check_sources/

Usage:  python scripts/check_sources.py
"""
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config as C                      # noqa: E402
from src import sources, zonal                   # noqa: E402
from src.backfill import season_dates            # noqa: E402
from src.domain import load_domain               # noqa: E402

TEST_DATES = {
    "SNODAS": ["20031001", "20130301", "20131001", "20140301", "20250301"],
    "UA_SWE": ["20031001", "20130301", "20250301"],
}
OUT = C.DATA_DIR / "logs" / "check_sources"


def quicklook(arr, grid, huc8, title, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    t = grid.transform
    ext = [t.c, t.c + t.a * grid.width, t.f + t.e * grid.height, t.f]
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.imshow(np.where(arr > 0, arr, np.nan), extent=ext, cmap="Blues", vmax=np.nanpercentile(arr[arr > 0], 98) if (arr > 0).any() else 1)
    huc8.boundary.plot(ax=ax, color="k", linewidth=0.4)
    ax.set_title(title); ax.set_axis_off()
    fig.savefig(path, dpi=130, bbox_inches="tight"); plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    huc8, huc6 = load_domain()
    grid = zonal.build_grid(huc8, huc6)
    i6 = grid.codes["huc6"].index("130100") if "130100" in grid.codes["huc6"] else None
    n_days = sum(len(list(season_dates(wy))) for wy in range(C.CLIM_START_WY, C.BACKFILL_END_WY + 1))
    print(f"Backfill WY{C.CLIM_START_WY}-WY{C.BACKFILL_END_WY}: {n_days} season days per product "
          f"(Oct 1-Jul 31)\n")
    for product, dates in TEST_DATES.items():
        sizes, t_dl, t_pr = [], [], []
        print(f"== {product} ==")
        for d in dates:
            path = sources.snodas_path(d) if product == "SNODAS" else sources.uaswe_path(d)
            try:
                t0 = time.time()
                if product == "SNODAS":
                    sources.download_snodas(d)
                else:
                    sources.download_uaswe(d)
                t1 = time.time()
                arr = zonal.to_grid(sources.LOADERS[product](d, download=False), grid)
                swe = zonal.apply_threshold(arr)
                st = zonal.stats_all_levels(swe, grid)
                t2 = time.time()
            except Exception as e:                                   # noqa: BLE001
                print(f"  {d}: FAILED - {e}")
                continue
            size = path.stat().st_size / 1e6
            sizes.append(size); t_dl.append(t1 - t0); t_pr.append(t2 - t1)
            tot = st.loc[st.level == "huc8", "volume_af"].sum()
            rgh = st.loc[(st.level == "huc6") & (st.huc == "130100"), "volume_af"].sum() if i6 is not None else np.nan
            print(f"  {d}: ok  file {size:6.1f} MB  download {t1 - t0:5.1f} s  process {t2 - t1:4.1f} s  "
                  f"| 80 HUC8s {tot:12,.0f} af | Rio Grande Headwaters {rgh:10,.0f} af")
            if product == "SNODAS" and d in ("20130301", "20140301"):
                png = OUT / f"snodas_{d}.png"
                quicklook(swe, grid, huc8, f"SNODAS {d} ({'pre' if d < '2013' else 'post'}-2013 grid)", png)
                print(f"      quick-look map: {png}")
            path.unlink(missing_ok=True)
        if sizes:
            gb = np.mean(sizes) * n_days / 1e3
            hrs = (np.mean(t_dl) + np.mean(t_pr)) * n_days / 3600
            print(f"  estimate, every day:     ~{gb:,.0f} GB downloaded (deleted as it goes), ~{hrs:,.1f} h")
            print(f"  estimate, every 3rd day: ~{gb / 3:,.0f} GB, ~{hrs / 3:,.1f} h")
            print("  (winter files are larger than autumn ones; treat as a rough guide)\n")


if __name__ == "__main__":
    main()
