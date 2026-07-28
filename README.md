# ISRU Site Selection Engine

This tool identifies candidate lunar base locations of the south pole of the moon from the proximity to cold traps and well lit power areas.

---

# Data Sources

The data used in the MapProccessor.py are as follows:

1. [LOLA Illumination (ABGVIS_85S_060M_201608)](https://pgda.gsfc.nasa.gov/products/69): The illumination data from NASA's product catalogue, containing the sunvisibility of each 60m x 60m pixel from 85°S (latitude) to the south pole.
2. [LOLA DEM (LDEM_85S_10M_FLOAT)](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/polar/float_img/): The altitude of each 10m x 10m pixel up from 85°S (latitude) to the south pole.

## Notes

The LDEM was processed inside of QGIS to go from km to m to match the pixel spacing which allows for slope calculation, and is also more specifically altidude relative to the 1737.4km reference sphere which is the completely smooth average radius of the moon we use as standard.

---

# Dependencies

All the dependencies can be found in Requirements.txt.
