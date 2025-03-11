# -*- coding: utf-8 -*-
"""
Created on Tue Mar  4 16:37:50 2025

@author: blats
"""

## load libraries
import rasterio
from rasterio.plot import show
import matplotlib.pyplot as plt
import geopandas as gpd
import numpy as np
from rasterio.mask import mask
from rasterio.features import rasterize
from osgeo import gdal
from rasterio.windows import Window

## set date
date = "20250302"

## read raster file
snodas_file = "SNODAS_Data/us_ssmv11034tS__T0001TTNATS" + date + "05HP001.tif"

snodas_rast = rasterio.open(snodas_file)
snodas_rast.crs

raster_shape = (snodas_rast.height, snodas_rast.width)
raster_transform = snodas_rast.transform


## read watershed boundary shapefile
HUC8 = gpd.read_file("Shapefiles/WBDHU8_RG/WBDHU8_RG.shp")
print(HUC8)
list(HUC8)
HUC8['Name']
rgh = HUC8.loc[HUC8['Name'] == "Rio Grande Headwaters"]
HUC8.plot()

## check if crs are same for raster and shapefile
snodas_rast.crs == HUC8.crs

## Plot polygon over raster
fig, ax = plt.subplots(figsize=(10, 10))
show(snodas_rast, ax = ax)
HUC8.plot(ax = ax, edgecolor="red", facecolor="none", linewidth=1)
plt.show()
plt.close()


## crop raster to polygon
out_image, out_transform = mask(snodas_rast, rgh.geometry, crop=True)
out_image
show(out_image)

## extract mean from polygon
mean_value = np.nanmean(out_image[out_image != snodas_rast.nodata]) / 1000
mean_value

swe_volume = mean_value * (float(rgh['AreaSqKm'])*1000000)
swe_volume

swe_af = swe_volume * 0.000810714
swe_af

## check against UA SWE value from QGIS
(157.6090425531915/1000) * (float(rgh['AreaSqKm'])*1000000) * 0.000810714


###############################################3
bbox = HUC8.total_bounds
idx = [0, 3, 2, 1]
bbox = bbox[idx]
ds = gdal.Open(snodas_file)
ds = gdal.Translate('SNODAS_Data/new.tif', ds, projWin = bbox)
ds = None

## read cropped file
snodas_cropped = rasterio.open("SNODAS_Data/new.tif")
snodas_cropped.crs
show(snodas_cropped)

## Plot polygon over cropped raster
fig, ax = plt.subplots(figsize=(10, 10))
show(snodas_cropped, ax = ax)
HUC8.plot(ax = ax, edgecolor="red", facecolor="none", linewidth=1)
plt.show()
plt.close()








