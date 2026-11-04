"""
Build the statewide reporting domain from WBD HUC6/HUC8 polygons.

Outputs (data/domain/):
    domain.gpkg     layers in the analysis CRS (EPSG:5070):
                      'huc8'       the reporting HUC8s
                      'huc6'       each HUC6 as the union of its reporting HUC8s
                                   (HUC6 totals = sum of the included HUC8s)
                      'huc6_full'  full WBD extent of the partial HUC6s (map outline)
                      'huc12'      selected HUC12 subwatersheds (C.WBD_HU12), if present
    huc8_lookup.csv  HUC8 code, name, parent HUC6, OSE grouping, area
    huc6_lookup.csv  HUC6 coverage: included/full area, HUC8 counts, excluded HUC8s
    huc12_lookup.csv HUC12 code, name, parent HUC8/HUC6, area (if HUC12s present)

HUC12s are a hand-picked set, not a partition of the HUC8s: they are zoned
independently and never added into HUC8/HUC6 totals.

Everything downstream is keyed on HUC codes, never on names (names repeat:
'Upper Rio Grande' is both a HUC6 and a HUC8, 'Rio Salado' occurs twice).

Run:  python -m src.domain
"""
import warnings

import geopandas as gpd
import pandas as pd
import shapely
from shapely.geometry import MultiPolygon, Polygon

from src import config as C


def _read_hu8_supplement(codes_needed):
    """Look for missing HUC8 polygons in the supplemental shapefiles."""
    found = []
    for path in C.SUPPLEMENTAL_HU8:
        if not path.exists() or not codes_needed:
            continue
        gdf = gpd.read_file(path)
        col = next((c for c in gdf.columns if c.upper() == "HUC8"), None)
        if col is None:
            continue
        gdf = gdf.rename(columns={col: "HUC8"})
        gdf["HUC8"] = gdf["HUC8"].astype(str)
        hit = gdf[gdf["HUC8"].isin(codes_needed)].to_crs(C.CRS_ANALYSIS)
        if len(hit):
            name_col = next((c for c in hit.columns if c.lower() == "name"), None)
            hit = hit.assign(Name=hit[name_col] if name_col else hit["HUC8"],
                             States=hit.get("States", ""))
            found.append(hit[["HUC8", "Name", "States", "geometry"]])
            codes_needed = codes_needed - set(hit["HUC8"])
    out = pd.concat(found, ignore_index=True) if found else None
    return out, codes_needed


def _all_known_hu8(hu8):
    """Every HUC8 in the WBD extract and supplements (to name excluded HUC8s)."""
    frames = [hu8[["HUC8", "Name", "geometry"]]]
    for path in C.SUPPLEMENTAL_HU8:
        if path.exists():
            g = gpd.read_file(path).to_crs(C.CRS_ANALYSIS)
            col = next((c for c in g.columns if c.upper() == "HUC8"), None)
            name = next((c for c in g.columns if c.lower() == "name"), None)
            if col:
                frames.append(g.rename(columns={col: "HUC8", name: "Name"})[["HUC8", "Name", "geometry"]])
    known = pd.concat(frames, ignore_index=True)
    known["HUC8"] = known["HUC8"].astype(str)
    known = known.drop_duplicates("HUC8")
    known["area_km2"] = known.geometry.area / 1e6
    return known


def _fill_slivers(geom, max_hole_km2=1.0):
    """Drop interior holes < max_hole_km2 left by edge mismatches between WBD vintages."""
    polys = getattr(geom, "geoms", [geom])
    out = [Polygon(p.exterior, [r for r in p.interiors if Polygon(r).area / 1e6 >= max_hole_km2])
           for p in polys]
    return out[0] if len(out) == 1 else MultiPolygon(out)


def _empty_huc12():
    return gpd.GeoDataFrame(columns=["HUC12", "Name", "States", "HUC8", "HUC6", "area_km2", "geometry"],
                            geometry="geometry", crs=C.CRS_ANALYSIS)


def _build_huc12(huc8):
    """Selected HUC12s from C.WBD_HU12, with parent HUC8/HUC6 codes."""
    if not C.WBD_HU12.exists():
        return _empty_huc12()
    g = gpd.read_file(C.WBD_HU12).to_crs(C.CRS_ANALYSIS)
    col = next((c for c in g.columns if c.upper() == "HUC12"), None)
    if col is None:
        warnings.warn(f"{C.WBD_HU12} has no HUC12 column; HUC12 level skipped.")
        return _empty_huc12()
    name = next((c for c in g.columns if c.lower() == "name"), None)
    states = next((c for c in g.columns if c.lower() == "states"), None)
    g = g.rename(columns={col: "HUC12"})
    g["HUC12"] = g["HUC12"].astype(str)
    g["Name"] = g[name] if name else g["HUC12"]
    g["States"] = g[states] if states else ""
    g["HUC8"], g["HUC6"] = g["HUC12"].str[:8], g["HUC12"].str[:6]
    g["area_km2"] = g.geometry.area / 1e6
    orphans = sorted(set(g["HUC8"]) - set(huc8["HUC8"]))
    if orphans:
        warnings.warn(f"HUC12 parent HUC8s outside the domain: {orphans}. Those HUC12s are "
                      "still reported, but their HUC8 is not on the map.")
    return g[["HUC12", "Name", "States", "HUC8", "HUC6", "area_km2", "geometry"]] \
        .sort_values("HUC12").reset_index(drop=True)


