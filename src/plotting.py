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

import pickle

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

## manually assign OSE colors
custom_colors = ["#FFAA00", "#018571", "#E6E600", "#a6611a"]
custom_cmap = mcolors.ListedColormap(custom_colors)

def get_max_value(snodas, cu_swe, ua_swe, average):
    bounds = huc6.total_bounds
    xpad = 100000
    ypad_top = 100000
    ypad_bottom = 50000
    bounds_padded = [bounds[0]-xpad, bounds[1]-ypad_bottom, bounds[2]+xpad, bounds[3]+ypad_top]

    # clip rasters
    clipped_snodas = snodas.where(snodas>=0).rio.clip_box(*bounds_padded) 
    clipped_cu_swe = cu_swe.where(cu_swe>=0).rio.clip_box(*bounds_padded) 
    clipped_ua_swe = ua_swe.where(ua_swe>=0).rio.clip_box(*bounds_padded) 
    #clipped_era5 = era5.where(era5>=0).rio.clip_box(*bounds_padded) 
    clipped_average = average.where(average>=0).rio.clip_box(*bounds_padded) 

    # get 98th percent for each raster
    perc_max_snodas = np.nanpercentile(clipped_snodas, 98)
    perc_max_cu_swe = np.nanpercentile(clipped_cu_swe, 98)
    perc_max_ua_swe = np.nanpercentile(clipped_ua_swe, 98)
    #perc_max_era5 = np.nanpercentile(clipped_era5, 98)
    perc_max_average = np.nanpercentile(clipped_average, 98)

    # get max value
    max_swe_val = np.max([perc_max_snodas, perc_max_cu_swe, perc_max_ua_swe, 
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
    out_dir_date = datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d")
    out_file = BASE_DIR / "reports" / out_dir_date / "figures" / 'swe_maps' / f'overview_map_{data_source}_{date}.png'
    plt.savefig(out_file, dpi=300, bbox_inches='tight')
    plt.close()

    ##########################################

    ## plot subbasins
    for idx, basin in huc6.iterrows():
        bounds = basin.geometry.bounds
        swe_basin = clipped_data.where(clipped_data>=0).rio.clip_box(*bounds)
        ## percentile for colorbar
        perc_max = np.nanpercentile(swe_basin, 98)

        huc8_basins = huc8.loc[huc8['HUC6 Basin'] == basin['Name']]
        #print(huc8_basins)

        #swe_basin = clipped_data.rio.clip([basin.geometry])
            
        ## plot clipped polygon
        f, ax = plt.subplots()
        #swe_basin.plot(cmap="Blues", ax=ax)
        swe_basin.plot(ax=ax, cmap='Blues', vmax = perc_max)
        cbar = ax.collections[-1].colorbar
        cbar.set_label('SWE [in]', fontsize=16, labelpad=14)
        cbar.ax.tick_params(labelsize=12)

        cx.add_basemap(ax, crs=clipped_data.rio.crs, source = cx.providers.Esri.WorldImagery, attribution_size=0)
        #cx.add_basemap(ax, crs=clipped_data.rio.crs)

        gpd.GeoSeries(basin.geometry).boundary.plot(ax=ax, edgecolor="black", linewidth=1.5)
        huc8_basins.plot(color='None',
                        edgecolor='black',
                        linewidth=0.8,
                        ax=ax)
        ## add huc8 polygon labels
        
        for idx, row in huc8_basins.iterrows():
            label_text = row["Name"].replace("-", " ")
            label_text = label_text.replace(" ", "\n")

            centroid = row.geometry.centroid
            ax.text(centroid.x, centroid.y, label_text, #row["Name"],
                    fontsize=6, color="black", ha="center", va="center",
                    path_effects=[PathEffects.withStroke(linewidth=3, foreground="white")])
                    

        m2km = lambda x, _: f'{x/1000:g}'
        ax.xaxis.set_major_formatter(m2km)
        ax.yaxis.set_major_formatter(m2km)
        #ax.locator_params(axis="x", nbins=3)
        #ax.locator_params(axis="y", nbins=3)
        plt.gca().xaxis.set_major_locator(plt.MaxNLocator(3))
        plt.gca().yaxis.set_major_locator(plt.MaxNLocator(3))
        #ax.ticklabel_format(style='sci', axis='x', scilimits=(0,0)) 
        ax.set_xlabel('Easting [km]')
        ax.set_ylabel('Northing [km]')
        ax.set_title(f'{data_source} SWE Overview ' + basin['Name'])
        ax.text(1.05, 0.5, 'Credit: Institute of Arctic and Alpine Research', rotation=90, 
                va='center', ha='center', transform=ax.transAxes, fontsize=8)
        #plt.show()
        out_file_basin = BASE_DIR / "reports" / out_dir_date / "figures" / "swe_maps" / f'{basin['Name']}_map_{data_source}_{date}.png'
        plt.savefig(out_file_basin, dpi=300, bbox_inches='tight')
        plt.close()

# difference plot for study area
def plot_study_area_diff(raster_current, data_source, date, last_report_date):

    report_date_formatted = datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d")
    last_report_date_unformatted = datetime.strptime(last_report_date, "%Y-%m-%d").strftime("%Y%m%d")
    pkl_last_filename = BASE_DIR / "reports" / last_report_date / "pkl" / f"{data_source}_utm_{last_report_date_unformatted}.pkl"
    with open(pkl_last_filename, "rb") as f:
        raster_last = pickle.load(f)

    ## get huc6 bounds for clipping rasters
    bounds = huc6.total_bounds
    xpad = 100000
    ypad_top = 100000
    ypad_bottom = 50000
    bounds_padded = [bounds[0]-xpad, bounds[1]-ypad_bottom, bounds[2]+xpad, bounds[3]+ypad_top]

    ## clip current and last raster to bounds
    raster_current_clipped = raster_current.rio.clip_box(*bounds_padded)
    raster_current_clipped = raster_current_clipped.fillna(0)
    raster_last_clipped = raster_last.rio.clip_box(*bounds_padded)
    raster_last_clipped = raster_last_clipped.fillna(0)
    
    ## create difference raster
    swe_diff = raster_current_clipped - raster_last_clipped
    #swe_diff = swe_diff.where(swe_diff != 0, np.nan)
    ## mask only where BOTH inputs are zero
    mask = (raster_current_clipped == 0) & (raster_last_clipped == 0)
    swe_diff = swe_diff.where(~mask, np.nan)

    ## get min and max values for colorbar
    #swe_min = -np.nanmax(np.abs(swe_diff))
    #swe_max = np.nanmax(np.abs(swe_diff))
    swe_max = np.nanpercentile(np.abs(swe_diff), 98)
    swe_min = -swe_max


    # Plot
    fig, ax = plt.subplots(figsize=(6,5))
    swe_diff.plot(ax=ax, cmap='RdBu', vmin = swe_min, vmax = swe_max)
    cbar = ax.collections[-1].colorbar
    cbar.set_label('Change in SWE [in]', fontsize=16, labelpad=14)
    cbar.ax.tick_params(labelsize=12)
    cx.add_basemap(ax, crs=raster_current_clipped.rio.crs, source = cx.providers.Esri.WorldImagery, 
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
    #label_text = ['Santa Fe', 'ABQ']
    for idx, row in nm_cities.iterrows():
        label_text = row["NAME"]

        centroid = row.geometry
        ax.text(centroid.x + dx_city[idx], centroid.y + dy_city[idx], label_text,
                fontsize=6, color="black", ha="center", va="center")

    #cx.add_basemap(ax, crs=clipped_data.rio.crs)
    ## add huc6 polygons
    huc6.plot(color='None',
                        edgecolor='black',
                        linewidth=1.1,
                        ax=ax)

    ## add polygon labels
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

    ## plot with outlined polygons
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
            

    m2km = lambda x, _: f'{x/1000:g}'
    ax.xaxis.set_major_formatter(m2km)
    ax.yaxis.set_major_formatter(m2km)
    ax.locator_params(axis="x", nbins=2)
    ax.locator_params(axis="y", nbins=4)
    #ax.ticklabel_format(style='sci', axis='x', scilimits=(0,0)) 
    ax.set_xlabel('Easting [km]')
    ax.set_ylabel('Northing [km]')
    ax.set_title(f'{data_source} SWE Difference {last_report_date} to {report_date_formatted}')

    ax.text(1.05, 0.5, 'Credit: Institute of Arctic and Alpine Research', rotation=90, 
            va='center', ha='center', transform=ax.transAxes, fontsize=8)

    legend = ax.get_legend()
    if legend:
        legend.set_bbox_to_anchor((0.5, -0.25)) # move legend below plot
        legend.set_loc("center")

    
    ## save plot
    out_file = BASE_DIR / "reports" / report_date_formatted / "figures" / "swe_difference_maps" / f'overview_difference_map_{data_source}_{date}.png'
    plt.savefig(out_file, dpi=300, bbox_inches='tight')
    plt.close()

    #####################################

    ## plot difference for each subbasin
    for idx, basin in huc6.iterrows():
        # clip raster to basin bounds
        bounds = basin.geometry.bounds
        swe_basin = raster_current_clipped.where(raster_current_clipped>=0).rio.clip_box(*bounds)
        swe_basin_last = raster_last_clipped.where(raster_last_clipped>=0).rio.clip_box(*bounds) # clip data from last report

        # calculate SWE difference for basin
        swe_basin_diff = swe_basin - swe_basin_last
        #swe_basin_diff = swe_basin_diff.where(swe_basin_diff != 0, np.nan)
        ## mask only where BOTH inputs are zero
        mask = (swe_basin == 0) & (swe_basin_last == 0)
        swe_basin_diff = swe_basin_diff.where(~mask, np.nan)

        # get min and max for colorbar
        p98 = np.nanpercentile(np.abs(swe_basin_diff), 98)
        swe_min = -p98
        swe_max = p98
        
        huc8_basins = huc8.loc[huc8['HUC6 Basin'] == basin['Name']]
        #print(huc8_basins)

        #swe_basin = clipped_data.rio.clip([basin.geometry])
            
        ## plot clipped polygon
        f, ax = plt.subplots()
        #swe_basin.plot(cmap="Blues", ax=ax)
        swe_basin_diff.plot(ax=ax, cmap='RdBu', vmin=swe_min, vmax=swe_max)
        cbar = ax.collections[-1].colorbar
        cbar.set_label('Change in SWE [in]', fontsize=16, labelpad=14)
        cbar.ax.tick_params(labelsize=12)

        cx.add_basemap(ax, crs=swe_basin_diff.rio.crs, source = cx.providers.Esri.WorldImagery, attribution_size=0)
        #cx.add_basemap(ax, crs=clipped_data.rio.crs)

        gpd.GeoSeries(basin.geometry).boundary.plot(ax=ax, edgecolor="black", linewidth=1.5)
        huc8_basins.plot(color='None',
                        edgecolor='black',
                        linewidth=0.8,
                        ax=ax)
        ## add huc8 polygon labels
        
        for idx, row in huc8_basins.iterrows():
            label_text = row["Name"].replace("-", " ")
            label_text = label_text.replace(" ", "\n")

            centroid = row.geometry.centroid
            ax.text(centroid.x, centroid.y, label_text, #row["Name"],
                    fontsize=6, color="black", ha="center", va="center",
                    path_effects=[PathEffects.withStroke(linewidth=3, foreground="white")])
                    

        m2km = lambda x, _: f'{x/1000:g}'
        ax.xaxis.set_major_formatter(m2km)
        ax.yaxis.set_major_formatter(m2km)
        #ax.locator_params(axis="x", nbins=3)
        #ax.locator_params(axis="y", nbins=3)
        plt.gca().xaxis.set_major_locator(plt.MaxNLocator(3))
        plt.gca().yaxis.set_major_locator(plt.MaxNLocator(3))
        #ax.ticklabel_format(style='sci', axis='x', scilimits=(0,0)) 
        ax.set_xlabel('Easting [km]')
        ax.set_ylabel('Northing [km]')
        ax.set_title(f'{data_source} SWE Change ' + basin['Name'])
        ax.text(1.05, 0.5, 'Credit: Institute of Arctic and Alpine Research', rotation=90, 
                va='center', ha='center', transform=ax.transAxes, fontsize=8)
        #plt.show()
        out_file_basin = BASE_DIR / "reports" / report_date_formatted / "figures" / "swe_difference_maps" / f'{basin['Name']}_difference_map_{data_source}_{date}.png'
        plt.savefig(out_file_basin, dpi=300, bbox_inches='tight')
        plt.close()