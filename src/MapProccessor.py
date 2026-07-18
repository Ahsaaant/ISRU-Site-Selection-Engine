import rasterio, numpy as np, scipy, matplotlib.pyplot as plt


ILLUMINATION_SCALING_FACTOR = 0.00004

# Open the raster file and read it's data.
file = rasterio.open('SunVisibility(abgvis_85S_060M_201608).tiff')
data = file.read(1)

illumination_array = []

for pixel in data:
    illumination_array.append(pixel * ILLUMINATION_SCALING_FACTOR)
