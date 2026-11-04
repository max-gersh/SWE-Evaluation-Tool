"""
fetch_wbd_additions.py — SWEET spatial-extent additions

1. Mancos HUC8 (14080107)  -> data/Shapefiles/WBD_supplement/wbdhu8_mancos.shp
2. Eight HUC12s           -> data/Shapefiles/WBD_HUC12/wbdhu12_sweet.shp

The Mancos HUC8 is looked up by ID. The HUC12s are looked up by NAME in the
USGS WBD MapServer (hydro.nationalmap.gov): each name must match exactly one
WBD HUC12 within its parent HUC8 (widened to the HUC4 if absent). The resolved
IDs are printed next to the IDs originally supplied. Unresolved names get a
list of nearby candidates and block the HUC12 write. It also checks each polygon's computed area (EPSG:5070) against the
WBD areasqkm attribute. Finally, it reports Upper San Juan HUC6 (140801)
coverage using your local WBD_NM extract plus WBD_supplement.

Run from the repo root:  python scripts/fetch_wbd_additions.py
"""
from pathlib import Path
import sys

import requests
import geopandas as gpd
import pandas as pd
import shapely

ROOT = Path(__file__).resolve().parents[1]
SHP = ROOT / "data" / "Shapefiles"
SUPP = SHP / "WBD_supplement"
H12_DIR = SHP / "WBD_HUC12"

SVC = "https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer"
LAYER = {"huc6": 3, "huc8": 4, "huc12": 6}
AREA_CRS = "EPSG:5070"

HUC8_ADD = {"14080107": "Mancos"}
# HUC12s by WBD name (authoritative), with the parent HUC8 to search in.
# Comment: the ID originally supplied, kept only for the comparison printout.
HUC12_NAMES = [
    ("Headwaters Santa Fe River", "13020201"),  # 130202010102
    ("Headwaters Navajo River",   "14080101"),  # 140801010602
    ("Headwaters Rio Blanco",     "14080101"),  # 140801010302
    ("Headwaters Rio Chama",      "13020102"),  # 130201020101
    ("Little Navajo River",       "14080101"),  # 140801010502
    ("East Fork Navajo River",    "14080101"),  # 140801010601 (was "Upper Navajo River")
    ("Archuleta Creek",           "13020102"),  # 130201020102
    ("Wolf Creek",                "13020102"),  # 130201020203 (pinned below; was "Upper Rio Brazos")
]
SUPPLIED_IDS = ["130202010102", "140801010602", "140801010302", "130201020101",
                "140801010502", "140801010601", "130201020102", "130201020203"]
# Names whose ID has been confirmed by the user: the WBD record for the ID must
# carry this name, otherwise the run stops (guards against WBD renames).
PINNED = {"Wolf Creek": "130201020203"}
GENERIC = {"headwaters", "upper", "lower", "middle", "river", "creek", "rio", "of", "the",
           "east", "west", "north", "south", "fork", "little", "canyon", "arroyo"}


def query(level: str, ids: list[str]) -> gpd.GeoDataFrame:
    """Full-resolution polygons for the given HUC IDs (no generalization)."""
    field = level  # huc8 / huc12 field names match the level
    where = f"{field} IN ({','.join(repr(i) for i in ids)})"
    r = requests.get(
        f"{SVC}/{LAYER[level]}/query",
        params={"where": where, "outFields": "*", "returnGeometry": "true",
                "outSR": 4326, "f": "geojson"},
        timeout=180,
    )
    r.raise_for_status()
    gdf = gpd.GeoDataFrame.from_features(r.json()["features"], crs="EPSG:4326")
    if gdf.empty:
        sys.exit(f"No {level} features returned for {ids}")
    return gdf


