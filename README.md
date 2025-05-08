# nm_swe
Analysis, figures and tables for NM OSE SWE reports  
This repository is used to generate weekly snow water equivalent (SWE) reports for the northern Rio Grande River Basin in Colorado and New Mexico. Code is included to download SNODAS SWE estimates from https://noaadata.apps.nsidc.org/NOAA/G02158/ and generate summary figures and tables. Future updates will include additonal SWE products including UA/SWANN (https://climate.arizona.edu/data/UA_SWE/) and CU SWE. 

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
5. Select nm_swe kernel for running jupyter notebooks. If nm_swe kernel does not show up in kernel list in VSCode or JupyterLab run the following lines the in the terminal:
```
pip install ipykernel
python -m ipykernel install --user --name nm_swe --display-name "nm_swe"    
```
After this, "nm_swe" should appear in the list of kernel (may need to restart VSCode/JupyterLab first).

## Running the SWE Analysis Code
The current system uses three jupyter notebooks in the `notebooks` directory for downloading, plotting and generating tables. Run all cells in each of the three notebooks in the following order:

1. `notebooks/snodas_download.ipynb`  
This notebook downloads the masked SNODAS data for the current day and saves the SWE file as a .tif in the folder `data/SNODAS/`.  
Note: Data is uploaded daily to https://noaadata.apps.nsidc.org/NOAA/G02158/masked/ at 13:00 UTC (7:00 AM MST) (sometimes later) so this notebook needs to be run after this time. To download data for a day other than the current date, the code in the first cell after the packages import can be modified:
```
date = "20250507" # for manual date setting
#date = datetime.today().strftime('%Y%m%d') # get today's date
```
This code also needs to be modified in the other two notebooks to generate figures and tables for a different day.   

2. `notebooks/plot_snodas.ipynb`  
This notebook generates plots for SWE and change in SWE since the last report for the entire study area and each HUC6 basin.
New report directories are also created for saving figures, tables, and csvs. Figures are saved to `reports/YYYY-MM-DD/figures`.

3. `notebooks/swe_tables_snodas.ipynb`
This notebook generates tables for SWE mean, median, volume, and volume change for HUC6 basin, OSE basins, and by elevation band. Elevation band bar plots are also generated for each HUC6 basin.
  - Tables are saved to `reports/YYYY-MM-DD/pdfs` and opened with Microsoft Word for generating weekly reports.
  - Elevation bar plots are saved to `reports/YYYY-MM-DD/figures`.
  - Tables are saved as csv's to `reports/YYYY-MM-DD/csvs` and used for SWE difference calculations. 

## Note on SWE difference calculation
The current system for calculating SWE change since the previous report for plots and tables uses the SNODAS .tif file in the `data/SNODAS` folder and csvs in the `reports` folder with the maximum date in their file names. When the code is run each week, the tifs and csvs are saved to these folders to be used for the difference calculation of the next report. The file structure will need to be updated to organize files by water year since no previous data will have been downloaded for the first report of each water year.    

Example csvs, figures, and pdf tables are included for 2025-05-06 in `reports/2025-05-06`. By default SWE difference will be calculated from this date.  
