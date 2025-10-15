import os
from datetime import datetime
import rioxarray as rxr
import xarray as xr
import numpy as np
import pandas as pd
import importlib
import src.download_data
importlib.reload(src.download_data)
import src.reproject
importlib.reload(src.reproject)
import src.plotting
importlib.reload(src.plotting)
import src.tables_graphs
importlib.reload(src.tables_graphs)


#from src.download_data import download_snodas
#from src.download_data import download_uaswe
#from src.download_data import download_era5

#from src.reproject import load_shapefiles
#date = datetime.today().strftime('%Y%m%d') # get today's date
cu_swe_files = os.listdir("data/CU_SWE")
cu_swe_dates = [fname[:8] for fname in cu_swe_files]
#date = '20250401'

# download data
'''
src.download_data.download_snodas(date)
src.download_data.download_uaswe(date)
src.download_data.download_era5(date)
'''

# load shapefiles

shapefiles = src.reproject.load_shapefiles()
huc6 = shapefiles['huc6']
huc8 = shapefiles['huc8']
OSE = shapefiles['OSE']
state_boundaries = shapefiles['state_boundaries']
nm_cities = shapefiles['nm_cities']

for date in cu_swe_dates:
    print(f"Generating figures for date {date}")

    # load UTM rasters
    snodas_utm = src.reproject.load_snodas(date, filter=True)
    ua_swe_utm = src.reproject.load_uaswe(date, reproject=True, filter=True)
    cu_swe_utm = src.reproject.load_cuswe(date, reproject=True, filter=True)
    era5_utm = src.reproject.load_era5(date, reproject=True, filter=True)

    # load lat lon rasters
    ua_swe_unproj = src.reproject.load_uaswe(date, reproject=False, filter=True)
    cu_swe_unproj = src.reproject.load_cuswe(date, reproject=False, filter=True)
    era5_unproj = src.reproject.load_era5(date, reproject=False, filter=True)

    ## generate average raster
    # resample to 1km to take average
    ua_swe_1km = ua_swe_unproj.rio.reproject_match(snodas_utm, resampling = 1) # 1 = bilinear resampling, 0 = nearest neighbor
    cu_swe_1km = cu_swe_unproj.rio.reproject_match(snodas_utm, resampling = 1)
    era5_1km = era5_unproj.rio.reproject_match(snodas_utm, resampling = 1)

    # stack rasters and take mean
    raster_list = []
    raster_list.append(snodas_utm)
    raster_list.append(ua_swe_1km)
    raster_list.append(cu_swe_1km)
    raster_list.append(era5_1km)

    raster_stack = xr.concat(raster_list, dim="layer")
    # count non nan values at each pixel
    valid_count = raster_stack.notnull().sum(dim="layer")
    del(ua_swe_1km, cu_swe_1km, era5_1km, raster_list)

    # calculate avg and std dev and mask by valid count
    average = raster_stack.mean(dim="layer", skipna=True)
    average = average.where(valid_count >= 3)
    std_dev = raster_stack.std(dim="layer", skipna = True)
    std_dev = std_dev.where(valid_count >= 3)
    del(raster_stack)

    ## create study area overview plots
    max_value_cbar = src.plotting.get_max_value(snodas = snodas_utm, cu_swe = cu_swe_utm, ua_swe = ua_swe_utm,
                                era5 = era5_utm, average = average)

    src.plotting.plot_study_area(data = snodas_utm, data_source = "SNODAS",
                                date = date, max_value_cbar = max_value_cbar)
    src.plotting.plot_study_area(data = ua_swe_utm, data_source = "UA_SWE",
                                date = date, max_value_cbar = max_value_cbar)
    src.plotting.plot_study_area(data = cu_swe_utm, data_source = "CU_SWE",
                                date = date, max_value_cbar = max_value_cbar)
    src.plotting.plot_study_area(data = era5_utm, data_source = "ERA5",
                                date = date, max_value_cbar = max_value_cbar)
    src.plotting.plot_study_area(data = average, data_source = "Average",
                                date = date, max_value_cbar = max_value_cbar)
    src.plotting.plot_study_area(data = std_dev, data_source = "Std_Dev",
                                date = date, max_value_cbar = max_value_cbar)


## generate statistics tables
snodas_utm_unfilt = src.reproject.load_snodas(date, filter=False)
ua_swe_utm_unfilt = src.reproject.load_uaswe(date, reproject=True, filter=False)
cu_swe_utm_unfilt = src.reproject.load_cuswe(date, reproject=True, filter=False)
era5_utm_unfilt = src.reproject.load_era5(date, reproject=True, filter=False)


## table 1
table1_snodas = src.tables_graphs.generate_table1(snodas_utm_unfilt)
table1_ua_swe = src.tables_graphs.generate_table1(ua_swe_utm_unfilt)
table1_cu_swe = src.tables_graphs.generate_table1(cu_swe_utm_unfilt)
table1_era5 = src.tables_graphs.generate_table1(era5_utm_unfilt)

## generate ensemble table
ensemble_mean = np.mean([table1_snodas['Estimated Volume (af)'], table1_ua_swe['Estimated Volume (af)'], 
                         table1_cu_swe['Estimated Volume (af)'], table1_era5['Estimated Volume (af)']], 
                         axis=0)
ensemble_median = np.median([table1_snodas['Estimated Volume (af)'], table1_ua_swe['Estimated Volume (af)'], 
                         table1_cu_swe['Estimated Volume (af)'], table1_era5['Estimated Volume (af)']], 
                         axis=0)
ensemble_std = np.std([table1_snodas['Estimated Volume (af)'], table1_ua_swe['Estimated Volume (af)'], 
                         table1_cu_swe['Estimated Volume (af)'], table1_era5['Estimated Volume (af)']], 
                         axis=0)
ensemble_min = np.min([table1_snodas['Estimated Volume (af)'], table1_ua_swe['Estimated Volume (af)'], 
                         table1_cu_swe['Estimated Volume (af)'], table1_era5['Estimated Volume (af)']], 
                         axis=0)
ensemble_max = np.max([table1_snodas['Estimated Volume (af)'], table1_ua_swe['Estimated Volume (af)'], 
                         table1_cu_swe['Estimated Volume (af)'], table1_era5['Estimated Volume (af)']], 
                         axis=0)

table1_ensemble = pd.DataFrame({'HUC6 Basin': table1_snodas['HUC6 Basin'],
                                'HUC8 Basin': table1_snodas['HUC8 Subbasin'],
                                'Ensemble Mean Vol. (af)': ensemble_mean,
                                'Ensemble Median Vol (af)': ensemble_median,
                                'Ensemble SD Vol. (af)': ensemble_std,
                                'Ensemble Min. Vol. (af)': ensemble_min,
                                'Ensemble Max. Vol. (af)': ensemble_max})

# save table 1 pdfs
src.tables_graphs.table1_reportlab(table1_snodas, data_source="SNODAS",
                                   date=date)
src.tables_graphs.table1_reportlab(table1_ua_swe, data_source="UA_SWE",
                                   date=date)
src.tables_graphs.table1_reportlab(table1_cu_swe, data_source="CU_SWE",
                                   date=date)
src.tables_graphs.table1_reportlab(table1_era5, data_source="ERA5",
                                   date=date)
src.tables_graphs.table1_reportlab(table1_ensemble, data_source="Ensemble",
                                   date=date)