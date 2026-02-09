import os
from datetime import datetime
import rioxarray as rxr
import xarray as xr
import numpy as np
import pandas as pd
import pickle

import importlib
import src.download_data
importlib.reload(src.download_data)
import src.reproject
importlib.reload(src.reproject)
import src.plotting
importlib.reload(src.plotting)
import src.tables_graphs
importlib.reload(src.tables_graphs)
import src.tools
importlib.reload(src.tools)

from src import BASE_DIR


#from src.download_data import download_snodas
#from src.download_data import download_uaswe
#from src.download_data import download_era5

#from src.reproject import load_shapefiles
#date = datetime.today().strftime('%Y%m%d') # get today's date
cu_swe_files = os.listdir("data/CU_SWE")
cu_swe_dates = sorted([fname[:8] for fname in cu_swe_files])
#date = cu_swe_dates[1]
date = '20260201'
date_formatted = datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d")

## make report directories
src.tools.create_report_dirs(date)
# get last report date in current water year
date_last_report = src.tools.last_report_date(date)
if date_last_report != 'NA':
    date_last_report_unformatted = datetime.strptime(date_last_report, "%Y-%m-%d").strftime("%Y%m%d")

# download data
src.download_data.download_snodas(date)
src.download_data.download_uaswe(date)
#src.download_data.download_era5(date)

# load shapefiles

shapefiles = src.reproject.load_shapefiles()
huc6 = shapefiles['huc6']
huc8 = shapefiles['huc8']
OSE = shapefiles['OSE']
state_boundaries = shapefiles['state_boundaries']
nm_cities = shapefiles['nm_cities']


print(f"Generating figures for date {date}")

# load rasters and reproject - set values of 0 to nan
pkl_dir = BASE_DIR / "reports" / date_formatted / "pkl"
snodas_utm = src.reproject.load_snodas(date, filter=True)
ua_swe_utm = src.reproject.load_uaswe(date, reproject=True, filter=True)
cu_swe_utm = src.reproject.load_cuswe(date, reproject=True, filter=True)
#era5_utm = src.reproject.load_era5(date, reproject=True, filter=True)

# save UTM pkl objects
with open(str(pkl_dir / f'SNODAS_utm_{date}.pkl'), "wb") as f:
    pickle.dump(snodas_utm, f, protocol=-1)

with open(str(pkl_dir / f'UA_SWE_utm_{date}.pkl'), "wb") as f:
    pickle.dump(ua_swe_utm, f, protocol=-1)

with open(str(pkl_dir / f'CU_SWE_utm_{date}.pkl'), "wb") as f:
    pickle.dump(cu_swe_utm, f, protocol=-1)

#with open(str(pkl_dir / f'era5_utm_{date}.pkl'), "wb") as f:
#    pickle.dump(era5_utm, f, protocol=-1)

# load rasters without reprojection
ua_swe_unproj = src.reproject.load_uaswe(date, reproject=False, filter=True)
cu_swe_unproj = src.reproject.load_cuswe(date, reproject=False, filter=True)
#era5_unproj = src.reproject.load_era5(date, reproject=False, filter=True)

## generate average raster
# resample to 1km to take average
ua_swe_1km = ua_swe_unproj.rio.reproject_match(snodas_utm, resampling = 1) # 1 = bilinear resampling, 0 = nearest neighbor
cu_swe_1km = cu_swe_unproj.rio.reproject_match(snodas_utm, resampling = 1)
#era5_1km = era5_unproj.rio.reproject_match(snodas_utm, resampling = 1)

# stack rasters and take mean
raster_list = []
raster_list.append(snodas_utm)
raster_list.append(ua_swe_1km)
raster_list.append(cu_swe_1km)
#raster_list.append(era5_1km)

raster_stack = xr.concat(raster_list, dim="layer")
# count non nan values at each pixel
valid_count = raster_stack.notnull().sum(dim="layer")
del(ua_swe_1km, cu_swe_1km, raster_list)

# calculate avg and std dev and mask by valid count
average = raster_stack.mean(dim="layer", skipna=True)
average = average.where(valid_count >= 2)
with open(str(pkl_dir / f'Average_utm_{date}.pkl'), "wb") as f:
    pickle.dump(average, f, protocol=-1)

