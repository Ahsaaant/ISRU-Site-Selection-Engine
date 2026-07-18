import rasterio, numpy as np, scipy, matplotlib.pyplot as plt

def read_raster(file_path):
    """
    Reads a raster file and returns its data as a numpy array.
    
    Parameters:
    file_path (str): The path to the raster file.
    
    Returns:
    numpy.ndarray: The data from the raster file.
    float: The scale factor for the raster data.
    """
    with rasterio.open(file_path) as src:
        return src.read(1), src.scales[0]

# Read the raster file and get its data and scale factor.
data, illumination_scale_factor = read_raster('data/SunVisibility(abgvis_85S_060M_201608).tiff')

permanently_shadowed_region = [pixel > 0 for pixel in data.flatten()]
print(data)