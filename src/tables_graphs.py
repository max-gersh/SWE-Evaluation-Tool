import numpy as np
import pandas as pd
import geopandas as gpd
import xarray as xr
import rasterio as rio
import rioxarray as rxr
import matplotlib.pyplot as plt
from glob import glob
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, Spacer

from datetime import datetime
from pathlib import Path
import os

import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

#import importlib
import src.reproject
#import src.tables_graphs
#importlib.reload(src.tables_graphs)

from src import BASE_DIR

# load shapefiles
shapefiles = src.reproject.load_shapefiles()
huc6 = shapefiles['huc6']
huc8 = shapefiles['huc8']
OSE = shapefiles['OSE']

## function for calculating swe statistics for polygons
def swe_stat_calc(raster, shapefile_gdf):
    """
    Calculates snow water equivalent mean, median, and volume for each 
    polygon in a shapefile and returns it as a dataframe.

    Parameters:
    raster (xarray.DataArray): An xarray object with SWE raster data. Units must be in inches.
    shapefile_gdf (geopandas.GeoDataFrame): A GeoDataFrame with shapefile data.

    Returns:
    pandas.DataFrame: A DataFrame with one row for each polygon in shapefile and columns
                        for median, mean, and total swe volume. Mean and median units are
                        in inches and volume units are acre feet.
    """

    ## clip raster to polygon bounds
    bounds = shapefile_gdf.total_bounds
    raster = raster.rio.clip_box(*bounds)
    raster = raster.fillna(0)

    cols_swe = ['name', 'Median SWE (in.)', 'Mean SWE (in.)', 
                'Estimated Volume (af)'] #output column names
    swe_df = [] #empty list for polygon stats

    ## loop through each polygon in shapefile and append statistics to swe_df list
    for idx, basin in shapefile_gdf.iterrows():
        swe_basin = raster.rio.clip([basin.geometry])
        
        '''
        ## plot clipped polygon
        f, ax = plt.subplots()
        swe_basin.plot(cmap="Blues",
                        ax=ax)
        cbar = ax.collections[-1].colorbar
        cbar.set_label('SWE [in]', fontsize=16, labelpad=14)
        cbar.ax.tick_params(labelsize=12)
        ax.ticklabel_format(style='sci', axis='x', scilimits=(0,0)) 
        ax.set_xlabel('Easting [m]')
        ax.set_ylabel('Northing [m]')
        ax.set_title('SWE Overview ' + basin['Name'])
        plt.show()'
        '''
        
        
        swe_median = np.nanmedian(swe_basin) # median swe for basin
        swe_mean = np.nanmean(swe_basin) # mean swe for basin
        swe_sum_inches = np.nansum(swe_basin) # swe sum for basin

        ## get pixel area in feet
        pixel_size_x, pixel_size_y = swe_basin.rio.resolution()
        pixel_area = abs((pixel_size_x*3.28084) * (pixel_size_y*3.28084))
        
        swe_vol_cuft = (swe_sum_inches / 12) * pixel_area # volume in cubic feet
        swe_vol_af = np.float32(swe_vol_cuft / 43560) # volume in acre feet

        ## append values to list
        swe_df.append([basin['Name'], swe_median, 
                    swe_mean, swe_vol_af,])

    ## convert list to dataframe
    swe_df_table = pd.DataFrame(swe_df, columns=cols_swe)
    return(swe_df_table)

#########################################################################

## function to generate table 1 csv
def generate_table1(raster):
    ## huc8 stats calculation
    huc8_stats = swe_stat_calc(raster, huc8)
    huc8_stats = huc8_stats.rename(columns={'name': 'HUC8 Subbasin'}) 
    huc6_basin = np.array(huc8['HUC6 Basin'])
    huc8_stats['HUC6 Basin'] = huc6_basin

    ## huc6 stats calculation
    huc6_stats = swe_stat_calc(raster, huc6)
    huc6_stats = huc6_stats.rename(columns={'name': 'HUC6 Basin'})
    huc6_stats['HUC8 Subbasin'] = np.repeat('Total', [3], axis=0)

    ## concatenate, select columns
    table1 = pd.concat([huc8_stats, huc6_stats], ignore_index=True)
    table1 = table1[['HUC6 Basin', 'HUC8 Subbasin', 'Median SWE (in.)', # reorder columns
                    'Mean SWE (in.)', 'Estimated Volume (af)']]


    ## FIX ME!
    ## temporary fix to reoder rows, needs to be changed ##
    table1 = table1.reindex([0, 1, 2, 3, 4, 18,
                            5, 6, 19,
                            7, 8, 9, 10, 11, 12, 
                            13, 14, 15, 16, 17, 20]).reset_index().drop(columns= ['index'])
    return(table1)

def table1_reportlab(table1, data_source, date):
    if data_source == "Ensemble":
        cols_round = ['Ensemble Mean Vol. (af)', 'Ensemble Median Vol (af)',
                      'Ensemble SD Vol. (af)', 'Ensemble Min. Vol. (af)',
                      'Ensemble Max. Vol. (af)']    
        table1[cols_round] = table1[cols_round].map(lambda x: f'{x:,.0f}' if isinstance(x, (int, float)) else x)

    else:    
        cols_round = ['Median SWE (in.)', 'Mean SWE (in.)']
        table1[cols_round] = table1[cols_round].map(lambda x: f'{x:,.1f}' if isinstance(x, (int, float)) else x)
        table1['Estimated Volume (af)'] = table1['Estimated Volume (af)'].map(lambda x: f'{x:,.0f}' if isinstance(x, (int, float)) else x)

    ## remove duplicate HUC6 labels
    table1['HUC6 Basin'] = table1.groupby('HUC6 Basin')['HUC6 Basin'].transform(lambda x: x.where(x.index == x.index[0], ""))

    ## export to pdf
    # PDF filename
    pdf_filename = BASE_DIR / 'tables_for_Max' / f'table1_{data_source}_{date}.pdf'
    pdf_filename = str(pdf_filename)

    # Create empty PDF
    doc = SimpleDocTemplate(pdf_filename, pagesize = landscape(letter))
    elements = []

    # Convert dataframe to list of lists (including column headers)
    columns = table1.columns.tolist()
    table_data = [columns] + table1.values.tolist()

    # Create Table
    col_widths = [100] * len(table1.columns) # adjust column width
    table = Table(table_data, colWidths = col_widths)

    # Add style to Table
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),  # Header background
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),  # Header text color
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  # Align all text to center
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  # Header font
        ('FONTSIZE', (0, 0), (-1, 0), 8),  # Header font size (default 10)
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),  # Padding for header
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),  # Row background color
        ('GRID', (0, 0), (-1, -1), 1, colors.black)  # Grid lines
    ])

    table.setStyle(style)

    # Set pdf title
    styles = getSampleStyleSheet()
    title = Paragraph(f'Table 1. Estimated {data_source} SWE by Basin and Subbasin for {date}', styles["Title"])

    # Add title
    elements.append(title)

    # Add space between text and table
    elements.append(Spacer(1, 12))

    # Add table to PDF
    elements.append(table)

    # Build PDF
    doc.build(elements)

    # print pandas dataframe
    table1.style.hide()