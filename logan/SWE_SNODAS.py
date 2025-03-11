# -*- coding: utf-8 -*-
"""
Created on Tue Feb  4 15:29:26 2025

@author: blats
"""

import requests
import tarfile
import gzip
import shutil
#!pip install osgeo
from osgeo import gdal
import calendar

date = "20250310"
year = date[0:4]
month = date[4:6]
month_abbrev = calendar.month_abbr[int(month)]
file_path = "https://noaadata.apps.nsidc.org/NOAA/G02158/masked/" + year + "/" + month + "_" + month_abbrev + "/"
file_name = "SNODAS_" + date + ".tar"
file_url = file_path + file_name

## download file from SNODAS website
r = requests.get(file_url)

'''
r.raise_for_status()
except requests.exceptions.HTTPError as err:
    raise SystemExit(err)       
    '''

with open("SNODAS_Data/" + file_name, "wb") as f:	
    f.write(r.content)
    
## untar file
tar = tarfile.open("SNODAS_Data/" + file_name)
tar.extractall(path="SNODAS_Data/")
tar.close()

## unzip SWE dat file
with gzip.open("SNODAS_Data/us_ssmv11034tS__T0001TTNATS" + date + "05HP001.dat.gz", 'rb') as file_in:
    with open("SNODAS_Data/us_ssmv11034tS__T0001TTNATS" + date + "05HP001.dat", 'wb') as file_out:
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
hdr_filename = "SNODAS_Data/us_ssmv11034tS__T0001TTNATS" + date + "05HP001.hdr"  # Change this to your desired filename
with open(hdr_filename, "w") as f:
    f.write(hdr_content)

## convert .dat file to .tif with gdal_translate
input_file = "SNODAS_Data/us_ssmv11034tS__T0001TTNATS" + date + "05HP001.dat"
#output_file = "SNODAS_Data/us_ssmv11034tS__T0001TTNATS" + date + "05HP001.tif"
output_file = "SNODAS_Data/SNODAS_SWE_" +  date + ".tif"

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


