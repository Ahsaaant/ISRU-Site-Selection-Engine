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

def get_illumination_masks(data, scale_factor):
    """
    Creates two masks for the illuminated region based on the raster data and scale factor.
    
    Parameters:
    data (numpy.ndarray): The raster data.
    scale_factor (float): The scale factor for the raster data.
    
    Returns:
    numpy.ndarray: A boolean mask where highly illuminated pixels are True.
    numpy.ndarray: A boolean mask where shadowed pixels are True.
    """

    data = data * scale_factor  # Scale the data using the provided scale factor.

    # Create a boolean mask for the illuminated region and the shadowed region respectively.
    return np.where(data > 0.6, True, False), np.where(data == 0, True, False)

highly_lit_mask, shadowed_mask = get_illumination_masks(data, illumination_scale_factor)