#std_dev = raster_stack.std(dim="layer", skipna = True)
#std_dev = std_dev.where(valid_count >= 3)
del(raster_stack)

## generate study area overview plots
max_value_cbar = src.plotting.get_max_value(snodas = snodas_utm, cu_swe = cu_swe_utm, ua_swe = ua_swe_utm,
                            average = average)

src.plotting.plot_study_area(data = snodas_utm, data_source = "SNODAS",
                            date = date, max_value_cbar = max_value_cbar)
src.plotting.plot_study_area(data = ua_swe_utm, data_source = "UA_SWE",
                            date = date, max_value_cbar = max_value_cbar)
src.plotting.plot_study_area(data = cu_swe_utm, data_source = "CU_SWE",
                            date = date, max_value_cbar = max_value_cbar)
#src.plotting.plot_study_area(data = era5_utm, data_source = "ERA5",
#                            date = date, max_value_cbar = max_value_cbar)
src.plotting.plot_study_area(data = average, data_source = "Average",
                            date = date, max_value_cbar = max_value_cbar)
#src.plotting.plot_study_area(data = std_dev, data_source = "Std_Dev",
#                            date = date, max_value_cbar = max_value_cbar)


if date_last_report != 'NA':
    ## generate study area difference plots
    src.plotting.plot_study_area_diff(raster_current = snodas_utm, data_source = "SNODAS",
                                date = date, last_report_date = date_last_report)
    src.plotting.plot_study_area_diff(raster_current = ua_swe_utm, data_source = "UA_SWE",
                                date = date, last_report_date = date_last_report)
    src.plotting.plot_study_area_diff(raster_current = cu_swe_utm, data_source = "CU_SWE",
                                date = date, last_report_date = date_last_report)
    #src.plotting.plot_study_area(data = era5_utm, data_source = "ERA5",
    #                            date = date, max_value_cbar = max_value_cbar)
    src.plotting.plot_study_area_diff(raster_current = average, data_source = "Average",
                                date = date, last_report_date = date_last_report)


#############################################################################

## generate statistics tables
# load data and reproject, do not set pixels with less than 1 inch of SWE to nan (filter=False)
snodas_utm_unfilt = src.reproject.load_snodas(date, filter=False)
ua_swe_utm_unfilt = src.reproject.load_uaswe(date, reproject=True, filter=False)
cu_swe_utm_unfilt = src.reproject.load_cuswe(date, reproject=True, filter=False)
#era5_utm_unfilt = src.reproject.load_era5(date, reproject=True, filter=False)


###############################################################################

## set data sources for ensemble min and max
sources = np.array(['SNODAS', 'UA_SWE', 'CU_SWE'])

## table 1
table1_snodas = src.tables_graphs.generate_table1(raster=snodas_utm_unfilt,
                                                  data_source="SNODAS", date=date,
                                                  last_report_date=date_last_report)
table1_ua_swe = src.tables_graphs.generate_table1(raster=ua_swe_utm_unfilt,
                                                  data_source="UA_SWE", date=date,
                                                  last_report_date=date_last_report)
table1_cu_swe = src.tables_graphs.generate_table1(raster=cu_swe_utm_unfilt,
                                                  data_source="CU_SWE", date=date,
                                                  last_report_date=date_last_report)
#table1_era5 = src.tables_graphs.generate_table1(era5_utm_unfilt)

## generate ensemble table
vals_table1 = np.vstack([
    table1_snodas['Estimated Volume (af)'].values,
    table1_ua_swe['Estimated Volume (af)'].values,
    table1_cu_swe['Estimated Volume (af)'].values
])


# ensemble mean
table1_ensemble_mean = np.mean([table1_snodas['Estimated Volume (af)'], table1_ua_swe['Estimated Volume (af)'], 
                         table1_cu_swe['Estimated Volume (af)']], 
                         axis=0)
# ensemble median
table1_ensemble_median = np.median([table1_snodas['Estimated Volume (af)'], table1_ua_swe['Estimated Volume (af)'], 
                         table1_cu_swe['Estimated Volume (af)']], 
                         axis=0)

# numeric min 
table1_ensemble_min = np.nanmin(vals_table1, axis=0)

# index of dataset producing the min
min_idx = [
    np.where(vals_table1[:, j] == table1_ensemble_min[j])[0].tolist()
    for j in range(vals_table1.shape[1])
]
# min source
min_sources_str = [
    ", ".join(sources[i] for i in idxs)
    for idxs in min_idx
]

