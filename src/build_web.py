"""
Build the self-contained SWEET basin explorer page.

Inputs
    data/domain/domain.gpkg                      HUC6/HUC8/HUC12 polygons (src.domain)
    data/stats/current/WY<yyyy>_products.parquet per-product basin statistics
    data/stats/current/WY<yyyy>_ensemble.parquet ensemble statistics
    data/climatology/<PRODUCT>_clim.parquet      optional; per-product history
    state boundaries shapefile (C.STATES_SHP)    NM outline + neighbours

Output
    web/sweet_explorer.html          template + inlined JSON; libraries from jsDelivr
    web/sweet_explorer_offline.html  with --offline: libraries inlined from
                                     web/vendor/, no network needed

The page only reads the embedded JSON, so it can be hosted as a static file
(e.g. on drought.nm.gov) and regenerated after each daily run.

Usage: python -m src.build_web --wy 2026 [--offline]
"""
import argparse
import json
from datetime import datetime

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from src import config as C
from src.climatology import dowy
from src.domain import load_domain, load_huc6_full, load_huc12

SIMPLIFY_M = 400          # coverage simplification tolerance (m), topology-safe
SIMPLIFY_M_HUC12 = 100    # finer for the small HUC12s (tens to a few hundred km2)
COORD_DECIMALS = 4
STATES_SHP = C.SHP_DIR / "cb_2018_us_state_20m" / "cb_2018_us_state_20m.shp"
NEIGHBOURS = ["Arizona", "Colorado", "Utah", "Texas", "Oklahoma", "Kansas"]
CITIES = [  # (name, lat, lon) reference points on the map
    ("Albuquerque", 35.0844, -106.6504), ("Santa Fe", 35.6870, -105.9378),
    ("Las Cruces", 32.3199, -106.7637), ("Farmington", 36.7281, -108.2187),
    ("Roswell", 33.3943, -104.5230), ("Taos", 36.4072, -105.5731),
    ("Gallup", 35.5281, -108.7426), ("Silver City", 32.7701, -108.2803),
]


def _simplify(geoms, tol=SIMPLIFY_M):
    """Simplify basin outlines for the web page.

    GEOS >= 3.12: coverage simplification, which keeps shared borders identical.
    Older GEOS (e.g. some conda builds): per-polygon topology-preserving
    simplification at a smaller tolerance, so neighbouring outlines still meet
    within a few tens of metres, well below what the page can show.
    """
    if shapely.geos_version >= (3, 12, 0):
        return shapely.coverage_simplify(geoms, tol)
    return shapely.simplify(geoms, tol / 4, preserve_topology=True)


def _round_geojson(gdf, props):
    gdf = gdf.to_crs(4326)
    gdf["geometry"] = shapely.set_precision(gdf.geometry.values, 10 ** -COORD_DECIMALS)
    fc = json.loads(gdf[props + ["geometry"]].to_json(drop_id=True))
    return fc


def _geometry():
    huc8, huc6 = load_domain()
    out = {}
    for level, gdf, code in (("huc8", huc8, "HUC8"), ("huc6", huc6, "HUC6")):
        g = gdf.copy()
        g["geometry"] = _simplify(g.geometry.values)
        g = g.rename(columns={code: "huc"})
        out[level] = _round_geojson(g, ["huc"])
    huc12 = load_huc12()
    if len(huc12):
        g = huc12.copy()
        g["geometry"] = _simplify(g.geometry.values, SIMPLIFY_M_HUC12)
        out["huc12"] = _round_geojson(g.rename(columns={"HUC12": "huc"}), ["huc"])
    full = load_huc6_full()
    if len(full):
        full["geometry"] = shapely.simplify(full.geometry.values, SIMPLIFY_M)
    out["huc6full"] = _round_geojson(full.rename(columns={"HUC6": "huc"}), ["huc"]) if len(full) \
        else {"type": "FeatureCollection", "features": []}
    states = gpd.read_file(STATES_SHP)
    out["nm"] = _round_geojson(states[states["NAME"] == "New Mexico"].assign(n="NM"), ["n"])
    out["nb"] = _round_geojson(states[states["NAME"].isin(NEIGHBOURS)].rename(columns={"STUSPS": "n"}), ["n"])
    basins = {}
    for _, r in huc6.iterrows():
        b = dict(n=r.Name, l="huc6", a=round(r.area_km2, 1), s=r.States, n8=int(r.n_huc8))
        if r.partial:
            ex = [e.split(":", 1) for e in (r.excluded_huc8 or "").split(";") if e]
            b.update(part=True, fa=round(r.full_area_km2, 1), ex=ex,
                     exAll=bool(r.excluded_listed_km2 >= 0.99 * (r.full_area_km2 - r.area_km2)))
        basins[r.HUC6] = b
    for _, r in huc8.iterrows():
        basins[r.HUC8] = dict(n=r.Name, l="huc8", p=r.HUC6, a=round(r.area_km2, 1), s=r.States,
                              o=r["OSE Grouping"] if isinstance(r["OSE Grouping"], str) else None)
    for _, r in huc12.iterrows():
        basins[r.HUC12] = dict(n=r.Name, l="huc12", p=r.HUC8, p6=r.HUC6,
                               a=round(r.area_km2, 1), s=r.States if isinstance(r.States, str) and r.States else None)
    # HUC8s with statistics but no polygon (missing from the WBD extract)
    for code in C.EXTRA_HUC8:
        basins.setdefault(code, dict(n=C.EXTRA_HUC8[code], l="huc8", p=code[:6], a=None, s=None,
                                     o=C.OSE_GROUPING.get(code), nogeom=True))
    return out, basins


