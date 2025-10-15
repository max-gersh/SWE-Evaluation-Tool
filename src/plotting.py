import numpy as np
import pandas as pd
import geopandas as gpd
import xarray as xr
import rasterio as rio
import rioxarray as rxr
import matplotlib.pyplot as plt
from glob import glob
import re
import matplotlib.colors as mcolors
import contextily as cx
import matplotlib.patheffects as PathEffects

from datetime import datetime
from shapely.geometry import Point

from pathlib import Path
import os

import importlib

import src.reproject
importlib.reload(src.reproject)

from src import BASE_DIR

# load shapefiles
shapefiles = src.reproject.load_shapefiles()
huc6 = shapefiles['huc6']
huc8 = shapefiles['huc8']
OSE = shapefiles['OSE']
state_boundaries = shapefiles['state_boundaries']
nm_cities = shapefiles['nm_cities']

def get_max_value(snodas, cu_swe, ua_swe, era5, average):
    bounds = huc6.total_bounds
    xpad = 100000
    ypad_top = 100000
    ypad_bottom = 50000
    bounds_padded = [bounds[0]-xpad, bounds[1]-ypad_bottom, bounds[2]+xpad, bounds[3]+ypad_top]

    # clip rasters
    clipped_snodas = snodas.where(snodas>=0).rio.clip_box(*bounds_padded) 
    clipped_cu_swe = cu_swe.where(cu_swe>=0).rio.clip_box(*bounds_padded) 
    clipped_ua_swe = ua_swe.where(ua_swe>=0).rio.clip_box(*bounds_padded) 
    clipped_era5 = era5.where(era5>=0).rio.clip_box(*bounds_padded) 
    clipped_average = average.where(average>=0).rio.clip_box(*bounds_padded) 

    # get 98th percent for each raster
    perc_max_snodas = np.nanpercentile(clipped_snodas, 98)
    perc_max_cu_swe = np.nanpercentile(clipped_cu_swe, 98)
    perc_max_ua_swe = np.nanpercentile(clipped_ua_swe, 98)
    perc_max_era5 = np.nanpercentile(clipped_era5, 98)
    perc_max_average = np.nanpercentile(clipped_average, 98)

    # get max value
    max_swe_val = np.max([perc_max_snodas, perc_max_cu_swe, perc_max_ua_swe, perc_max_era5, 
                          perc_max_average])
    
    return(max_swe_val)


def plot_study_area(data, data_source, date, max_value_cbar):

    bounds = huc6.total_bounds
    xpad = 100000
    ypad_top = 100000
    ypad_bottom = 50000
    bounds_padded = [bounds[0]-xpad, bounds[1]-ypad_bottom, bounds[2]+xpad, bounds[3]+ypad_top]
    clipped_data = data.where(data>=0).rio.clip_box(*bounds_padded) 
    #clipped_data = clipped_data.where(clipped_data > 1, np.nan)


    ## percentile for colorbar
    if data_source == "Std_Dev":
        perc_max = np.nanpercentile(clipped_data, 100)
    else:    
        perc_max = max_value_cbar

    ## manually assign OSE colors
    custom_colors = ["#FFAA00", "#018571", "#E6E600", "#a6611a"]
    custom_cmap = mcolors.ListedColormap(custom_colors)

    # Plot
    fig, ax = plt.subplots(figsize=(6,5))
    clipped_data.plot(ax=ax, cmap='Blues', vmax = perc_max)
    #clipped_data.plot(ax=ax, cmap='Blues')
    cbar = ax.collections[-1].colorbar
    cbar.set_label('SWE [in]', fontsize=16, labelpad=14)
    cbar.ax.tick_params(labelsize=12)

    # source = cx.providers.CartoDB.Positron
    #source = cx.providers.Esri.WorldImagery
    cx.add_basemap(ax, crs=clipped_data.rio.crs, source = cx.providers.Esri.WorldImagery, 
                attribution_size=0)
    state_boundaries.plot(color = 'None',
                        edgecolor='black',
                        linewidth=0.5,
                        ax=ax,
                        linestyle=(0, (5, 10)))
    ## add state labels
    dx_state = [-240000, 0, -295000, 0]
    dy_state = [280000, 0, -200000, 0]
    for idx, row in state_boundaries.iterrows():
        label_text = row["STUSPS"]
        if label_text in ["UT", "AZ"]:
            label_text = ""

        centroid = row.geometry.centroid
        ax.text(centroid.x + dx_state[idx], centroid.y + dy_state[idx], label_text, #row["Name"],
                fontsize=7, color="black", ha="center", va="center")

    ## add Albuquerque and Santa Fe
    nm_cities.plot(ax=ax, marker='o', markersize=5, color='black')
    dx_city = [-30000, -45000]
    dy_city = [-17500, -17500]
    for idx, row in nm_cities.iterrows():
        label_text = row["NAME"]
        centroid = row.geometry
        ax.text(centroid.x + dx_city[idx], centroid.y + dy_city[idx], label_text,
                fontsize=6, color="black", ha="center", va="center")

    ## add huc6 polygons
    huc6.plot(color='None',
                        edgecolor='black',
                        linewidth=1.1,
                        ax=ax)

    ## add labels to HUC6 basins
    dx = [125000, -145000, 150000]
    dy = [80000, 25000, 0]
    label_text = ['Rio Grande\nHeadwaters', 'Upper\nRio Grande', 
                'Rio Grande\nElephant\nButte']
    for idx, row in huc6.iterrows():
        #label_text = row["Name"].replace(" ", "\n")

        centroid = row.geometry.centroid
        ax.text(centroid.x + dx[idx], centroid.y + dy[idx], label_text[idx], #row["Name"],
                fontsize=7, color="black", ha="center", va="center",
                path_effects=[PathEffects.withStroke(linewidth=3, foreground="white")])

    ## add OSE polygons
    ## dotted lines so overlapping boundaries are visible
    OSE.plot(column='Name',  
            #cmap='turbo',
            cmap = custom_cmap,
            facecolor='none', 
            edgecolor=None, 
            linewidth=0.9,  
            legend=True,
            legend_kwds={'fontsize': 8},
            ax=ax,
            alpha=1,
            linestyle="-.")
            
    # convert axes from m to km
    m2km = lambda x, _: f'{x/1000:g}'
    ax.xaxis.set_major_formatter(m2km)
    ax.yaxis.set_major_formatter(m2km)
    ax.locator_params(axis="x", nbins=2)
    ax.locator_params(axis="y", nbins=4)
    #ax.ticklabel_format(style='sci', axis='x', scilimits=(0,0)) 
    ax.set_xlabel('Easting [km]')
    ax.set_ylabel('Northing [km]')
    ax.set_title(f'{data_source} SWE {date}')
    # add INSTAAR credit
    ax.text(1.05, 0.5, 'Credit: Institute of Arctic and Alpine Research', rotation=90, 
            va='center', ha='center', transform=ax.transAxes, fontsize=8)
    # change legend position
    legend = ax.get_legend()
    if legend:
        legend.set_bbox_to_anchor((0.5, -0.25)) # move legend below plot
        legend.set_loc("center")

    #plt.show()
    out_file = BASE_DIR / 'figs_for_Max' / f'figure1_{data_source}_{date}.png'
    plt.savefig(out_file, dpi=300, bbox_inches='tight')
    plt.close()