def verify(gdf: gpd.GeoDataFrame, level: str, expected: dict) -> bool:
    ok = True
    gdf = gdf.copy()
    gdf["calc_km2"] = gdf.to_crs(AREA_CRS).area / 1e6
    print(f"\n{level.upper()} check")
    print(f"{'ID':<14}{'Expected':<28}{'WBD name':<28}{'WBD km2':>10}{'Calc km2':>10}  Status")
    for huc, exp in expected.items():
        row = gdf[gdf[level] == huc]
        if row.empty:
            print(f"{huc:<14}{exp:<28}{'— not found —':<28}{'':>10}{'':>10}  MISSING")
            ok = False
            continue
        row = row.iloc[0]
        name_ok = row["name"].strip().lower() == exp.lower()
        area_ok = abs(row["calc_km2"] - row["areasqkm"]) / row["areasqkm"] < 0.001
        status = "OK" if name_ok and area_ok else (
            "NAME MISMATCH" if not name_ok else "AREA MISMATCH")
        ok &= name_ok and area_ok
        print(f"{huc:<14}{exp:<28}{row['name']:<28}{row['areasqkm']:>10.2f}"
              f"{row['calc_km2']:>10.2f}  {status}  ({row.get('states', '')})")
    return ok


def keep_cols(gdf: gpd.GeoDataFrame, level: str) -> gpd.GeoDataFrame:
    """Same field names as the WBD_NM extract (HUC8/HUC12, Name, States), which
    src.domain reads. DBF field names are case-insensitive, so only one of
    name/Name is kept."""
    cols = {level: level.upper(), "name": "Name", "states": "States",
            "areasqkm": "AreaSqKm", "areaacres": "AreaAcres", "tohuc": "ToHUC",
            "loaddate": "LoadDate"}
    out = gdf[[c for c in cols if c in gdf.columns] + ["geometry"]].rename(columns=cols)
    if "LoadDate" in out:  # epoch ms -> date string for the .dbf
        out["LoadDate"] = pd.to_datetime(out["LoadDate"], unit="ms").dt.strftime("%Y-%m-%d")
    return out


def huc6_coverage():
    """Upper San Juan HUC6 coverage from local WBD_NM + WBD_supplement HUC8s."""
    try:
        h6 = gpd.read_file(SHP / "WBD_NM" / "wbdhu6_a_nm.shp").to_crs(AREA_CRS)
        h8 = gpd.read_file(SHP / "WBD_NM" / "wbdhu8_a_nm.shp").to_crs(AREA_CRS)
    except Exception as e:
        print(f"\nHUC6 coverage check skipped ({e})")
        return
    def code(g, n):  # WBD field names vary in case between sources
        c = next(c for c in g.columns if c.upper() == f"HUC{n}")
        return g.rename(columns={c: "code"}).assign(code=lambda d: d["code"].astype(str))
    h6 = code(h6, 6)
    h6 = h6[h6["code"] == "140801"]
    parts = [code(h8, 8)]
    for f in SUPP.glob("*.shp"):
        s = gpd.read_file(f).to_crs(AREA_CRS)
        if any(c.upper() == "HUC8" for c in s.columns):
            parts.append(code(s, 8))
    h8_all = pd.concat([g[g["code"].str.startswith("140801")][["code", "geometry"]] for g in parts])
    h8_all = gpd.GeoDataFrame(h8_all.drop_duplicates("code"), crs=AREA_CRS)
    u6 = shapely.union_all(h6.geometry.values)
    cover = shapely.union_all(h8_all.geometry.values).intersection(u6).area / u6.area
    print(f"\nUpper San Juan HUC6 140801: HUC8s {sorted(h8_all['code'])}")
    print(f"Coverage: {cover:.2%}")


def _attrs(where):
    r = requests.get(f"{SVC}/{LAYER['huc12']}/query",
                     params={"where": where, "outFields": "huc12,name,states,areasqkm",
                             "returnGeometry": "false", "orderByFields": "huc12", "f": "json"},
                     timeout=180)
    r.raise_for_status()
    return [f["attributes"] for f in r.json().get("features", [])]


def _q(x):
    return x.replace("'", "''")