# numeric max
table1_ensemble_max = np.nanmax(vals_table1, axis=0)

# index of dataset producing the max
max_idx = [
    np.where(vals_table1[:, j] == table1_ensemble_max[j])[0].tolist()
    for j in range(vals_table1.shape[1])
]
# max source
max_sources_str = [
    ", ".join(sources[i] for i in idxs)
    for idxs in max_idx
]

## difference calc
if date_last_report != 'NA':
    table1_last_report_csv = pd.read_csv(BASE_DIR / 'reports' / date_last_report / 'csv_tables' / f'table1_Ensemble_{date_last_report_unformatted}.csv' )

    ## calculate volume difference
    table1_mean_vol_diff = table1_ensemble_mean - table1_last_report_csv['Ensemble Mean Vol. (af)']
    table1_median_vol_diff = table1_ensemble_median - table1_last_report_csv['Ensemble Median Vol. (af)']


# create ensemble dataframe
table1_data = {
    'HUC6 Basin': table1_snodas['HUC6 Basin'],
    'HUC8 Basin': table1_snodas['HUC8 Subbasin'],
    'Ensemble Mean Vol. (af)': table1_ensemble_mean,
    'Ensemble Median Vol. (af)': table1_ensemble_median,
    'Ensemble Min. Vol. (af)': table1_ensemble_min,
    'Ensemble Max. Vol. (af)': table1_ensemble_max,
    'Min. Source': min_sources_str,
    'Max. Source': max_sources_str,
}

# only add change columns if applicable
if date_last_report != 'NA':
    table1_data[f'Mean Vol. Change since {date_last_report} (af)'] = table1_mean_vol_diff
    table1_data[f'Median Vol. Change since {date_last_report} (af)'] = table1_median_vol_diff

table1_ensemble = pd.DataFrame(table1_data)
table1_ensemble.to_csv(BASE_DIR / 'reports' / date_formatted / 'csv_tables' / f'table1_Ensemble_{date}.csv', index=False)

# save table 1 pdfs
src.tables_graphs.table1_reportlab(table1_snodas, data_source="SNODAS",
                                   date=date, last_report_date=date_last_report)
src.tables_graphs.table1_reportlab(table1_ua_swe, data_source="UA_SWE",
                                   date=date, last_report_date=date_last_report)
src.tables_graphs.table1_reportlab(table1_cu_swe, data_source="CU_SWE",
                                   date=date, last_report_date=date_last_report)
#src.tables_graphs.table1_reportlab(table1_era5, data_source="ERA5",
#                                   date=date)
src.tables_graphs.table1_reportlab(table1_ensemble, data_source="Ensemble",
                                   date=date, last_report_date=date_last_report)


#######################################################################

## table 2
table2_snodas = src.tables_graphs.generate_table2(raster=snodas_utm_unfilt,
                                                  data_source="SNODAS", date=date,
                                                  last_report_date=date_last_report)
table2_ua_swe = src.tables_graphs.generate_table2(raster=ua_swe_utm_unfilt,
                                                  data_source="UA_SWE", date=date,
                                                  last_report_date=date_last_report)
table2_cu_swe = src.tables_graphs.generate_table2(raster=cu_swe_utm_unfilt,
                                                  data_source="CU_SWE", date=date,
                                                  last_report_date=date_last_report)

## generate ensemble table
vals_table2 = np.vstack([
    table2_snodas['Estimated Volume (af)'].values,
    table2_ua_swe['Estimated Volume (af)'].values,
    table2_cu_swe['Estimated Volume (af)'].values
])

# ensemble mean
table2_ensemble_mean = np.mean([table2_snodas['Estimated Volume (af)'], table2_ua_swe['Estimated Volume (af)'], 
                         table2_cu_swe['Estimated Volume (af)']], 
                         axis=0)

# ensemble median
table2_ensemble_median = np.median([table2_snodas['Estimated Volume (af)'], table2_ua_swe['Estimated Volume (af)'], 
                         table2_cu_swe['Estimated Volume (af)']], 
                         axis=0)

# numeric min 
table2_ensemble_min = np.nanmin(vals_table2, axis=0)

