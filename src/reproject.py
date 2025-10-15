import numpy as np
import pandas as pd
import geopandas as gpd
import xarray as xr
import rasterio as rio
import rioxarray as rxr
from shapely.geometry import Point

from src import BASE_DIR

## function to load reproject shapefiles
def load_shapefiles():
    """
    Loads shapefiles in 'data/Shapefiles' and reprojects to UTM Zone 13N for tables and plotting.

    Parameters:
        No input parameters.

    Returns:
        dict of GeoDataFrames
    """    
    print("Loading and reprojecting shapefiles...")

    # huc6 and huc8 shapefiles, reproject to UTM Zone 13N
    huc6 = gpd.read_file(BASE_DIR / 'data' / 'Shapefiles' / 'WBDHU6_RG' / 'WBDHU6_RG.shp').to_crs('epsg:26913')
    huc8 = gpd.read_file(BASE_DIR / 'data' / 'Shapefiles' / 'WBDHU8_RG' / 'WBDHU8_RG.shp').to_crs('epsg:26913')
    huc8 = huc8.drop(huc8.index[72]) # drop Rio Salado basin in Mexico

    ## read OSE shapefile and reproject
    OSE = gpd.read_file(BASE_DIR / 'data' / 'Shapefiles' / 'OSE_Basin_Delineations_Updated' / 'OSEBasinDelineations_Updated.shp').to_crs('epsg:26913')
    OSE = OSE.replace({'Name' : {'Sangre De Cristo' : 'Sangre de Cristo'}}) # 'De' to lowercase
    OSE = OSE.sort_values('Name').reset_index().drop(columns = ['index']) # sort alphabetically
    #OSE['geometry'] = OSE.geometry.scale(xfact=0.95, yfact=0.95, origin='center') # scale to reduce overlap in plot

    ## read state boundaries shapefile and reproject
    state_boundaries = gpd.read_file(BASE_DIR / 'data' / 'Shapefiles' / 'cb_2018_us_state_20m' / 'cb_2018_us_state_20m.shp').to_crs('epsg:26913')
    state_boundaries = state_boundaries[state_boundaries['NAME'].isin(['Arizona', 'Colorado', 'New Mexico', 'Utah'])].reset_index()

    ## New Mexico cities shapefiles
    nm_cities = gpd.read_file(BASE_DIR / 'data' / 'Shapefiles' / 'tl_2024_35_place' / 'tl_2024_35_place.shp')
    geometry = [Point(xy) for xy in zip(nm_cities['INTPTLON'], nm_cities['INTPTLAT'])]
    nm_cities = gpd.GeoDataFrame(nm_cities, crs='EPSG:4326', geometry=geometry)
    nm_cities = nm_cities.to_crs('epsg:26913')
    nm_cities = nm_cities[nm_cities['NAME'].isin(['Albuquerque', 'Santa Fe'])].reset_index()

    ## select HUC6 polygons of interest
    huc6_polys = ['Rio Grande Headwaters', 'Upper Rio Grande',
        'Rio Grande-Elephant Butte']
    huc6 = huc6[huc6['Name'].isin(huc6_polys)]

    ## select HUC8 polygons of interest
    huc8_polys = ['Rio Grande Headwaters', 'Alamosa-Trinchera',
                'San Luis', 'Saguache',
                'Conejos', 'Upper Rio Grande',
                'Rio Chama', 'Rio Grande-Santa Fe',
                'Jemez', 'Rio Grande-Albuquerque',
                'Arroyo Chico', 'North Plains',
                'Rio San Jose', 'Plains of San Agustin',
                'Rio Salado', 'Jornada Del Muerto',
                'Elephant Butte Reservoir', 'Rio Puerco']
    huc8 = huc8[huc8['Name'].isin(huc8_polys)]


    ## sort by polygon order
    huc8 = huc8.set_index('Name', drop = False)
    huc8 = huc8.reindex(huc8_polys)

    ## add huc6 basin and region columns to huc8 geopandas dataframe for table 1
    ## huc6 basins
    huc6_basin = np.array(['Rio Grande Headwaters', 'Upper Rio Grande', 
                        'Rio Grande-Elephant Butte'])
    huc6_basin = np.repeat(huc6_basin, [5, 2, 11], axis=0)

    ## region
    region = np.repeat('Rio Grande', [18], axis = 0)

    ## add huc6 basin and region to huc8 geopandas dataframe
    huc8['HUC6 Basin'] = huc6_basin
    huc8['Region'] = region

    print("Done reprojecting shapefiles.")

    return {
        "huc6": huc6,
        "huc8": huc8,
        "OSE": OSE,
        "state_boundaries": state_boundaries,
        "nm_cities": nm_cities
    }

    

###################################################################

## function to load snodas tif and reproject to UTM
def load_snodas(date: str, filter: bool):
    """
    Loads SNODAS tif for given date in 'data/SNODAS', reprojects to UTM Zone 13N, and converts
    units to inches.

    Parameters:
        date (str): String object of the date of the SNODAS file.

    Returns:
        snodas_inches (xarray.DataArray): An xarray object with SWE raster data.
    """    
    print(f'Loading SNODAS for date {date}...')

    snodas = rxr.open_rasterio(BASE_DIR / 'data' / 'SNODAS' / f'SNODAS_SWE_{date}.tif').sel(band=1).reset_coords('band', drop=True)
    snodas_utm = snodas.rio.reproject('epsg:26913', resampling = 0, resolution = 1000) # 0=nearest neighbor #resolution=1000

    # convert to inches
    snodas_inches = snodas_utm.where(snodas_utm>=0) / 1000 * 3.2808 * 12
    if filter == True:
        snodas_inches = snodas_inches.where(snodas_inches > 1, np.nan)

    print(f'Done loading SNODAS for {date}.')

    return(snodas_inches)

