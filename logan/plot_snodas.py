# -*- coding: utf-8 -*-
"""
Created on Mon Mar 10 15:33:16 2025

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
data.shape
data.rio.crs
data.rio.nodata

## get min and max values
print("the minimum raster value is: ", np.nanmin(data.values))
print("the maximum raster value is: ", np.nanmax(data.values))

# Plot the raster data
f, ax = plt.subplots(figsize=(10, 6))
data.plot(cmap="Greys_r",
                 ax=ax)
ax.set_title("SNODAS SWE " + date)
ax.set_axis_off()
plt.show()

## read shapeifles
OSE = gpd.read_file("data/Shapefiles/OSE_Basin_Designations/SubBasins_Dissolve.shp")
OSE = OSE.to_crs(4326)
OSE.crs
HUC8 = gpd.read_file("data/Shapefiles/WBDHU8_RG/WBDHU8_RG.shp")
HUC6 = gpd.read_file("data/Shapefiles/WBDHU6_RG/WBDHU6_RG.shp")

## check if crs are equal
OSE.crs
HUC8.crs
HUC6.crs
OSE.crs == HUC8.crs == HUC6.crs == data.rio.crs

## select HUC6 polygons of interest
list(HUC6.columns.values)
HUC6['Name'].unique()

## select first 3 rows
HUC6 = HUC6.head(3)
HUC6['Name'].unique()

## select OSE polygons of interest
OSE['SubBasin'].unique()
OSE = OSE.loc[OSE['SubBasin'] != 'San Juan River Basin']


## clip raster to HUC8 extent
bbox = HUC6.total_bounds
clipped_data = data.rio.clip_box(*bbox)

# Plot the raster data
f, ax = plt.subplots()
clipped_data.plot(cmap="Blues",
                 ax=ax)
HUC6.plot(color='None',
                    edgecolor='grey',
                    linewidth=1,
                    ax=ax)
'''
## plot with filled polygons
OSE.plot(column='SubBasin',  
         cmap='Reds',
         edgecolor='None',
         linewidth=0.5,
         legend=True,
         ax=ax,
         alpha = 0.5)
'''
## plot with outlined polygons
## dotted lines so overlapping boundaries are visible
OSE.plot(column='SubBasin',  
         cmap='Reds', 
         facecolor='none', 
         edgecolor=None, 
         linewidth=0.8,  
         legend=True,  
         ax=ax,
         alpha=1,
         linestyle="-.")



ax.set_title("SNODAS SWE " + date)
ax.set_axis_off()
legend = ax.get_legend()
if legend:
    legend.set_bbox_to_anchor((0.5, -0.2)) # move legend below plot
    legend.set_loc("center")

plt.show()