def _nan_list(a, nd=0):
    return [None if (x is None or (isinstance(x, float) and np.isnan(x))) else round(float(x), nd) for x in a]


def _series(wy):
    cur = C.STATS_DIR / "current"
    prod = pd.read_parquet(cur / f"WY{wy}_products.parquet")
    ens = pd.read_parquet(cur / f"WY{wy}_ensemble.parquet")
    dates = sorted(ens["date"].unique())
    idx = pd.DatetimeIndex(dates)
    series = {}
    for huc, g in ens.groupby("huc"):
        g = g.set_index("date").reindex(idx)
        s = {"ens": {k: _nan_list(g[f"ens_{k}_af"]) for k in ("mean", "median", "min", "max")}}
        s["ens"]["minsrc"] = [x if isinstance(x, str) else None for x in g["min_source"]]
        s["ens"]["maxsrc"] = [x if isinstance(x, str) else None for x in g["max_source"]]
        s["ens"]["rep"] = [bool(x) if pd.notna(x) else False for x in g["reported"]]
        if "agree_area_km2" in g:
            s["ens"]["agree"] = _nan_list(g["agree_area_km2"], 1)
        series[huc] = s
    for (huc, masked), g in prod.groupby(["huc", "masked"]):
        w = g.pivot_table(index="date", columns="product", values="volume_af", aggfunc="first").reindex(idx)
        key = "pm" if masked else "p"
        series.setdefault(huc, {})[key] = {p: _nan_list(w[p]) for p in w.columns}
    source = prod["source"].dropna().iloc[0] if "source" in prod and prod["source"].notna().any() \
        else "SWEET daily statewide run"
    # products that contributed on each date (a date without CU SWE is a 2-product ensemble)
    avail = (prod[~prod["masked"]].dropna(subset=["volume_af"]).groupby("date")["product"]
             .agg(lambda x: sorted(set(x))).reindex(idx))
    date_products = [p if isinstance(p, list) else [] for p in avail]
    return [pd.Timestamp(d).strftime("%Y-%m-%d") for d in dates], series, source, date_products


def _elev(wy, dates):
    """Ensemble volume by elevation band, per basin, aligned with the page dates."""
    f = C.STATS_DIR / "current" / f"WY{wy}_elev.parquet"
    if not f.exists():
        return {}
    df = pd.read_parquet(f)
    df["d"] = df["date"].dt.strftime("%Y-%m-%d")
    di = {d: i for i, d in enumerate(dates)}
    df = df[df["d"].isin(di)]
    out = {}
    for huc, g in df.groupby("huc"):
        bands = sorted(int(b) for b in g["band_lo_ft"].unique())
        bi = {b: j for j, b in enumerate(bands)}
        nd, nb = len(dates), len(bands)
        arr = {k: [[None] * nb for _ in range(nd)] for k in ("m", "lo", "hi", "ls", "hs")}
        for r in g.itertuples():
            i, j = di[r.d], bi[int(r.band_lo_ft)]
            for k, col in (("m", "ens_mean_af"), ("lo", "ens_min_af"), ("hi", "ens_max_af")):
                v = getattr(r, col)
                arr[k][i][j] = None if pd.isna(v) else round(float(v))
            arr["ls"][i][j] = r.min_source if isinstance(r.min_source, str) else None
            arr["hs"][i][j] = r.max_source if isinstance(r.max_source, str) else None
        out[huc] = {"b": bands, **arr}
    return out