# index of dataset producing the min
min_idx = [
    np.where(vals_table2[:, j] == table2_ensemble_min[j])[0].tolist()
    for j in range(vals_table2.shape[1])
]
# min source
min_sources_str = [
    ", ".join(sources[i] for i in idxs)
    for idxs in min_idx
]

# numeric max
table2_ensemble_max = np.nanmax(vals_table2, axis=0)

# index of dataset producing the max
max_idx = [
    np.where(vals_table2[:, j] == table2_ensemble_max[j])[0].tolist()
    for j in range(vals_table2.shape[1])
]
# max source
max_sources_str = [
    ", ".join(sources[i] for i in idxs)
    for idxs in max_idx
]

## difference calc
if date_last_report != 'NA':
    table2_last_report_csv = pd.read_csv(BASE_DIR / 'reports' / date_last_report / 'csv_tables' / f'table2_Ensemble_{date_last_report_unformatted}.csv' )

    ## calculate volume difference
    table2_mean_vol_diff = table2_ensemble_mean - table2_last_report_csv['Ensemble Mean Vol. (af)']
    table2_median_vol_diff = table2_ensemble_median - table2_last_report_csv['Ensemble Median Vol. (af)']


# create ensemble dataframe
table2_data = {
    'OSE Grouping': table2_snodas['OSE Grouping'],
    'HUC8 Basin': table2_snodas['HUC8 Subbasin'],
    'Ensemble Mean Vol. (af)': table2_ensemble_mean,
    'Ensemble Median Vol. (af)': table2_ensemble_median,
    'Ensemble Min. Vol. (af)': table2_ensemble_min,
    'Ensemble Max. Vol. (af)': table2_ensemble_max,
    'Min. Source': min_sources_str,
    'Max. Source': max_sources_str
}

# only add change columns if applicable
if date_last_report != 'NA':
    table2_data[f'Mean Vol. Change since {date_last_report} (af)'] = table2_mean_vol_diff
    table2_data[f'Median Vol. Change since {date_last_report} (af)'] = table2_median_vol_diff

table2_ensemble = pd.DataFrame(table2_data)
table2_ensemble.to_csv(BASE_DIR / 'reports' / date_formatted / 'csv_tables' / f'table2_Ensemble_{date}.csv', index=False)


# save table 2 pdfs
src.tables_graphs.table2_reportlab(table2_snodas, data_source="SNODAS",
                                   date=date, last_report_date=date_last_report)
src.tables_graphs.table2_reportlab(table2_ua_swe, data_source="UA_SWE",
                                   date=date, last_report_date=date_last_report)
src.tables_graphs.table2_reportlab(table2_cu_swe, data_source="CU_SWE",
                                   date=date, last_report_date=date_last_report)
src.tables_graphs.table2_reportlab(table2_ensemble, data_source="Ensemble",
                                   date=date, last_report_date=date_last_report)

###################################################################3

## table 3 (elevation bands)
table3_snodas = src.tables_graphs.generate_table3(raster=snodas_utm_unfilt,
                                                  data_source="SNODAS", date=date,
                                                  band_width=1000, save_csv=True,
                                                  last_report_date=date_last_report, calc_diff=True)
table3_ua_swe = src.tables_graphs.generate_table3(raster=ua_swe_utm_unfilt,
                                                  data_source="UA_SWE", date=date,
                                                  band_width=1000, save_csv=True,
                                                  last_report_date=date_last_report, calc_diff=True)
table3_cu_swe = src.tables_graphs.generate_table3(raster=cu_swe_utm_unfilt,
                                                  data_source="CU_SWE", date=date,
                                                  band_width=1000, save_csv=True,
                                                  last_report_date=date_last_report, calc_diff=True)

## generate ensemble table
## dataframes have different numbers of rows (different resolutions)
## need to index on elevation band, huc6, and huc8 basin to align dataframes
idx_cols = ['HUC6 Basin', 'HUC8 Subbasin', 'Elevation Band (ft.)']

t3_snodas = table3_snodas.set_index(idx_cols)
t3_ua_swe = table3_ua_swe.set_index(idx_cols)
t3_cu_swe = table3_cu_swe.set_index(idx_cols)

# --- SNODAS DEFINES ORDER ---
base_idx = t3_snodas.index

t3_ua_swe = t3_ua_swe.reindex(base_idx)
t3_cu_swe = t3_cu_swe.reindex(base_idx)

