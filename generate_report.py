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

#############################

## EDIT DATE HERE: (CU SWE data must exist for date, with filename 'data/CU_SWE/YYYYMMDD_raster.tif')
date = '20260322'

#############################

#date = datetime.today().strftime('%Y%m%d') # get today's date
#cu_swe_files = os.listdir("data/CU_SWE")
#cu_swe_dates = sorted([fname[:8] for fname in cu_swe_files])


# format date for folder names and figure captions
date_formatted = datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d")

## make report directories for current date
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


print(f"Generating figures for date: {date}")

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


## table 1
print(f"Generating table 1 for date: {date}")

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


#######################################################################

## table 2
print(f"Generating table 2 for date: {date}")

table2_snodas = src.tables_graphs.generate_table2(raster=snodas_utm_unfilt,
                                                  data_source="SNODAS", date=date,
                                                  last_report_date=date_last_report)
table2_ua_swe = src.tables_graphs.generate_table2(raster=ua_swe_utm_unfilt,
                                                  data_source="UA_SWE", date=date,
                                                  last_report_date=date_last_report)
table2_cu_swe = src.tables_graphs.generate_table2(raster=cu_swe_utm_unfilt,
                                                  data_source="CU_SWE", date=date,
                                                  last_report_date=date_last_report)

###################################################################3

## table 3 (elevation bands)
print(f"Generating table 3 for date: {date}")

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


## table 3 for elevation plots - band width set to 250 feet instead of 1000
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
print(f"Generating elevation density plots for date: {date}")
src.tables_graphs.elevation_plots(snodas_table=table3_snodas_plotting,
                                  ua_swe_table=table3_ua_swe_plotting,
                                  cu_swe_table=table3_cu_swe_plotting,
                                  date=date)


## generate ensemble tables
print(f"Generating ensemble tables for date: {date}")
src.tables_graphs.generate_ensemble_tables(table1_snodas, table1_ua_swe, table1_cu_swe, 1, date, date_last_report)
src.tables_graphs.generate_ensemble_tables(table2_snodas, table2_ua_swe, table2_cu_swe, 2, date, date_last_report)
src.tables_graphs.generate_ensemble_tables(table3_snodas, table3_ua_swe, table3_cu_swe, 3, date, date_last_report)


print(f"Done generating SWE figures and tables for date: {date}")