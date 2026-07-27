import rasterio, numpy as np, scipy, matplotlib.pyplot as plt
from rasterio.warp import reproject, Resampling

# The LOLA reference sphere radius is 1737400 meters, which is used to adjust the altitude data.
ALTITUDE_OFFSET = 1737400

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
            src_nodata = start_data_file.nodata,
            dst_nodata = start_data_file.nodata, # Use the same nodata value for the destination as the source.
            resampling = Resampling.average
        )

        resampled_data[resampled_data == start_data_file.nodata] = np.nan
        return resampled_data

def radius_to_elevation(altitude_data):
    """
    Converts altitude data to elevation data by subtracting the LOLA reference sphere radius.
    
    Parameters:
    altitude_data (numpy.ndarray): The altitude data.
    
    Returns:
    numpy.ndarray: The elevation data.
    """
    return altitude_data - ALTITUDE_OFFSET

def get_illumination_masks(data, scale_factor, lit_threshold=0.6):
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

    # Create a boolean mask for the illuminated region and the shadowed regions (where data is less than or equal to 0) respectively.
    return data > lit_threshold, data <= 0

def elevation_to_slope(elevation_data, pixel_size_x = 60, pixel_size_y = 60):
    """
    Calculates the slope of the elevation data using numpy's gradient function.
    
    Parameters:
    elevation_data (numpy.ndarray): The elevation data.
    pixel_size_x (float): The size of each pixel in the raster data along the x-axis.
    pixel_size_y (float): The size of each pixel in the raster data along the y-axis.
    
    Returns:
    numpy.ndarray: The slope of the elevation data.
    """
    # Calculate the gradient
    grad_y, grad_x = np.gradient(elevation_data, pixel_size_x, pixel_size_y)

    # Calculate the slope as the magnitude of the gradient vector
    tangent = np.sqrt(grad_x**2 + grad_y**2)

    # Convert the tangent to slope in degrees
    slope = np.degrees(np.arctan(tangent))  
    
    return slope

# Read the illumination raster file and get its data and scale factor.
sun_vis_data, sun_vis_scale = read_raster(
    'data/SunVisibility(abgvis_85S_060M_201608).tiff'
    )

# Resample the altitude raster file to match the resolution of the illumination raster file.
resampled_altitude_data = resample_raster(
    'data/Altitude-rasterize.tif',
    'data/SunVisibility(abgvis_85S_060M_201608).tiff'
    )

slope_data = elevation_to_slope(radius_to_elevation(resampled_altitude_data))
highly_lit_mask, shadowed_mask = get_illumination_masks(sun_vis_data, sun_vis_scale)


plt.hist((sun_vis_data * sun_vis_scale) > 0, bins=10, color='blue', alpha=0.7)
print("Count of in-between pixels:", np.sum(((sun_vis_data * sun_vis_scale) > 0.1) & ((sun_vis_data * sun_vis_scale) < 0.9)))
plt.xlabel('Illumination Values')
plt.ylabel('Frequency')
plt.show()