def resolve():
    """Name -> HUC12 ID from WBD. Returns ({id: name} in list order, all_resolved)."""
    resolved, ok = {}, True
    print(f"\nHUC12 name lookup")
    print(f"{'Name':<28}{'Supplied ID':<14}{'WBD ID':<14}{'km2':>8}  {'States':<7} Status")
    for (name, h8), sid in zip(HUC12_NAMES, SUPPLIED_IDS):
        hits, scope = [], None
        if name in PINNED:
            hits = _attrs(f"huc12 = '{PINNED[name]}'")
            if len(hits) == 1 and hits[0]["name"].strip().lower() == name.lower():
                a = hits[0]
                print(f"{name:<28}{sid:<14}{a['huc12']:<14}{a['areasqkm']:>8.2f}  {a['states'] or '':<7} OK (pinned ID)")
                resolved[a["huc12"]] = a["name"]
            else:
                ok = False
                got = hits[0]["name"] if hits else "no such HUC12"
                print(f"{name:<28}{sid:<14}{PINNED[name]:<14}{'':>8}  {'':<7} PINNED ID MISMATCH: WBD has '{got}'")
            continue
        for prefix in (h8, h8[:4]):
            hits = _attrs(f"LOWER(name) = '{_q(name.lower())}' AND huc12 LIKE '{prefix}%'")
            if hits:
                scope = prefix
                break
        if len(hits) == 1:
            a = hits[0]
            note = "OK" + ("" if scope == h8 else f" (found outside HUC8 {h8}, in HUC4 {scope})")
            note += "" if a["huc12"] == sid else "  <- ID corrected"
            print(f"{name:<28}{sid:<14}{a['huc12']:<14}{a['areasqkm']:>8.2f}  {a['states'] or '':<7} {note}")
            resolved[a["huc12"]] = a["name"]
            continue
        ok = False
        if hits:
            print(f"{name:<28}{sid:<14}{'':<14}{'':>8}  {'':<7} AMBIGUOUS: "
                  + "; ".join(f"{a['huc12']} ({a['states']}, {a['areasqkm']:.1f} km2)" for a in hits))
            continue
        words = [w for w in name.lower().split() if w not in GENERIC] or name.lower().split()[-1:]
        like = " OR ".join(f"LOWER(name) LIKE '%{_q(w)}%'" for w in words)
        cand = _attrs(f"({like}) AND huc12 LIKE '{h8}%'")
        print(f"{name:<28}{sid:<14}{'':<14}{'':>8}  {'':<7} NOT FOUND in WBD by this name")
        for a in cand[:15]:
            print(f"{'':<4}candidate {a['huc12']}  {a['name']}  ({a['states']}, {a['areasqkm']:.1f} km2)")
        if not cand:
            print(f"{'':<4}no HUC12 in {h8} has '{'/'.join(words)}' in its name")
    return resolved, ok


def main():
    SUPP.mkdir(parents=True, exist_ok=True)
    H12_DIR.mkdir(parents=True, exist_ok=True)

    h8 = query("huc8", list(HUC8_ADD))
    ok8 = verify(h8, "huc8", HUC8_ADD)
    huc12_add, ok12 = resolve()
    if huc12_add:
        h12 = query("huc12", list(huc12_add))
        ok12 = verify(h12, "huc12", huc12_add) and ok12

    # each level is written only if all of its rows check out
    if ok8:
        keep_cols(h8, "huc8").to_file(SUPP / "wbdhu8_mancos.shp")
        print(f"\nWrote {SUPP / 'wbdhu8_mancos.shp'}")
        huc6_coverage()
    else:
        print("\nHUC8 mismatch: Mancos not written.")
    if ok12:
        order = list(huc12_add)
        h12 = keep_cols(h12, "huc12").set_index("HUC12").loc[order].reset_index()
        h12.to_file(H12_DIR / "wbdhu12_sweet.shp")
        print(f"Wrote {H12_DIR / 'wbdhu12_sweet.shp'} ({len(h12)} HUC12s)")
    else:
        print("HUC12s unresolved: shapefile not written. Fix the names in HUC12_NAMES "
              "(see candidates above) and re-run.")
    if not (ok8 and ok12):
        sys.exit(1)


if __name__ == "__main__":
    main()
