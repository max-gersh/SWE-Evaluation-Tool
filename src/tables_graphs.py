import numpy as np
import pandas as pd
import geopandas as gpd
import xarray as xr
import rasterio as rio
import rioxarray as rxr
import matplotlib.pyplot as plt
import math
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
    #raster = raster.fillna(0)

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
def generate_table1(raster, data_source, date):
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
    
    # save table as csv
    csv_dir_date = datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d")
    csv_filename = BASE_DIR / 'reports' / csv_dir_date / "csvs" / f'table1_{data_source}_{date}.csv'
    table1.to_csv(csv_filename, index=False)

    return(table1)

## function to generate table 1 reportlab pdf
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
    pdf_dir_date = datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d")
    pdf_filename = BASE_DIR / 'reports' / pdf_dir_date / "pdfs" / f'table1_{data_source}_{date}.pdf'
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
    title = Paragraph(f'Table 1. Estimated {data_source} SWE by Basin and Subbasin for {pdf_dir_date}', styles["Title"])

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


## generate table 2
def generate_table2(raster, data_source, date):
    huc8_ose_polys = ['Rio Grande Headwaters', 'Saguache',
                    'Conejos', 'San Luis',
                    'Alamosa-Trinchera', 'Upper Rio Grande']
    huc8_ose = huc8[huc8['Name'].isin(huc8_ose_polys)]

    ## sort by polygon order
    huc8_ose = huc8_ose.set_index('Name', drop = False)
    huc8_ose = huc8_ose.reindex(huc8_ose_polys)

    ## add ose basin column
    ose_grouping = np.array(['Upper Rio Grande', 
                        'Sangre de Cristo'])
    ose_grouping = np.repeat(ose_grouping, [3, 3], axis=0)

    huc8_ose['OSE Grouping'] = ose_grouping

    ## create table
    huc8_ose_stats = swe_stat_calc(raster, huc8_ose)
    huc8_ose_stats = huc8_ose_stats.rename(columns={'name': 'HUC8 Subbasin'}) 
    huc8_ose_stats['OSE Grouping'] = ose_grouping


    ose_stats = swe_stat_calc(raster, OSE)
    ose_stats = ose_stats.rename(columns={'name': 'OSE Grouping'})
    ose_stats['HUC8 Subbasin'] = np.repeat('Total', [4], axis=0)

    #huc6_stats
    table2 = pd.concat([huc8_ose_stats, ose_stats], ignore_index=True)
    table2 = table2[['OSE Grouping', 'HUC8 Subbasin', 'Median SWE (in.)', 
                    'Mean SWE (in.)', 'Estimated Volume (af)']]
    
    ## FIX ME!
    ## temporary fix to reoder rows, needs to be changed ##
    table2 = table2.reindex([0, 1, 2, 9,
                            3, 4, 5, 8,
                            7, 6]).reset_index().drop(columns= ['index'])
    
    # save table as csv
    csv_dir_date = datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d")
    csv_filename = BASE_DIR / 'reports' / csv_dir_date / "csvs" / f'table2_{data_source}_{date}.csv'
    table2.to_csv(csv_filename, index=False)

    return(table2)



## function to generate table 2 reportlab pdf
def table2_reportlab(table2, data_source, date):
    if data_source == "Ensemble":
        cols_round = ['Ensemble Mean Vol. (af)', 'Ensemble Median Vol (af)',
                      'Ensemble SD Vol. (af)', 'Ensemble Min. Vol. (af)',
                      'Ensemble Max. Vol. (af)']    
        table2[cols_round] = table2[cols_round].map(lambda x: f'{x:,.0f}' if isinstance(x, (int, float)) else x)

    else:    
        cols_round = ['Median SWE (in.)', 'Mean SWE (in.)']
        table2[cols_round] = table2[cols_round].map(lambda x: f'{x:,.1f}' if isinstance(x, (int, float)) else x)
        table2['Estimated Volume (af)'] = table2['Estimated Volume (af)'].map(lambda x: f'{x:,.0f}' if isinstance(x, (int, float)) else x)

    ## remove duplicate HUC6 labels
    table2['OSE Grouping'] = table2.groupby('OSE Grouping')['OSE Grouping'].transform(lambda x: x.where(x.index == x.index[0], ""))

    ## export to pdf
    # PDF filename
    pdf_dir_date = datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d")
    pdf_filename = BASE_DIR / 'reports' / pdf_dir_date / "pdfs" / f'table2_{data_source}_{date}.pdf'
    pdf_filename = str(pdf_filename)

    # Create empty PDF
    doc = SimpleDocTemplate(pdf_filename, pagesize = landscape(letter))
    elements = []

    # Convert dataframe to list of lists (including column headers)
    columns = table2.columns.tolist()
    table_data = [columns] + table2.values.tolist()

    # Create Table
    col_widths = [100] * len(table2.columns) # adjust column width
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
    title = Paragraph(f'Table 2. Estimated {data_source} SWE by OSE Basin and Subbasin for {pdf_dir_date}', styles["Title"])

    # Add title
    elements.append(title)

    # Add space between text and table
    elements.append(Spacer(1, 12))

    # Add table to PDF
    elements.append(table)

    # Build PDF
    doc.build(elements)

    # print pandas dataframe
    table2.style.hide()



