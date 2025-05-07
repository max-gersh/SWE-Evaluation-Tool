# nm_swe
Analysis, figures and tables for NM OSE SWE reports  
This repository is used to generate weekly snow water equivalent (SWE) reports for the northern Rio Grande River Basin in Colorado and New Mexico. Code is included to download SNODAS SWE estimates from https://noaadata.apps.nsidc.org/NOAA/G02158/ and generate summary figures and tables. Future updates will include additonal SWE estimates including UA/SWANN (https://climate.arizona.edu/data/UA_SWE/) and CU SWE. 

## Setup
1. Clone the repository:
```
git clone https://github.com/RittgerLabGroup/nm_swe.git
```
2. Create the nm_swe conda environment from the `environment.yml` file:
```
conda env create -f setup/environment.yml
```
This will install all required modules.  

3. Activate the new environment: 
```
conda activate nm_swe
```

5. Verify that the new environment was installed correctly:
```
conda env list
```

5. Select nm_swe kernel for running jupyter notebooks.  
