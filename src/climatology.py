"""
Per-product day-of-water-year climatology from the backfilled statistics.

For each product, zone (HUC8/HUC6) and calendar day of the water year, the
basin SWE volume over WY CLIM_START_WY..CLIM_END_WY (None = every completed
year in data/stats/hist) is summarised as the
median, percentiles (C.CLIM_PERCENTILES), min, max and number of years.

Day of water year uses a fixed 365-day calendar (Oct 1 = day 1); Feb 29 is
dropped so the same calendar day lines up across leap and non-leap years.

Output: data/climatology/<PRODUCT>_clim.parquet
Usage:  python -m src.climatology
"""
import numpy as np
import pandas as pd

from src import config as C


def dowy(dates):
    """Day of water year on a 365-day calendar (Oct 1 = 1, Sep 30 = 365); Feb 29 -> NaN."""
    dates = pd.DatetimeIndex(dates)
    ref = pd.to_datetime(dict(year=np.where(dates.month >= 10, 2001, 2002),  # non-leap reference WY
                              month=dates.month, day=np.where((dates.month == 2) & (dates.day == 29), 28, dates.day)))
    d = (ref - pd.Timestamp("2001-10-01")).dt.days.to_numpy() + 1
    return np.where((dates.month == 2) & (dates.day == 29), np.nan, d)


def _fill_days(clim):
    """Linear interpolation of every statistic onto all days between the first
    and last sampled day (needed when the backfill samples every Nth day)."""
    stats = [c for c in clim.columns if c not in ("level", "huc", "dowy")]
    out = []
    for (level, huc), g in clim.groupby(["level", "huc"]):
        g = g.set_index("dowy").reindex(range(int(g.dowy.min()), int(g.dowy.max()) + 1))
        g[stats] = g[stats].interpolate(method="index", limit_area="inside")
        g["n_years"] = g["n_years"].round()
        out.append(g.assign(level=level, huc=huc).rename_axis("dowy").reset_index())
    return pd.concat(out, ignore_index=True)


def build(product, last_wy=None):
    """last_wy: newest water year to include (the rollover passes the year it just
    closed). By default only completed water years are used, so a backfill of the
    current, unfinished year is drawn as the page's current-year line and not
    folded into its own median."""
    files = sorted((C.STATS_DIR / "hist" / product).glob("WY*.parquet"))
    if last_wy is None:
        today = pd.Timestamp.today()
        last_wy = today.year if today.month >= 10 else today.year - 1
    end = min(C.CLIM_END_WY or 9999, last_wy)
    files = [f for f in files if ".partial" not in f.name
             and C.CLIM_START_WY <= int(f.stem[2:6]) <= end]
    if not files:
        raise FileNotFoundError(f"No backfilled statistics for {product}; run src.backfill first")
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    df["dowy"] = dowy(df["date"])
    df = df.dropna(subset=["dowy"])
    df["dowy"] = df["dowy"].astype(int)
    n = C.BACKFILL_EVERY_N_DAYS
    if n > 1:   # every year contributes on the same sampled days
        df = df[(df["dowy"] - 1) % n == 0]

    g = df.groupby(["level", "huc", "dowy"])["volume_af"]
    clim = g.agg(["median", "min", "max", "count"]).rename(columns={"count": "n_years"})
    for p in C.CLIM_PERCENTILES:
        clim[f"p{p}"] = g.quantile(p / 100)
    clim["mean_in_median"] = df.groupby(["level", "huc", "dowy"])["mean_in"].median()
    clim = clim.reset_index()
    clim = _fill_days(clim)
    wys = sorted(int(f.stem[2:6]) for f in files)
    clim.insert(0, "product", product)
    clim["wy_first"], clim["wy_last"], clim["n_wy"] = wys[0], wys[-1], len(wys)

    C.CLIM_DIR.mkdir(parents=True, exist_ok=True)
    out = C.CLIM_DIR / f"{product}_clim.parquet"
    clim.to_parquet(out, index=False)
    print(f"{product}: climatology from {len(files)} water years -> {out}")
    return clim


if __name__ == "__main__":
    for p in C.CLIM_PRODUCTS:
        try:
            build(p)
        except FileNotFoundError as e:
            print(e)