###############################################################

## function to load UA SWE netcdf and reproject to UTM
def load_uaswe(date: str, reproject: bool, filter: bool):
    """
    Loads UA SWE netcdf for given date in 'data/UA_SWE', reprojects to UTM Zone 13N,
    and converts units to inches.

    Parameters:
        date (str): String object of the date of the UA SWE file.
        reproject (bool): True or False value whether to reproject to UTM

    Returns:
        ua_swe_inches (xarray.DataArray): An xarray object with SWE raster data.
    """ 

    ua = xr.open_dataset(BASE_DIR / 'data' / 'UA_SWE' / f'UA_SWE_{date}.nc', engine="netcdf4", decode_coords="all")
    ua_swe = ua["SWE"].squeeze("time", drop=True) # select SWE variable, drop time
    ua_swe = ua_swe.rio.set_spatial_dims(x_dim="lon", y_dim="lat")
    ua_swe = ua_swe.rename({"lon": "x", "lat": "y"})
    
    if reproject == True:
        print(f'Reprojecting UA SWE for date {date}...')
        ua_swe_utm = ua_swe.rio.reproject('epsg:26913', resampling = 0, resolution = 800) # 0=nearest neighbor

        # convert to inches
        ua_swe_inches = ua_swe_utm.where(ua_swe_utm>=0) / 1000 * 3.2808 * 12
        ua_swe_inches = ua_swe_inches.where(ua_swe_inches > 1, np.nan)
        
        ua_swe_inches = ua_swe_inches.rio.write_crs(ua_swe_utm.rio.crs) # add crs

        print(f'Done reprojecting UA SWE for date {date}.')

    else:
        print(f'Skipping reprojection of UA SWE for date {date}...')    

        # convert to inches
        ua_swe_inches = ua_swe.where(ua_swe>=0) / 1000 * 3.2808 * 12
        if filter == True:
            ua_swe_inches = ua_swe_inches.where(ua_swe_inches > 1, np.nan)

        ua_swe_inches = ua_swe_inches.rio.write_crs(ua_swe.rio.crs) # add crs

        print(f'Done loading UA SWE for date {date}.')

    return(ua_swe_inches)

#############################################################################

## function to load CU SWE tif and reproject to UTM
def load_cuswe(date: str, reproject: bool, filter: bool):
    """
    Loads CU SWE tif for given date in 'data/CU_SWE', reprojects to UTM Zone 13N,
    and converts units to inches.

    Parameters:
        date (str): String object of the date of the CU SWE file.

    Returns:
        cu_swe_inches (xarray.DataArray): An xarray object with SWE raster data.
    """ 
    cu_swe = rxr.open_rasterio(BASE_DIR / 'data' / 'CU_SWE' / f'{date}_raster.tif').sel(band=1).reset_coords('band', drop=True)
    
    if reproject == True:
        print(f'Reprojecting CU SWE for date {date}...')
        cu_swe_utm = cu_swe.rio.reproject('epsg:26913', resampling = 0, resolution = 500) # 0=nearest neighbor #resolution=1000

        # convert from meters to inches
        cu_swe_inches = cu_swe_utm.where(cu_swe_utm>=0) * 3.2808 * 12

        print(f'Done reprojecting CU SWE for date {date}.')

    else:
        print(f'Skipping reprojection of CU SWE for date {date}...')    
        # convert from meters to inches
        cu_swe_inches = cu_swe.where(cu_swe>=0) * 3.2808 * 12

        print(f'Done loading CU SWE for date {date}.')

    if filter == True:
        cu_swe_inches = cu_swe_inches.where(cu_swe_inches > 1, np.nan)    

    return(cu_swe_inches)


###############################################################

## function to load UA SWE netcdf and reproject to UTM
def load_era5(date: str, reproject: bool, filter: bool):
    """
    Loads ERA5 grib for given date in 'data/ERA5', reprojects to UTM Zone 13N,
    and converts units to inches.

    Parameters:
        date (str): String object of the date of the ERA5 file.

    Returns:
        era5_inches (xarray.DataArray): An xarray object with SWE raster data.
    """ 

    era5 = xr.open_dataset(BASE_DIR / 'data' / 'ERA5' / f'ERA5_SWE_{date}.grib', engine="cfgrib", decode_coords="all")
    era5.rio.write_crs('epsg:4326', inplace = True)
    era5 = era5["sd"].squeeze() # select SWE variable, drop time
    era5 = era5.rio.set_spatial_dims(x_dim="longitude", y_dim="latitude")
        
    if reproject == True:
        print(f'Reprojecting ERA5 for date {date}...')    
        era5_utm = era5.rio.reproject('epsg:26913', resampling = 0, resolution = 9000) # 0=nearest neighbor

        # convert to inches
        era5_inches = era5_utm.where(era5_utm>=0) * 3.2808 * 12
        #era5_inches = era5_inches.rio.write_crs(era5_utm.rio.crs) # add crs

        print(f'Done reprojecting ERA5 for date {date}.')

    else:
        print(f'Skipping reprojection of ERA5 for date {date}...')
        # convert to inches
        era5_inches = era5.where(era5>=0) * 3.2808 * 12

        print(f'Done loading ERA5 for date {date}.')    

    if filter == True:
        era5_inches = era5_inches.where(era5_inches > 1, np.nan)

    return(era5_inches)

