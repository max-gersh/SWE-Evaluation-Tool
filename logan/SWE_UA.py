# -*- coding: utf-8 -*-
"""
Created on Mon Mar  3 12:22:56 2025

@author: blats
"""

import requests


date = "20250301"
file_path = "https://climate.arizona.edu/data/UA_SWE/DailyData_800m/WY2025/"
file_name = "UA_SWE_Depth_800m_v1_" + date + "_early.nc"
file_url = file_path + file_name

## download file from SNODAS website
r = requests.get(file_url)

with open("UA_SWE/" + file_name, "wb") as f:	
    f.write(r.content)
    
## download mask file
mask_url = "https://climate.arizona.edu/data/UA_SWE/SWE_Mask_800m.nc"
mask_file_name = "UA_SWE/SWE_Mask_800m.nc"

r = requests.get(mask_url)

with open(mask_file_name, "wb") as f:	
    f.write(r.content)