## generate table 3 (elevation band) csv
def generate_table3(raster, data_source, date, band_width, save_csv):
    bounds = huc8.geometry.total_bounds
    raster_clipped = raster.rio.clip_box(*bounds)


    dem = rxr.open_rasterio(BASE_DIR / 'data' / 'dem.tif').sel(band=1).reset_coords('band', drop=True)
    dem = dem.where(dem>=0).rio.reproject_match(raster_clipped)

    ## combine swe and dem arrays
    swe_ds = xr.Dataset()
    swe_ds['swe'] = raster_clipped
    swe_ds['elevation'] = dem

    ## get pixel area in feet
    pixel_size_x, pixel_size_y = swe_ds.rio.resolution()
    pixel_area = abs((pixel_size_x*3.28084) * (pixel_size_y*3.28084))
            

    cols_swe_elev = ['HUC6 Basin', 'HUC8 Subbasin', 'Elevation Band (ft.)',
                    'Median SWE (in.)', 'Mean SWE (in.)', 
                    'Estimated Volume (af)'] #output column names
    swe_elev_df = [] #empty list for polygon stats

    for idx, basin in huc8.iterrows():
        swe_basin = swe_ds.rio.clip([basin.geometry])
        '''
        f, ax = plt.subplots()
        swe_basin.elevation.plot(cmap="terrain",
                                ax=ax)
        plt.show()
        '''

        ## get min and max elevation for basin
        elev_min = np.floor(float(np.nanmin(swe_basin.elevation)) / 1000) * 1000
        elev_max = np.ceil(float(np.nanmax(swe_basin.elevation)) / 1000) * 1000
        elev_bands = np.arange(elev_min, elev_max, band_width) # band height 1000 ft

        ## loop through elevation bands and calculate statistics
        for i in range(len(elev_bands)):
            elev_mask = (swe_basin['elevation'] >= elev_bands[i]) * (swe_basin['elevation'] < elev_bands[i] + 1000)
            swe_sum_inches = float(swe_basin['swe'].where(elev_mask).sum()) # sum swe at mask
            swe_vol_cuft = (swe_sum_inches / 12) * pixel_area # volume in cubic feet
            swe_vol_af = swe_vol_cuft / 43560 # volume in acre feet

            ## swe median and mean at mask
            swe_median = float(swe_basin['swe'].where(elev_mask).median())
            swe_mean = float(swe_basin['swe'].where(elev_mask).mean())

            band = str(int(elev_bands[i])) + '-' + str(int(elev_bands[i] + 1000)) + "\'"

            ## append values to list
            swe_elev_df.append([basin['HUC6 Basin'], basin['Name'], band, 
                        swe_median, swe_mean, swe_vol_af,])

    ## convert list to dataframe
    table3 = pd.DataFrame(swe_elev_df, columns=cols_swe_elev)

    # save table as csv if save csv flag equals True
    if save_csv:
        csv_dir_date = datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d")
        csv_filename = BASE_DIR / 'reports' / csv_dir_date / "csvs" / f'table3_{data_source}_{date}.csv'
        table3.to_csv(csv_filename, index=False)

    return(table3)