def _clim():
    """Median and interquartile range per product/basin on the history's sampled
    day-of-WY grid (every BACKFILL_EVERY_N_DAYS days)."""
    clim, avail, years = {}, [], []
    n = C.BACKFILL_EVERY_N_DAYS
    for p in C.CLIM_PRODUCTS:
        f = C.CLIM_DIR / f"{p}_clim.parquet"
        if not f.exists():
            continue
        df = pd.read_parquet(f)
        avail.append(p)
        if "wy_first" in df:
            years += [int(df["wy_first"].min()), int(df["wy_last"].max())]
        df = df[(df["dowy"] - 1) % n == 0] if n > 1 else df
        grid = sorted(int(d) for d in df["dowy"].unique())
        clim[p] = {"d": grid, "b": {}}
        for huc, g in df.groupby("huc"):
            g = g.set_index("dowy").reindex(grid)
            clim[p]["b"][huc] = {"m": _nan_list(g["median"]), "q1": _nan_list(g["p25"]), "q3": _nan_list(g["p75"])}
    period = (f"WY{min(years)}\u2013WY{max(years)}" if years
              else f"WY{C.CLIM_START_WY}\u2013WY{C.CLIM_END_WY or C.BACKFILL_END_WY}")
    return clim, avail, period


def _hist_years(wy):
    """Each historical water year's series per product and basin, on the same
    sampled day-of-WY grid, so individual years can be switched on in the page.
    The page's own water year (and later ones) is left out: it is drawn as the
    current year from _current_year()."""
    out = {}
    n = C.BACKFILL_EVERY_N_DAYS
    end = min(C.CLIM_END_WY or 9999, wy - 1)
    for p in C.CLIM_PRODUCTS:
        files = sorted(f for f in (C.STATS_DIR / "hist" / p).glob("WY*.parquet")
                       if ".partial" not in f.name and C.CLIM_START_WY <= int(f.stem[2:6]) <= end)
        if not files:
            continue
        df = pd.concat([pd.read_parquet(f, columns=["date", "huc", "volume_af"]).assign(wy=int(f.stem[2:6]))
                        for f in files], ignore_index=True)
        df["dowy"] = dowy(df["date"])
        df = df.dropna(subset=["dowy"])
        df["dowy"] = df["dowy"].astype(int)
        if n > 1:
            df = df[(df["dowy"] - 1) % n == 0]
        grid = sorted(df["dowy"].unique().tolist())
        wys = sorted(df["wy"].unique().tolist())
        piv = df.pivot_table(index=["huc", "wy"], columns="dowy", values="volume_af", aggfunc="first")
        piv = piv.reindex(columns=grid)
        b = {}
        for huc, g in piv.groupby(level="huc"):
            g = g.droplevel("huc").reindex(wys)
            b[huc] = [_nan_list(row) for row in g.to_numpy()]
        out[p] = {"d": [int(x) for x in grid], "y": [int(w) for w in wys], "b": b}
    return out


def _current_year(wy):
    """Each product's unmasked basin volume for the whole WY `wy` season, for the
    current-year line of the history panels, independent of the report dates.

    Sources, best first, merged by date:
      1. the statewide daily run   (stats/current/WY<wy>_products.parquet, unmasked rows)
      2. a backfill of this year   (stats/hist/<PRODUCT>/WY<wy>.parquet)
      3. weekly-report imports     (report dates only; the fallback before 1 or 2 exist)
    """
    frames = []
    cur = C.STATS_DIR / "current" / f"WY{wy}_products.parquet"
    if cur.exists():
        df = pd.read_parquet(cur)
        df = df[~df["masked"]]
        rep = (df["source"].astype(str).str.contains("report", case=False)
               if "source" in df else pd.Series(False, index=df.index))
        frames += [df[~rep].assign(rank=0), df[rep].assign(rank=2)]
    for p in C.CLIM_PRODUCTS:
        f = C.STATS_DIR / "hist" / p / f"WY{wy}.parquet"
        if f.exists():
            frames.append(pd.read_parquet(f, columns=["date", "huc", "volume_af"]).assign(product=p, rank=1))
    if not frames:
        return {}
    df = pd.concat([f[["date", "product", "huc", "volume_af", "rank"]] for f in frames], ignore_index=True)
    df = df[df["product"].isin(C.CLIM_PRODUCTS)]
    df = (df.sort_values("rank").drop_duplicates(["date", "product", "huc"], keep="first"))
    out = {}
    for p, g in df.groupby("product"):
        w = g.pivot_table(index="date", columns="huc", values="volume_af", aggfunc="first").sort_index()
        out[p] = {"t": [pd.Timestamp(d).strftime("%Y-%m-%d") for d in w.index],
                  "b": {h: _nan_list(w[h]) for h in w.columns},
                  "n": int(len(w))}
    return out


