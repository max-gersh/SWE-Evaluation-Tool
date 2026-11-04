"""
Synthetic end-to-end test: known SWE fields -> run_daily -> check volumes.

SNODAS = 10 in everywhere, UA SWE = 10 in everywhere except 0.05 in (below the
0.1 in threshold) west of 107.5 W, CU SWE = 0 everywhere.
Expected:
  east of 107.5W: 2 products report snow -> in mask; ensemble = mean(10,10,0)
  west of 107.5W: only SNODAS reports snow -> outside mask; ensemble volume 0
  unmasked SNODAS volume = 10 in x basin area for every basin.
Also exercises the SNODAS tar/.dat.gz parser via a mocked HTTP response.
"""
import gzip, io, tarfile, sys
from pathlib import Path
from unittest import mock

import numpy as np, xarray as xr, rioxarray  # noqa
from rasterio.transform import from_bounds

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config as C, sources, zonal, run_daily
from src.domain import load_domain, load_huc12

DATE = "20990115"      # synthetic date, keeps test files apart from real ones
AF_PER_KM2_IN = 1e6 * 0.0254 / 1233.48183754752

def fake_snodas_response():
    arr = np.full((sources.SNODAS_ROWS, sources.SNODAS_COLS), 254, dtype=">i2")  # 254 mm = 10 in
    raw = gzip.compress(arr.tobytes())
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as t:
        name = f"us_ssmv11034tS__T0001TTNATS{DATE}05HP001.dat.gz"
        ti = tarfile.TarInfo(name); ti.size = len(raw); t.addfile(ti, io.BytesIO(raw))
    r = mock.Mock(status_code=200, content=buf.getvalue()); r.raise_for_status = lambda: None
    return r

def write_fakes():
    lon = np.arange(-112.5, -100.0, 0.008) + 0.004
    lat = np.arange(38.5, 30.5, -0.008) - 0.004
    ua = np.where(lon[None, :] < -107.5, 0.05 * 25.4, 254.0) * np.ones((len(lat), 1))
    ds = xr.Dataset({"SWE": (("time", "lat", "lon"), ua[None].astype("float32"))},
                    coords={"time": [np.datetime64("2099-01-15")], "lat": lat, "lon": lon})
    sources.uaswe_path(DATE).parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(sources.uaswe_path(DATE))
    cu = xr.DataArray(np.zeros((1000, 1500), "float32"), dims=("y", "x"))
    tr = from_bounds(-113, 30, -99, 39, 1500, 1000)
    cu = cu.rio.write_transform(tr).rio.write_crs("EPSG:4326").assign_coords(
        x=tr.c + tr.a * (np.arange(1500) + .5), y=tr.f + tr.e * (np.arange(1000) + .5))
    sources.cuswe_path(DATE).parent.mkdir(parents=True, exist_ok=True)
    cu.rio.to_raster(sources.cuswe_path(DATE))

DEM = C.DATA_DIR / "test_dem_ft.tif"

def write_dem():
    """Synthetic DEM (ft): 4,000 ft at 31N rising 1,500 ft per degree north."""
    lat = np.arange(39, 30, -0.01) - 0.005
    lon = np.arange(-113, -99, 0.01) + 0.005
    z = (4000 + (lat[:, None] - 31) * 1500) * np.ones((1, len(lon)))
    tr = from_bounds(-113, 30, -99, 39, len(lon), len(lat))
    da = xr.DataArray(z.astype("float32"), dims=("y", "x")).rio.write_transform(tr).rio.write_crs("EPSG:4326")
    da.assign_coords(x=lon, y=lat).rio.to_raster(DEM)

