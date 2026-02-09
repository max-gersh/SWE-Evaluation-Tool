import requests
import tarfile
import gzip
import shutil
from osgeo import gdal
import calendar
from datetime import datetime
import os
from pathlib import Path
import re
#import cdsapi # used for era5 download

from src import BASE_DIR

#BASE_DIR = Path.cwd().resolve()


## download snodas data and convert to tif
def download_snodas(date: str):
    """
    Downloads 1km SNODAS SWE data from https://noaadata.apps.nsidc.org/NOAA/G02158/masked/ and 
    converts to tif file saved in data/SNODAS.

    Parameters:
    date (str): String object of the date to be downloaded. 

    Returns:
    No return value.
    """

    file_path = BASE_DIR / "data" / "SNODAS" / f'SNODAS_SWE_{date}.tif'
    if file_path.is_file():
        print(f'File {file_path} already donwnloaded.')
        
    
    else:
        print(f'Downloading SNODAS data for date {date}...')

        year = date[0:4]
        month = date[4:6]
        month_abbrev = calendar.month_abbr[int(month)]
        file_path = f"https://noaadata.apps.nsidc.org/NOAA/G02158/masked/{year}/{month}_{month_abbrev}/"
        file_name = f"SNODAS_{date}.tar"
        file_url = file_path + file_name

        ## set snodas directory for download
        snodas_dir = BASE_DIR / "data" / "SNODAS"
        snodas_dir.mkdir(parents=True, exist_ok=True)


        ## download file from SNODAS website
        r = requests.get(file_url)

        tar_path = snodas_dir / file_name
        with open(tar_path, "wb") as f:	
            f.write(r.content)
        
        ## untar file
        tar = tarfile.open(tar_path)
        tar.extractall(path= snodas_dir)
        tar.close()

        ## unzip SWE dat file
        dat_zip_path = snodas_dir / f"us_ssmv11034tS__T0001TTNATS{date}05HP001.dat.gz"
        dat_path = snodas_dir / f"us_ssmv11034tS__T0001TTNATS{date}05HP001.dat"
        with gzip.open(dat_zip_path, 'rb') as file_in:
            with open(dat_path, 'wb') as file_out:
                shutil.copyfileobj(file_in, file_out)

        ## create hdr file 
        hdr_content = """ENVI
        samples = 6935
        lines = 3351
        bands = 1
        header offset = 0
        file type = ENVI Standard
        data type = 2
        interleave = bsq
        byte order = 1
        """

        ## save .hdr file
        hdr_filename = snodas_dir / f"us_ssmv11034tS__T0001TTNATS{date}05HP001.hdr"
        with open(hdr_filename, "w") as f:
            f.write(hdr_content)

        ## convert .dat file to .tif with gdal_translate
        input_file = snodas_dir / f"us_ssmv11034tS__T0001TTNATS{date}05HP001.dat"
        output_file = snodas_dir / f"SNODAS_SWE_{date}.tif"

        ## open input file
        dataset = gdal.Open(input_file, gdal.GA_ReadOnly)

        # Set output format and options
        output_format = "GTiff"  # GeoTIFF format
        options = [
            "-a_srs", "+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs",  # Set spatial reference
            "-a_nodata", "-9999",  # Set NoData value
            "-a_ullr", "-124.73333333333333", "52.87500000000000", "-66.94166666666667", "24.95000000000000"  # Set bounding box
        ]

        # Perform translation (conversion)
        gdal.Translate(output_file, dataset, format=output_format, options=options)

        # Close dataset
        dataset = None

        # Clean up SNODAS directory
        print(f'SNODAS tif for {date} successfully saved to {output_file}. Removing ancillary data files...')
        snodas_files = os.listdir(snodas_dir)
        files_to_delete = [f for f in snodas_files if '.tif' not in f]
        for i in range(len(files_to_delete)):
            os.remove(snodas_dir / files_to_delete[i])
        

####################################################################################

## download UofA SWE data
def download_uaswe(date: str):
    """
    Downloads 800m UA SWE netcdf from https://climate.arizona.edu/data/UA_SWE/DailyData_800m/ and 
    saves to data/UA_SWE.

    Parameters:
    date (str): String object of the date to be downloaded. 

    Returns:
    No return value.
    """
    ua_swe_dir = BASE_DIR / "data" / "UA_SWE"
    file_path = ua_swe_dir / f'UA_SWE_{date}.nc'
    if file_path.is_file():
        print(f'File {file_path} already downloaded.')
        
    
    else:
        print(f'Downloading UA SWE data for date {date}...')
        ua_swe_dir.mkdir(parents=True, exist_ok=True)

        year = date[0:4]
        month = date[4:6]

        # get water year from data
        year_int = int(year)
        date_obj = datetime.strptime(date, "%Y%m%d")
        if (date_obj.month, date_obj.day) > (9, 30):
            water_year = str(year_int + 1)
        else:
            water_year = year

        ## download data for date
        url = f"https://climate.arizona.edu/data/UA_SWE/DailyData_800m/WY{water_year}/"

        r = requests.get(url)
        r.raise_for_status()

        ## find all links ending in .nc (case-insensitive)
        nc_files = re.findall(r'href="([^"]+\.nc)"', r.text, flags=re.IGNORECASE)
        #print(nc_files)

        ## get file containing date
        matching_file = [f for f in nc_files if date in f]

        ## set full ua swe url
        full_url = f"{url}/{matching_file[0]}"

        r = requests.get(full_url)
        r.raise_for_status()

        nc_path = ua_swe_dir / f"UA_SWE_{date}.nc"
        with open(nc_path, "wb") as f:	
            f.write(r.content)

        print(f'UA SWE netcdf for {date} successfully saved to {nc_path}.')


####################################################################################

## download ERA5 SWE data
def download_era5(date: str):
    """
    Downloads 9km ERA5 SWE grib file from https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land?tab=overview 
    and saves to data/ERA5.

    Parameters:
    date (str): String object of the date to be downloaded. 

    Returns:
    No return value.
    """    
    file_path = BASE_DIR / "data" / "ERA5" / f'ERA5_SWE_{date}.grib'
    if file_path.is_file():
        print(f'File {file_path} already downloaded.')
    
    else:
        year = date[0:4]
        month = date[4:6]
        day = date[6:8]
        era5_dir = BASE_DIR / "data" / "ERA5"

        dataset = "reanalysis-era5-land"
        request = {
            "variable": ["snow_depth_water_equivalent"],
            "year": year,
            "month": month,
            "day": [day],
            "time": ["23:00"],
            "data_format": "grib",
            "download_format": "unarchived",
            "area": [42, -115, 30, -100]
        }
        target = str(era5_dir / f"ERA5_SWE_{date}.grib")

        client = cdsapi.Client()
        client.retrieve(dataset, request, target)