VENDOR = {  # CDN tag -> local copy in web/vendor (used by --offline)
    '<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>': "leaflet-1.9.4.min.js",
    '<script src="https://cdn.jsdelivr.net/npm/plotly.js-basic-dist-min@2.35.2/plotly-basic.min.js"></script>':
        "plotly-basic-2.35.2.min.js",
}
FONT_TAGS = [
    '<link rel="preconnect" href="https://fonts.googleapis.com">',
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Public+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap">',
]


def make_offline(html):
    """Inline the map/chart libraries and drop the web font, so the page runs
    with no network access (e.g. as an email attachment)."""
    for tag, fname in VENDOR.items():
        if tag not in html:
            raise RuntimeError(f"library tag not found in template: {tag}")
        js = (C.WEB_DIR / "vendor" / fname).read_text(encoding="utf-8").replace("</script", "<\\/script")
        html = html.replace(tag, f"<script>/* {fname} */\n{js}\n</script>")
    for tag in FONT_TAGS:
        html = html.replace(tag, "")
    return html


def build(wy, offline=False):
    geo, basins = _geometry()
    dates, series, source, date_products = _series(wy)
    clim, avail, period = _clim()
    hist = _hist_years(wy)
    cur_year = _current_year(wy)
    elev = _elev(wy, dates)
    payload = {
        "meta": {
            "wy": wy, "dates": dates, "dowy": [int(x) for x in dowy(pd.to_datetime(dates))],
            "products": C.PRODUCTS, "labels": C.PRODUCT_LABELS,
            "climProducts": C.CLIM_PRODUCTS, "climAvailable": avail,
            "climPeriod": period,
            "threshold": C.SNOW_THRESHOLD_IN, "minAgree": C.MIN_AGREEMENT,
            "source": source, "built": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "cities": CITIES, "bandFt": C.ELEV_BAND_FT, "dateProducts": date_products,
            "histEvery": C.BACKFILL_EVERY_N_DAYS,
        },
        "elev": elev, "hist": hist, "cur": cur_year,
        "basins": basins, "series": series, "clim": clim, "geo": geo,
    }
    tpl = (C.WEB_DIR / "template.html").read_text(encoding="utf-8")
    blob = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
    html = tpl.replace("__SWEET_DATA__", blob)
    out = C.WEB_DIR / "sweet_explorer.html"
    out.write_text(html, encoding="utf-8")
    if offline:
        off = C.WEB_DIR / "sweet_explorer_offline.html"
        off.write_text(make_offline(html), encoding="utf-8")
        print(f"Wrote {off} ({off.stat().st_size / 1e6:.2f} MB, no network needed)")
    n6, n8, n12 = (sum(1 for h in elev if len(h) == k) for k in (6, 8, 12))
    cur_txt = ", ".join(f"{p} {v['n']}" for p, v in cur_year.items()) or "none"
    print(f"Wrote {out} ({out.stat().st_size / 1e6:.2f} MB); climatology: {avail or 'none yet'} "
          f"({len(next(iter(hist.values()))['y']) if hist else 0} WYs); "
          f"elevation bands: {n6} HUC6 / {n8} HUC8 / {n12} HUC12; "
          f"WY{wy} history-panel days: {cur_txt}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--wy", type=int, required=True)
    ap.add_argument("--offline", action="store_true",
                    help="also write sweet_explorer_offline.html with libraries inlined (email attachment)")
    a = ap.parse_args()
    build(a.wy, a.offline)