def build_domain(write=True):
    hu8 = gpd.read_file(C.WBD_HU8).to_crs(C.CRS_ANALYSIS)
    hu6 = gpd.read_file(C.WBD_HU6).to_crs(C.CRS_ANALYSIS)
    hu8["HUC8"] = hu8["HUC8"].astype(str)
    hu6["HUC6"] = hu6["HUC6"].astype(str)

    in_state = hu8["States"].fillna("").str.split(",").apply(lambda s: C.DOMAIN_STATE in s)
    keep = in_state | hu8["HUC8"].isin(list(C.EXTRA_HUC8))
    huc8 = hu8.loc[keep, ["HUC8", "Name", "States", "geometry"]].copy()

    # fill required HUC8s that the regional extract does not contain
    missing = set(C.EXTRA_HUC8) - set(huc8["HUC8"])
    if missing:
        supp, still_missing = _read_hu8_supplement(missing)
        if supp is not None:
            huc8 = pd.concat([huc8, supp], ignore_index=True)
        if still_missing:
            warnings.warn(f"HUC8s not found in any input shapefile: {sorted(still_missing)}. "
                          "They are omitted, and their HUC6 totals will not include them.")

    huc8["HUC6"] = huc8["HUC8"].str[:6]
    huc8["OSE Grouping"] = huc8["HUC8"].map(C.OSE_GROUPING)
    huc8["area_km2"] = huc8.geometry.area / 1e6
    huc8 = huc8.sort_values("HUC8").reset_index(drop=True)

    # HUC6: union of the reporting HUC8s, so every HUC6 total is exactly the
    # sum of its HUC8 totals. HUC6s whose WBD extent reaches beyond the domain
    # are flagged 'partial' with the excluded area and known excluded HUC8s.
    full = hu6.set_index("HUC6")
    known8 = _all_known_hu8(hu8)
    rows, outlines = [], []
    for code, g in huc8.groupby("HUC6"):
        geom = _fill_slivers(shapely.union_all(g.geometry.values))
        full_geom = full.geometry.get(code)
        full_km2 = full_geom.area / 1e6 if full_geom is not None else geom.area / 1e6
        incl_km2 = geom.area / 1e6
        excl = known8[(known8["HUC8"].str[:6] == code) & ~known8["HUC8"].isin(huc8["HUC8"])]
        partial = (full_km2 - incl_km2) > C.PARTIAL_HUC6_FRAC * full_km2
        rows.append(dict(
            HUC6=code, Name=full["Name"].get(code, code), States=full["States"].get(code, ""),
            area_km2=incl_km2, full_area_km2=full_km2, coverage=incl_km2 / full_km2,
            n_huc8=len(g), partial=bool(partial),
            excluded_huc8=";".join(f"{r.HUC8}:{r.Name}" for r in excl.sort_values("HUC8").itertuples()) if partial else "",
            excluded_listed_km2=excl["area_km2"].sum() if partial else 0.0,
            geometry=geom))
        if partial and full_geom is not None:
            outlines.append(dict(HUC6=code, geometry=full_geom))
    huc6 = gpd.GeoDataFrame(rows, crs=C.CRS_ANALYSIS).sort_values("HUC6").reset_index(drop=True)
    huc6_full = gpd.GeoDataFrame(outlines, columns=["HUC6", "geometry"], geometry="geometry", crs=C.CRS_ANALYSIS)

    lookup = huc8.drop(columns="geometry").merge(
        huc6[["HUC6", "Name"]].rename(columns={"Name": "HUC6 Name"}), on="HUC6", how="left")

    huc12 = _build_huc12(huc8)

    if write:
        C.DOMAIN_DIR.mkdir(parents=True, exist_ok=True)
        gpkg = C.DOMAIN_DIR / "domain.gpkg"
        gpkg.unlink(missing_ok=True)          # no stale layers (e.g. an old huc12)
        huc8.to_file(gpkg, layer="huc8", driver="GPKG")
        huc6.to_file(gpkg, layer="huc6", driver="GPKG")
        huc6_full.to_file(gpkg, layer="huc6_full", driver="GPKG")
        if len(huc12):
            huc12.to_file(gpkg, layer="huc12", driver="GPKG")
        lookup.to_csv(C.DOMAIN_DIR / "huc8_lookup.csv", index=False)
        huc6.drop(columns="geometry").to_csv(C.DOMAIN_DIR / "huc6_lookup.csv", index=False)
        huc12.drop(columns="geometry").to_csv(C.DOMAIN_DIR / "huc12_lookup.csv", index=False)
        print(f"Domain: {len(huc8)} HUC8s, {len(huc6)} HUC6s "
              f"({int(huc6.partial.sum())} partial), {len(huc12)} HUC12s -> {gpkg}")
    return huc8, huc6


def load_domain():
    gpkg = C.DOMAIN_DIR / "domain.gpkg"
    if not gpkg.exists():
        return build_domain(write=True)
    return (gpd.read_file(gpkg, layer="huc8"),
            gpd.read_file(gpkg, layer="huc6"))


def load_huc6_full():
    return gpd.read_file(C.DOMAIN_DIR / "domain.gpkg", layer="huc6_full")


def load_huc12():
    """Selected HUC12s (empty GeoDataFrame if none). Rebuilds the domain if the
    HUC12 shapefile exists but domain.gpkg predates it."""
    gpkg = C.DOMAIN_DIR / "domain.gpkg"
    if not gpkg.exists():
        build_domain(write=True)
    def _read():
        try:
            return gpd.read_file(gpkg, layer="huc12")
        except Exception:          # layer absent (domain built without HUC12s)
            return None
    g = _read()
    if g is None and C.WBD_HU12.exists():
        build_domain(write=True)
        g = _read()
    if g is None or g.empty:
        return _empty_huc12()
    g["HUC12"] = g["HUC12"].astype(str)
    return g


if __name__ == "__main__":
    build_domain()
