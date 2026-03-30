# nm_swe
Analysis, figures and tables for NM OSE SWE reports  
This repository is used to generate weekly snow water equivalent (SWE) reports for the northern Rio Grande River Basin in Colorado and New Mexico. Code is included to download SNODAS SWE (https://noaadata.apps.nsidc.org/NOAA/G02158/), UA/SWANN (https://climate.arizona.edu/data/UA_SWE/), CU SWE (manual download from onedrive) and generate summary figures and tables.

## Setup
This system uses the python programming language. You will need to create a conda environment with the required packages. All of the following commands should be run in a terminal (powershell on windows) or the terminal inside of your code editor (tested on Visual Studio Code and JupyterLab for windows).

1. Clone the repository from GitHub to your desired local directory:
```
cd directory_name
git clone https://github.com/RittgerLabGroup/nm_swe.git
```
2. Create the nm_swe conda environment from the `environment.yml` file:
```
conda env create -f setup/environment.yml
```
To install the conda environment to a specified location use:
```
conda env create -f setup/environment.yml --prefix /full/path/to/env/nm_swe
```
This will install all required packages (~3GB).  

3. Activate the new environment: 
```
conda activate nm_swe
```
4. Verify that the new environment was installed correctly:
```
conda env list
```
5. Select nm_swe as the default python interpreter in VS code:
  Ctrl + Shift + P (Command + Shift + P on Mac) > Python: Select Interpreter > Choose 'nm_swe'

  Now when you run python scripts the nm_swe conda environment will be used. 


## Running the SWE Evaluation Tool Code
To run the SWEET code, the user simply needs to run the python file `generate_report.py` with minor modifications.

The steps are as follows:
1. Download latest CU SWE raster from onedrive folder and save to `data` folder with filename format `data/CU_SWE/YYYYMMDD_raster.tif`.
2. Change date on line 26 of `generate_report.py` and save file. CU SWE data must exist for this date.
3. Run `generate_report.py`. 



## Instruction for setting up the Climate Data Store (CDS) API for downloading ERA5 data
1. Create account at https://cds.climate.copernicus.eu/ and log in.
2. Click on name in top right corner then "Your Profile."
3. Scroll down to "API key" section and copy the 2 lines for "url" and "key."
4. Create a text file called ".cdsapi" in your home directory (on windows this is usually C:\Users\username) and paste the 2 lines.
