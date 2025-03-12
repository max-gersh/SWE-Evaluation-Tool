# -*- coding: utf-8 -*-
"""
Created on Wed Mar 12 14:33:46 2025

@author: blats
"""

import numpy as np
import pandas as pd
import geopandas as gpd
import xarray as xr
import rasterio as rio
import rioxarray as rxr
import matplotlib.pyplot as plt
from glob import glob
import re

## set date
date = "20230216"

## read raster file
snodas_file = "data/SNODAS/SNODAS_SWE_" + date + ".tif"
data = rxr.open_rasterio(snodas_file, masked = True).squeeze()

## read shapefiles
OSE = gpd.read_file("data/Shapefiles/OSE_Basin_Designations/SubBasins_Dissolve.shp")
OSE = OSE.to_crs(4326)
OSE.crs
HUC8 = gpd.read_file("data/Shapefiles/WBDHU8_RG/WBDHU8_RG.shp")
HUC8 = HUC8.drop(HUC8.index[72]) #remove Rio Salado polygon in Mexico
HUC6 = gpd.read_file("data/Shapefiles/WBDHU6_RG/WBDHU6_RG.shp")

## filter data to polygons of interest
HUC8['Name'].unique()
HUC8_polys = ['Rio Grande Headwaters', 'Alamosa-Trinchera',
              'San Luis', 'Saguache',
              'Conejos', 'Upper Rio Grande',
              'Rio Chama', 'Rio Grande-Santa Fe',
              'Jemez', 'Rio Grande-Albuquerque',
              'Arroyo Chico', 'North Plains',
              'Rio San Jose', 'Plains of San Agustin',
              'Rio Salado', 'Jornada Del Muerto',
              'Elephant Butte Reservoir', 'Rio Puerco']
HUC8 = HUC8[HUC8['Name'].isin(HUC8_polys)]

## confirm CRS are all equal
OSE.crs == HUC8.crs == HUC6.crs == data.rio.crs

## clip raster to HUC8 extent
bbox = HUC8.total_bounds
clipped_data = data.rio.clip_box(*bbox)


f, ax = plt.subplots()
clipped_data.plot(cmap="Blues",
                 ax=ax)
HUC8.plot(color='None',
                    edgecolor='red',
                    linewidth=1,
                    ax=ax)
plt.show()

###################################################

## SWE calc no reprojection
poly_clip = clipped_data.rio.clip([HUC8.iloc[1].geometry], HUC8.crs)

## plot clipped polygon
f, ax = plt.subplots()
poly_clip.plot(cmap="Blues",
                 ax=ax)
plt.show()

## calc SWE
mean_value = np.nanmean(poly_clip) / 1000
swe_volume = mean_value * (HUC8.iloc[1].AreaSqKm*1000000)
swe_volume

####################################################3

## SWE calc with reprojection
aea_crs = "EPSG:5070"
data_reprojected = clipped_data.rio.reproject(
    aea_crs, 
    resampling=rio.enums.Resampling.bilinear)  

HUC8_aea = HUC8.to_crs(5070)


## plot clipped raster extent
f, ax = plt.subplots()
data_reprojected.plot(cmap="Blues",
                 ax=ax)
HUC8_aea.plot(color='None',
                    edgecolor='red',
                    linewidth=1,
                    ax=ax)
plt.show()

## clip AEA raster to polygon 1
poly_clip_aea = data_reprojected.rio.clip([HUC8_aea.iloc[1].geometry], HUC8_aea.crs)

## plot clipped polygon
f, ax = plt.subplots()
poly_clip_aea.plot(cmap="Blues",
                 ax=ax)
plt.show()


pixel_size_x, pixel_size_y = poly_clip_aea.rio.resolution()
pixel_area = abs(pixel_size_x * pixel_size_y)

total_swe = (np.nansum(poly_clip_aea.values) / 1000) * pixel_area
total_swe