## stack values
vals_table3 = np.vstack([
    t3_snodas['Estimated Volume (af)'].values,
    t3_ua_swe['Estimated Volume (af)'].values,
    t3_cu_swe['Estimated Volume (af)'].values
])

# ensemble statistics
ensemble_mean = np.nanmean(vals_table3, axis=0)
ensemble_median = np.nanmedian(vals_table3, axis=0)
ensemble_min = np.nanmin(vals_table3, axis=0)
ensemble_max = np.nanmax(vals_table3, axis=0)

# get id of minimum value for each row
min_idx = [
    np.where(np.isclose(vals_table3[:, j], ensemble_min[j], equal_nan=False))[0].tolist()
    for j in range(vals_table3.shape[1])
]

max_idx = [
    np.where(np.isclose(vals_table3[:, j], ensemble_max[j], equal_nan=False))[0].tolist()
    for j in range(vals_table3.shape[1])
]

min_sources = [", ".join(sources[i] for i in idxs) for idxs in min_idx]
max_sources = [", ".join(sources[i] for i in idxs) for idxs in max_idx]

## ensemble data frame - maintain order
table3_ensemble = (
    pd.DataFrame(index=base_idx)
    .reset_index()
)

table3_ensemble['Ensemble Mean Vol. (af)'] = ensemble_mean
table3_ensemble['Ensemble Median Vol. (af)'] = ensemble_median
table3_ensemble['Ensemble Min. Vol. (af)'] = ensemble_min
table3_ensemble['Ensemble Max. Vol. (af)'] = ensemble_max
table3_ensemble['Min. Source'] = min_sources
table3_ensemble['Max. Source'] = max_sources

## difference calc since last report (if exists)
if date_last_report != 'NA':

    table3_last_report_csv = pd.read_csv(BASE_DIR / 'reports' / date_last_report / 'csv_tables' / f'table3_Ensemble_{date_last_report_unformatted}.csv')

    table3_ensemble[f'Mean Vol. Change since {date_last_report} (af)'] = (table3_ensemble['Ensemble Mean Vol. (af)'].values - table3_last_report_csv['Ensemble Mean Vol. (af)'].values)

    table3_ensemble[f'Median Vol. Change since {date_last_report} (af)'] = (table3_ensemble['Ensemble Median Vol. (af)'].values - table3_last_report_csv['Ensemble Median Vol. (af)'].values)

## save csv
table3_ensemble.to_csv(BASE_DIR / 'reports' / date_formatted / 'csv_tables' / f'table3_Ensemble_{date}.csv', index=False)



# save table 3 pdfs
src.tables_graphs.table3_reportlab(table3_snodas, data_source="SNODAS",
                                   date=date, last_report_date=date_last_report)
src.tables_graphs.table3_reportlab(table3_ua_swe, data_source="UA_SWE",
                                   date=date, last_report_date=date_last_report)
src.tables_graphs.table3_reportlab(table3_cu_swe, data_source="CU_SWE",
                                   date=date, last_report_date=date_last_report)
src.tables_graphs.table3_reportlab(table3_ensemble, data_source="Ensemble",
                                   date=date, last_report_date=date_last_report)

## table 3 for plots
table3_snodas_plotting = src.tables_graphs.generate_table3(raster=snodas_utm_unfilt,
                                                  data_source="SNODAS", date=date,
                                                  band_width=250, save_csv=False,
                                                  last_report_date=date_last_report, calc_diff=False)
table3_ua_swe_plotting = src.tables_graphs.generate_table3(raster=ua_swe_utm_unfilt,
                                                  data_source="UA_SWE", date=date,
                                                  band_width=250, save_csv=False,
                                                  last_report_date=date_last_report, calc_diff=False)
table3_cu_swe_plotting = src.tables_graphs.generate_table3(raster=cu_swe_utm_unfilt,
                                                  data_source="CU_SWE", date=date,
                                                  band_width=250, save_csv=False,
                                                  last_report_date=date_last_report, calc_diff=False)

## generate elevation plots 
## FIXME! Need to add condition to not generate plot if zero snow
src.tables_graphs.elevation_plots(snodas_table=table3_snodas_plotting,
                                  ua_swe_table=table3_ua_swe_plotting,
                                  cu_swe_table=table3_cu_swe_plotting,
                                  date=date)