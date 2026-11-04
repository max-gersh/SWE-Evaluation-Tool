"""
Statewide SWEET configuration.

All settings for the statewide expansion live here so that the domain, the
agreement rule and the climatology period can be changed without editing the
processing code.
"""
from pathlib import Path  # noqa: F401  (for PUBLISH_DIR)

from src import BASE_DIR

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR = BASE_DIR / "data"
SHP_DIR = DATA_DIR / "Shapefiles"
WBD_HU8 = SHP_DIR / "WBD_NM" / "wbdhu8_a_nm.shp"   # regional WBD extract (HUC8)
WBD_HU6 = SHP_DIR / "WBD_NM" / "wbdhu6_a_nm.shp"   # regional WBD extract (HUC6)
# Optional shapefiles used only to fill HUC8s that the regional extract lacks
# (e.g. the Colorado headwaters basins). Any file with a HUC8 column works.
SUPPLEMENTAL_HU8 = [
    SHP_DIR / "WBDHU8_RG" / "WBDHU8_RG.shp",
    SHP_DIR / "WBD_supplement" / "wbdhu8_supplement.shp",
    SHP_DIR / "WBD_supplement" / "wbdhu8_mancos.shp",
]
# Selected HUC12 subwatersheds (HUC12 tab). Written by scripts/fetch_wbd_additions.py;
# the domain simply has no HUC12 level if the file is absent.
WBD_HU12 = SHP_DIR / "WBD_HUC12" / "wbdhu12_sweet.shp"
DOMAIN_DIR = DATA_DIR / "domain"            # outputs of src.domain
STATS_DIR = DATA_DIR / "stats"              # daily basin statistics (parquet)
CLIM_DIR = DATA_DIR / "climatology"         # per-product day-of-WY climatology
WEB_DIR = BASE_DIR / "web"

# ---------------------------------------------------------------------------
# Analysis grid
# ---------------------------------------------------------------------------
# CONUS Albers equal-area: pixel area is constant across the state, so
# volume = sum(SWE) * pixel_area holds everywhere (UTM 13N distorts area in
# the western part of the state, which lies in zone 12).
CRS_ANALYSIS = "EPSG:5070"
GRID_RES_M = 500            # common grid resolution (m); CU SWE native
GRID_PAD_M = 5_000          # padding around domain bounds

# ---------------------------------------------------------------------------
# Reporting domain
# ---------------------------------------------------------------------------
# Rule: every full HUC8 whose WBD 'States' attribute includes NM, plus the
# upstream contributing basins that the Rio Grande reports already cover.
DOMAIN_STATE = "NM"
EXTRA_HUC8 = {
    "13010001": "Rio Grande Headwaters",
    "13010002": "Alamosa-Trinchera",
    "13010003": "San Luis",
    "13010004": "Saguache",
    "13010005": "Conejos",
    "14080102": "Piedra",
    "14080104": "Animas",
    "14080107": "Mancos",     # completes Upper San Juan HUC6 140801
}

# A HUC6 is flagged 'partial' when more than this fraction of its WBD area
# lies in HUC8s outside the domain (its total then covers the included HUC8s only).
PARTIAL_HUC6_FRAC = 0.01

# HUC8 -> OSE grouping (Table 2). Extend this dict to add groupings.
OSE_GROUPING = {
    "13010001": "Upper Rio Grande",
    "13010004": "Upper Rio Grande",
    "13010005": "Upper Rio Grande",
    "13010003": "Sangre de Cristo",
    "13010002": "Sangre de Cristo",
    "13020101": "Sangre de Cristo",
    "14080101": "San Juan",
    "14080102": "San Juan",
    "14080104": "San Juan",
}

# ---------------------------------------------------------------------------
# Elevation bands
# ---------------------------------------------------------------------------
# DEM covering the full domain (all 81 HUC8s): USGS 3DEP at 100 m in feet,
# written by scripts/fetch_3dep_dem.py. (The Rio Grande report DEM,
# data/dem.tif, is also in feet but covers only the Rio Grande.)
DEM_PATH = DATA_DIR / "dem_3dep_ft.tif"
DEM_UNITS = "ft"            # "ft" or "m" (converted to feet)
ELEV_BAND_FT = 1000         # band width (ft), as in Table 3

# ---------------------------------------------------------------------------
# Snow-presence / agreement rule
# ---------------------------------------------------------------------------
PRODUCTS = ["SNODAS", "UA_SWE", "CU_SWE"]
PRODUCT_LABELS = {"SNODAS": "SNODAS", "UA_SWE": "SWANN (UA)", "CU_SWE": "CU SWE"}
SNOW_THRESHOLD_IN = 0.1     # a product "reports snow" in a pixel if SWE >= this
MIN_AGREEMENT = 2           # pixel kept if >= this many products report snow
# Inside the agreement mask, a product's zero is kept as a real estimate
# (not treated as missing) when computing the ensemble.
ZEROS_IN_ENSEMBLE = True
# A basin is reported only if its agreed snow-covered area reaches this value
# (keeps basins with a handful of stray agreed pixels out of the tables/map).
MIN_REPORT_AREA_KM2 = 2.0

# ---------------------------------------------------------------------------
# Daily update (src.daily_update)
# ---------------------------------------------------------------------------
LOOKBACK_DAYS = 10          # missing season days this far back are caught up/retried
KEEP_RASTER_DAYS = 14       # daily agreement/ensemble rasters older than this are deleted
PUBLISH_DIR = None          # e.g. Path(r"\\ose-web\drought\sweet"): pages are copied here
                            # after each update (None = leave them in web/)

# ---------------------------------------------------------------------------
# Climatology
# ---------------------------------------------------------------------------
# Each product is compared only with its own history (CU SWE history is
# unknown), using the unmasked per-product basin statistics.
CLIM_PRODUCTS = ["SNODAS", "UA_SWE"]   # add "CU_SWE" once its history is backfilled
CLIM_START_WY = 2004        # first full SNODAS water year
CLIM_END_WY = None          # None = every completed WY in data/stats/hist (grows each
                            # year through scripts/rollover_wy.py)
BACKFILL_END_WY = 2025      # last WY the one-time backfill downloads
BACKFILL_EVERY_N_DAYS = 3   # history is sampled every 3rd day of the water year (Oct 1,
                            # Oct 4, ...); the rollover and climatology keep the same grid
SEASON_START = (10, 1)      # (month, day) processed in the backfill
SEASON_END = (7, 31)        # NM SWE is ~0 in Aug-Sep; shortens the backfill
CLIM_PERCENTILES = [10, 25, 50, 75, 90]
