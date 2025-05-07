# nm_swe
Analysis, figures and tables for NM OSE SWE reports  
This repository is used to generate weekly snow water equivalent (SWE) reports for the northern Rio Grande River Basin in Colorado and New Mexico. Code is included to download SNODAS SWE estimates from https://noaadata.apps.nsidc.org/NOAA/G02158/ and generate summary figures and tables. Future updates will include additonal SWE products including UA/SWANN (https://climate.arizona.edu/data/UA_SWE/) and CU SWE. 

## Setup
This system use the python programming language. You will need to create a conda environment with the required packages. All of the following commands should be run in a terminal (powershell on windows) or the terminal inside of your code editor (tested on Visual Studio Code for windows).

1. Clone the repository from GitHub to your desired local directory:
```
cd directory_name
git clone https://github.com/RittgerLabGroup/nm_swe.git
```
2. Create the nm_swe conda environment from the `environment.yml` file:
```
conda env create -f setup/environment.yml
```
This will install all required packages.  

3. Activate the new environment: 
```
conda activate nm_swe
```
4. Verify that the new environment was installed correctly:
```
conda env list
```
5. Select nm_swe kernel for running jupyter notebooks.

## Running the SWE Analysis Code
The current system uses 3 jupyter notebooks in the `notebooks` directory for downloading, plotting and generating tables
