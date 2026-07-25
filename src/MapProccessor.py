import rasterio, numpy as np, scipy, matplotlib.pyplot as plt
from rasterio.warp import reproject, Resampling

def read_raster(file_path):
    """
    Reads a raster file and returns its data as a numpy array with required metadata.
    
    Parameters:
    file_path (str): The path to the raster file.
    
    Returns:
    numpy.ndarray: The data from the raster file.
    float: The scale factor for the raster data.
    """
    with rasterio.open(file_path) as src:
        return src.read(1), src.scales[0]

def resample_raster(source_data_path, target_data_path):
    """
    Resamples the raster data based on the provided scale factor.
    
    Parameters:
    source_data_path (str): The path to the source raster file.
    target_data_path (str): The path to the target raster file.
    
    Returns:
    numpy.ndarray: The resampled raster data.
    """
    with rasterio.open(source_data_path) as start_data_file, rasterio.open(target_data_path) as target_data_file:

        # Create an empy numpy array with the new shape based on the target data shape.
        resampled_data = np.empty(target_data_file.shape, dtype=start_data_file.dtypes[0])

        reproject(
            source = rasterio.band(start_data_file, 1),
            destination = resampled_data,
            src_transform = start_data_file.transform,
            dst_transform = target_data_file.transform,
            src_crs = start_data_file.crs,
            dst_crs = target_data_file.crs,
            resampling = Resampling.average
        )

        return resampled_data


# Read the raster file and get its data and scale factor.
sun_vis_data, sun_vis_scale = read_raster(
    'data/SunVisibility(abgvis_85S_060M_201608).tiff'
    )

altitude_data, altitude_scale = read_raster(
    'data/Altitude-rasterize.tif'
    )

def get_illumination_masks(data, scale_factor):
    """
    Creates two masks based on the illuminated and shadowed regions of the raster.
    
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

highly_lit_mask, shadowed_mask = get_illumination_masks(sun_vis_data, sun_vis_scale)

resampled_altitude_data = resample_raster(
    'data/Altitude-rasterize.tif',
    'data/SunVisibility(abgvis_85S_060M_201608).tiff'
    )
print("Resampled Altitude Data Shape:", resampled_altitude_data.shape)