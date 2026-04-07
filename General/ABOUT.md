# Spatial Estimates of SWE for the Rio Grande Basin Using the SWE Evaluation Tool (SWEET)

This repository provides reports, figures, and data for near real-time spatial estimates of Snow Water Equivalent (SWE) across the Rio Grande Basin using the SWE Evaluation Tool (SWEET). SWEET integrates various, suitable data products to build an ensemble of spatially estimated SWE to support hydrologic assessments, water supply forecasting, snow monitoring, and research applications.

For more information or to be added to the distribution list, contact Max Gersh at Max.Gersh@ose.nm.gov.

## Introduction
The Rio Grande (RG) is a snowmelt-driven river system with up to 75% of its water originating from seasonal snowpack in the mountains of Colorado and northern New Mexico (Moeser et al., 2021). Snowpack acts as a natural reservoir in the RG Basin, gradually releasing meltwater during the spring and early summer months, sustaining streamflow and providing vital water supply for downstream users. However, regional decreases in snowpack volume and earlier snowmelt timing, especially throughout the western U.S. and New Mexico, can lead to reduced water availability (Mote et al., 2005; Mote et al., 2018; Hale et al., 2023).

Long-term changes in snowpack patterns and timing can serve as an indicator of climate change, while understanding short-term changes is critical for monitoring seasonal variability and forecasting seasonal water supply. Monitoring snowpack provides valuable data on shifts in precipitation patterns and temperatures, helping scientists and decision-makers better understand and manage climate-related challenges.

Snow water equivalent (SWE) is the estimate of the depth of liquid water contained in the snowpack. SWE is the standard metric in estimating the volume of meltwater in the snowpack, which plays a critical role in the seasonal snow water supply in the RG Basin. SWE is measured at in-situ NRCS Snow Telemetry (SNOTEL) sites throughout the RG Basin and the greater Western U.S. However, the spatial distribution of SWE is complex and often difficult to estimate outside of the in-situ SNOTEL measurements. While SNOTEL provides important point-based measurements, it has been suggested that these data may not be representative of the surrounding snow-covered area (Meromy et al., 2013). Whereas regional tendencies of spatial distribution are consistent, local snowpack volumes are more variable, all of which influences the magnitude and timing of snowmelt-driven runoff.

![Overview map of the Rio Grande (RG) Basin study area. The Rio Grande Headwaters, Upper Rio Grande, and Rio Grande-Elephant Butte Basins are presented as the standard HUC6 basins. HUC8 groupings (Jemez – orange, Rio Chama – green, Sangre de Cristo – yellow, and Upper Rio Grande – brown) are symbolized](General/Overview_Map.png)

## SWE Evaluation Tool (SWEET)
The RG Basin, and more broadly the Western U.S., is experiencing a prolonged and severe drought, exacerbated by a warming climate that increases evapotranspiration, reduces overall snowpack quantity, and reduces the seasonal duration of snowpack. The application of the SWE Evaluation Tool (SWEET) will supply scientists and decision-makers with an improved insight into the spatial distribution of SWE by providing near real-time spatial SWE estimates for the RG Basin, its subbasins, and elevation bands within the basin.

Because no spaceborne sensor can directly measure SWE, spatial distribution of SWE must be estimated from remotely sensed observations coupled with modeling approaches. However, gridded SWE products are known to have accuracy issues across both mountainous and non-mountainous regions (Mudryk et al., 2025), resulting in a range of spatial SWE estimates for any given location. For this reason, the New Mexico Office of the State Engineer (NM OSE) and Institute of Arctic and Alpine Research (INSTAAR) are developing a tool to integrate various, suitable data products to build SWEET based on an ensemble of spatially estimated SWE. By taking an ensemble approach, the goal for SWEET is to provide spatial SWE estimations for the RG Basin that are, on average, equally or more accurate than any individual model.

In the development of SWEET, building from previous research and our expertise, we have selected output from available models. Spatial resolution, temporal resolution, coverage, and data lag are model-dependent. These factors serve as key criteria in determining which models are selected, as they influence the model’s suitability for specific application in the project’s ensemble approach. The following models are included in the ensemble approach for WY2026 and are subject to change in the future.

### SNODAS SWE
The SNOw Data Assimilation System (SNODAS) is a physically based energy and mass-balance snow model, driven by near real-time weather variables that can assimilate available snow data from remote sensing and in situ measurements. SNODAS was developed by NOAA’s National Operational Hydrologic Remote Sensing Center (NOHRSC) and has been produced operationally for the U.S. since 2004. SNODAS estimates multiple snow characteristics on a daily basis by merging satellite, airborne, and in situ snow data with modeled depictions of snow cover. SNODAS generates daily 1-km spatial estimates of snow variables, including SWE, snow depth, snowmelt, sublimation, and snowpack average temperature, that are modeled and made available.