## function to generate table 2 reportlab pdf
def table3_reportlab(table3, data_source, date):
    if data_source == "Ensemble":
        cols_round = ['Ensemble Mean Vol. (af)', 'Ensemble Median Vol (af)',
                      'Ensemble SD Vol. (af)', 'Ensemble Min. Vol. (af)',
                      'Ensemble Max. Vol. (af)']    
        table3[cols_round] = table3[cols_round].map(lambda x: f'{x:,.0f}' if isinstance(x, (int, float)) else x)

    else:    
        cols_round = ['Median SWE (in.)', 'Mean SWE (in.)']
        table3[cols_round] = table3[cols_round].map(lambda x: f'{x:,.1f}' if isinstance(x, (int, float)) else x)
        table3['Estimated Volume (af)'] = table3['Estimated Volume (af)'].map(lambda x: f'{x:,.0f}' if isinstance(x, (int, float)) else x)

    ## remove duplicate HUC6 and HUC8 labels
    table3['HUC6 Basin'] = table3.groupby('HUC6 Basin')['HUC6 Basin'].transform(lambda x: x.where(x.index == x.index[0], ""))
    table3['HUC8 Subbasin'] = table3.groupby('HUC8 Subbasin')['HUC8 Subbasin'].transform(lambda x: x.where(x.index == x.index[0], ""))

    ## export to pdf
    # PDF filename
    # PDF filename
    pdf_dir_date = datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d")
    pdf_filename = BASE_DIR / 'reports' / pdf_dir_date / "pdfs" / f'table3_{data_source}_{date}.pdf'
    pdf_filename = str(pdf_filename)

    # Create empty PDF document
    doc = SimpleDocTemplate(pdf_filename, pagesize = landscape(letter))
    elements = []

    # Convert dataframe to list of lists (including column headers)
    columns = table3.columns.tolist()
    columns[-1] = columns[-1].replace("Change", "Change\n")
    table_data = [columns] + table3.values.tolist()

    # Create Table
    col_widths = [100] * len(table3.columns) # adjust column width
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

    # Table title
    styles = getSampleStyleSheet()
    title = Paragraph(f'Table 3. Estimated {data_source} SWE by Basin and Elevation Band for {pdf_dir_date}', styles["Title"])

    # Add title before table
    elements.append(title)

    # Add space between text and table
    elements.append(Spacer(1, 12))

    # Add table to PDF
    elements.append(table)

    # Build PDF
    doc.build(elements)



## elevation density plots
def elevation_plots(snodas_table, ua_swe_table, cu_swe_table, date):

    """
    Generates SWE volume by elevation plots for each huc8 basin and input product. 

    Parameters:
        snodas_table (pandas.DataFrame): DataFrame with SNODAS SWE volume by elevation band.
        ua_swe_table (pandas.DataFrame): DataFrame with UA SWE SWE volume by elevation band.
        snodas_table (pandas.DataFrame): DataFrame with SNODAS SWE volume by elevation band.
        date (str): Report date; used for setting file name. 

    Returns:
        None.
    """

    table3_dfs = [
        snodas_table.assign(data_source="SNODAS"),
        ua_swe_table.assign(data_source="UA_SWE"),
        cu_swe_table.assign(data_source="CU_SWE"),
    ]
    table3_aggreg = pd.concat(table3_dfs, ignore_index=True)
    table3_aggreg['Elevation Band (ft.)'] = table3_aggreg['Elevation Band (ft.)'].str.split("-").str[0]
    table3_aggreg['Elevation Band (ft.)'] = table3_aggreg['Elevation Band (ft.)'].astype(int)

    table3_aggreg['Estimated Volume (af)'] = table3_aggreg['Estimated Volume (af)'] / 1000

    # get unique huc6 ids
    huc6_id_list = table3_aggreg['HUC6 Basin'].unique()

    # loop through huc6 basins and generate elevation plots
    for huc6_basin in huc6_id_list:

        print(f'Creating elevation plot for {huc6_basin}')

        #huc6_id = huc6_basin
        table3_huc6 = table3_aggreg[table3_aggreg['HUC6 Basin'] == huc6_basin]    


        basins = table3_huc6['HUC8 Subbasin'].unique()

        ## get list of huc8 subbasins with 0 swe volume
        huc8_totals = table3_huc6.groupby(['HUC8 Subbasin'], sort = False)['Estimated Volume (af)'].sum()
        huc8_zero_volume = huc8_totals.loc[huc8_totals == 0].index.tolist()
        print(huc8_zero_volume)

        ## remove basins with zero volume from plots
        basins = [i for i in basins if i not in huc8_zero_volume]

        # set number of columns to 3 in plots
        n_basins = len(basins)
        if n_basins < 3:
            cols = n_basins
        else:
            cols = 3
        rows = math.ceil(n_basins / cols)

        ## plot
        fig, axes = plt.subplots(rows, cols, figsize=(15, 5 * rows), sharey=True)
        axes = axes.flatten()

        # loop through subbasins
        for ax, basin in zip(axes, basins):
            table3_basin = table3_aggreg[table3_aggreg['HUC8 Subbasin'] == basin]


            for data_source, group in table3_basin.groupby("data_source"):
                ax.plot(group['Estimated Volume (af)'], group['Elevation Band (ft.)'], label=data_source)

            ax.set_xlabel("SWE Volume (thousands of af)")
            ax.set_ylabel("Elevation (ft.)")
            ax.set_title(basin)
            ax.legend()

            # hide empty spaces if basins < rows*cols
            for i in range(len(basins), len(axes)):
                axes[i].set_visible(False)

            fig.suptitle(f'{huc6_basin} HUC6 Basin')
            plt.tight_layout()
            #plt.show()
            png_dir_date = datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d")
            png_filename = BASE_DIR / 'reports' / png_dir_date / 'figures' / f'{huc6_basin}_elevation_{date}.png'
            plt.savefig(png_filename, dpi=300, bbox_inches='tight')