def main():
    write_fakes(); write_dem()
    with mock.patch("src.sources.requests.get", return_value=fake_snodas_response()), \
         mock.patch.object(C, "DEM_PATH", DEM), mock.patch.object(C, "DEM_UNITS", "ft"):
        prod, ens, elev = run_daily.run(DATE)
    huc8, huc6 = load_domain()
    huc12 = load_huc12()
    area = dict(zip(huc8.HUC8, huc8.area_km2)); area.update(dict(zip(huc6.HUC6, huc6.area_km2)))
    area.update(dict(zip(huc12.HUC12, huc12.area_km2)))

    sn = prod[(prod["product"] == "SNODAS") & (~prod.masked)].set_index("huc")
    rel = (sn.volume_af / (sn.index.map(area) * 10 * AF_PER_KM2_IN) - 1).abs()
    big = sn.level != "huc12"
    print(f"Unmasked SNODAS vs 10 in x polygon area: max rel. error {rel[big].max():.4f} (rasterization at 500 m)")
    assert rel[big].max() < 0.02
    if len(huc12):
        # HUC12s: same check with a looser bound (fewer pixels, larger edge share),
        # every selected HUC12 present, and never more volume than its parent HUC8
        r12 = rel[~big]
        print(f"HUC12s ({len(huc12)}): max rel. error {r12.max():.4f}; "
              + ", ".join(f"{h} {area[h]:.0f} km2" for h in huc12.HUC12))
        assert set(huc12.HUC12) <= set(sn.index[~big]) and r12.max() < 0.06
        v8 = sn[sn.level == "huc8"].volume_af
        par = huc12.set_index("HUC12").HUC8
        over = [(h, p) for h, p in par.items() if p in v8 and sn.volume_af[h] > v8[p] + 1e-3]
        assert not over, over

    # Upper Pecos (13060003) lies east of 107.5W; Upper Gila (15040001) west
    e = ens.set_index("huc")
    exp_e = area["13060003"] * AF_PER_KM2_IN * 20 / 3
    print(f"13060003 ensemble mean {e.loc['13060003','ens_mean_af']:.0f} af, expected {exp_e:.0f}; "
          f"min source {e.loc['13060003','min_source']}")
    assert abs(e.loc["13060003", "ens_mean_af"] / exp_e - 1) < 0.02
    assert e.loc["13060003", "min_source"] == "CU_SWE"
    print(f"15040001 ensemble mean {e.loc['15040001','ens_mean_af']:.0f} af (expected 0: only SNODAS >= 0.1 in); "
          f"reported={e.loc['15040001','reported']}")
    assert e.loc["15040001", "ens_mean_af"] == 0 and not e.loc["15040001", "reported"]
    ua_west = prod[(prod["product"] == "UA_SWE") & (~prod.masked) & (prod.huc == "15040001")].volume_af.iloc[0]
    print(f"15040001 unmasked UA SWE {ua_west:.0f} af (0.05 in trace set to 0 by threshold)")
    assert ua_west == 0
    # HUC6 totals must equal the sum of their included HUC8 totals, for every
    # product (masked and unmasked) and for the ensemble
    p8 = prod[prod.level == "huc8"].assign(h6=lambda d: d.huc.str[:6])
    s8 = p8.groupby(["product", "masked", "h6"]).volume_af.sum()
    s6 = prod[prod.level == "huc6"].set_index(["product", "masked", "huc"]).volume_af
    worst = (s6 - s8.reindex(s6.index)).abs().max()
    print(f"HUC6 vs sum of HUC8s (all products, masked+unmasked): max |diff| = {worst:.6f} af")
    assert worst < 1e-3
    # elevation bands: per basin, the band volumes must add up to the masked
    # basin volume for every product, and the band ensemble means to the
    # basin ensemble mean
    m = prod[prod.masked].set_index(["level", "huc", "product"]).volume_af
    for p in ["SNODAS", "UA_SWE", "CU_SWE"]:
        bsum = elev.groupby(["level", "huc"])[f"vol_{p}"].sum()
        d = (bsum - m.xs(p, level="product").reindex(bsum.index)).abs().max()
        assert d < 1e-3, (p, d)
    e_sum = elev.groupby(["level", "huc"]).ens_mean_af.sum()
    e_bas = ens.set_index(["level", "huc"]).ens_mean_af.reindex(e_sum.index)
    print(f"Elevation bands: sum of band volumes vs basin volume, max |diff| = {(e_sum - e_bas).abs().max():.6f} af")
    assert (e_sum - e_bas).abs().max() < 1e-3
    b = elev[(elev.level == "huc8") & (elev.huc == "13060003")]
    print(f"13060003 bands (ft): {b.band_lo_ft.min():.0f}-{b.band_lo_ft.max() + 1000:.0f}, {len(b)} bands")
    DEM.unlink(missing_ok=True)
    print("ALL CHECKS PASSED")

if __name__ == "__main__":
    main()