The national SNODAS dataset is publicly available from the National Snow and Ice Data Center (NSIDC) Distributed Active Archive Center (DOI: 10.7265/N5TB14TC; NOHRSC, 2004). SNODAS data can be viewed at the [NOHRSC Interactive Snow Information page](https://www.nohrsc.noaa.gov/interactive/html/map.html). Gridded observed snowfall images, seasonal totals, and data downloads in several formats can be found on the [National Gridded Snowfall Analysis page](https://www.nohrsc.noaa.gov/snowfall_v2/).

For more information on SNODAS, visit the [SNODAS User Guide](https://nsidc.org/sites/default/files/g02158-v001-userguide_2_1.pdf) and the [NSIDC Special Report 11](https://nsidc.org/sites/default/files/nsidc_special_report_11.pdf) (Barrett, 2003).

### UA/SWANN SWE
The University of Arizona/Snow Water Artificial Neural Network Modeling System (UA/SWANN) modeling system is a research product that uses snow models, assimilated in situ SWE data, and artificial neural networks (ANNs) to generate gridded estimates of SWE and snow cover. The UA/SWANN dataset provides daily 4-km and downscaled 800-m (downscaling method described in Broxton et al., 2024) SWE and snow depth over the conterminous United States. The dataset assimilates in-situ measurements from SNOTEL and COOP stations with modeled precipitation and temperature fields (PRISM) to generate spatially continuous estimates.

The UA/SWANN SWE dataset is publicly available from the National Snow and Ice Data Center (NSIDC) Distributed Active Archive Center (DOI: 10.5067/0GGPB220EX6A; Broxton et al., 2019). The UA/SWANN SWE dataset can be viewed at the [SnowView Tool](https://snowview.arizona.edu/).

For more information on UA/SWANN SWE, visit the [UA/SWANN User Guide](https://nsidc.org/sites/default/files/documents/user-guide/nsidc-0719-v001-userguide.pdf) and the [SnowView StoryMap](https://storymaps.arcgis.com/stories/28b6f41ba4934867873c1131c37237fd).

### CU SWE
The University of Colorado (CU) SWE-Fusion product is an operational SWE dataset produced by the Mountain Hydrology Group at INSTAAR, CU Boulder (Professor Noah Molotch, Director). It provides near real-time SWE estimates at a 500-m spatial resolution using a spatial SWE-fusion approach that leverages historical satellite / model-based SWE reanalyses which guides the manner in which SNOTEL SWE are interpolated across the region (Schneider and Molotch, 2016; Yang et al., 2022). The method applies a General Linear Model in which SNOTEL SWE measurements (dependent variable) are related to a suite of independent variables including the historical SWE reanalyses and terrain-related variables. The model output is then scaled by satellite-observed fractional snow-covered area (fSCA) from [Snow Today](https://nsidc.org/snow-today) (Rittger, et. al. 2019) which uses the SPIReS algorithm (Bair, et al. 2021). 
 
The SWE-Fusion framework has been employed by the Mountain Hydrology Group in near-real-time to provide snowpack information for the Sierra Nevada, California since 2012, for the Southern Rockies / Upper Colorado River Basin (Intermountain West) since 2019, and for the Western US since 2025. To view the SWE reports, tables, and figures, visit the Mountain Hydrology Group's [webpage](https://www.colorado.edu/instaar/research/labs-groups/mountain-hydrology-group/western-us-swe-reports).

## Contributors
* Max Gersh, NM Office of the State Engineer Hydrology Bureau
* Logan Stephenson, CU Boulder, INSTAAR
* Ross Palomaki, CU Boulder, INSTAAR
* Karl Rittger, CU Boulder, INSTAAR

## Acknowledgements
The work completed and presented in this report is funded by NASA Western Water Actions Office (WWAO), subcontract no. 1712706, as part of the Rio Grande River Basin Needs Assessment Report (WWAO and DBS&A, 2022). The SWE Evaluation Tool is a collaborative effort from members at INSTAAR, University of Colorado Boulder, and the New Mexico Office of the State Engineer.

We would also like to extend our appreciation to Noah Molotch and the Mountain Hydrology Group at CU Boulder, INSTAAR, for granting our team access to the CU SWE operational SWE dataset. 

## References
Bair, E.H., T. Stillinger and J. Dozier (2021). Snow Property Inversion From Remote Sensing (SPIReS): A Generalized Multispectral Unmixing Approach With Examples From MODIS and Landsat 8 OLI. IEEE Transactions on Geoscience and Remote Sensing, 59(9): 7270-7284. DOI: 10.1109/TGRS.2020.3040328. 

Barrett, Andrew. (2003). National Operational Hydrologic Remote Sensing Center Snow Data Assimilation System (SNODAS) Products at NSIDC. NSIDC Special Report 11. Boulder, CO USA: National Snow and Ice Data Center. 19 pp.

Broxton, P., X. Zeng, and N. Dawson. (2019). Daily 4 km Gridded SWE and Snow Depth from Assimilated In-Situ and Modeled Data over the Conterminous US. (NSIDC-0719, Version 1). SWE Dataset. Boulder, Colorado USA. NASA National Snow and Ice Data Center Distributed Active Archive Center. https://doi.org/10.5067/0GGPB220EX6A.

Broxton, P., M. R. Ehsani, A. Behrangi, M. Reza. (2024). Improving mountain snowpack estimation using machine learning with Sentinel-1, the Airborne Snow Observatory, and University of Arizona snowpack data. Earth and Space Science, https://doi.org/10.1029/2023EA002964.

Hale, K.E., Jennings, K.S., Musselman, K.N., Livneh, B., Molotch, N.P. (2023). Recent decreases in snow water storage in western North America. Communications Earth & Environment, 4(1), p. 170. Available at: https://doi.org/10.1038/s43247-023-00751-3.

Meromy, L., Molotch, N.P., Link, T.E., Fassnacht, S.R., & Rice, R. (2013). Subgrid variability of snow water equivalent at operational snow stations in the western USA. Hydrological Processes, 27, 2383-2400, doi: 10.1002/hyp.9355.

Moeser, C.D., Chavarria, S.B., and Wootten, A.M. (2021). Streamflow response to potential changes in climate in the Upper Rio Grande Basin: U.S. Geological Survey Scientific Investigations Report 2021–5138, 41 p., https://doi.org/10.3133/sir20215138.

Mote, P. W., Hamlet, A. F., Clark, M. P., & Lettenmaier, D. P. (2005). Declining mountain snowpack in western North America. Bulletin of the American Meteorological Society, 86(1), 39–50. https://doi.org/10.1175/BAMS-86-1-39.

Mote, P. W., Li, S., Lettenmaier, D. P., Xiao, M., & Engel, R. (2018). Dramatic declines in snowpack in the western US. Climate and Atmospheric Science, 1, 2. https://doi.org/10.1038/s41612-018-0012-1.

Mudryk, L., Mortimer, C., Derksen, C., Elias Chereque, A., Kushner, P. (2025). Benchmarking of snow water equivalent (SWE) products based on outcomes of the SnowPEx+ Intercomparison Project. The Cryosphere, 19(1), pp. 201–218. Available at: https://doi.org/10.5194/tc-19-201-2025.

NASA Western Water Actions Office [WWAO] and Daniel B. Stephens & Associates, Inc. [DBS&A]. (2022). Rio Grande River Basin Needs Assessment Report. NASA WWAO Assessment Report. Available at: https://wwao.jpl.nasa.gov/documents/138/Water-Needs-Rio-Grande-Report-2022.pdf.

National Operational Hydrologic Remote Sensing Center [NOHRSC]. (2004). Snow Data Assimilation System (SNODAS) Data Products at NSIDC. (G02158, Version 1). SWE Dataset. Boulder, Colorado USA. NSIDC: National Snow and Ice Data Center. https://doi.org/10.7265/N5TB14TC.

Rittger, K., M. S. Raleigh, J. Dozier, A. F. Hill, J. A. Lutz, and T. H. Painter (2019). Canopy Adjustment and Improved Cloud Detection for Remotely Sensed Snow Cover Mapping. Water Resources Research 24 August 2019. doi:10.1029/2019WR024914.

Schneider D. and N.P. Molotch (2016). Real-time estimation of snow water equivalent in the Upper Colorado River Basin using MODIS-based SWE reconstructions and SNOTEL data. Water Resources Research, 52(10): 7892-7910. DOI: 10.1002/2016WR019067. 

Yang, K., K. N. Musselman, K. Rittger, S. A. Margulis, T. H. Painter and N. P. Molotch (2022). Combining ground-based and remotely sensed snow data in a linear regression model for real-time estimation of snow water equivalent. Advances in Water Resources, 160, 2022, 104075. DOI: 10.1016/j.advwatres.2021.104075. 
