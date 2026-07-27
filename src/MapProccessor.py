import rasterio, numpy as np, scipy, matplotlib.pyplot as plt
from rasterio.warp import reproject, Resampling

# rasterio 1.5.0 triggers a NumPy 2.5 shape deprecation in .scales; harmless, tracked upstream.
import warnings
warnings.filterwarnings(
    "ignore",
    message="Setting the shape on a NumPy array has been deprecated",
    category=DeprecationWarning,
)

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
    Resamples the raster data based on the provided target data to mimic its resolution.
    
    Parameters:
    source_data_path (str): The path to the source raster file.
    target_data_path (str): The path to the target raster file.
    
    Returns:
    numpy.ndarray: The resampled raster data.
    float: The pixel size along the x-axis of the target raster.
    float: The pixel size along the y-axis of the target raster.
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
        return resampled_data, target_data_file.res[0], target_data_file.res[1]  # Return the resampled data along with the pixel sizes.

def radius_to_elevation(altitude_data):
    """
    Converts altitude data to elevation data by subtracting the LOLA reference sphere radius.
    
    Parameters:
    altitude_data (numpy.ndarray): The altitude data.
    
    Returns:
    numpy.ndarray: The elevation data.
    """

    return altitude_data - ALTITUDE_OFFSET

def get_illumination_masks(data, scale_factor, lit_threshold=0.44):
    """
    Creates two masks based on the illuminated and shadowed regions of the raster.
    
    Parameters:
    data (numpy.ndarray): The raster data.
    scale_factor (float): The scale factor for the raster data.
    lit_threshold (float): The threshold value to determine highly illuminated pixels.
    
    Returns:
    numpy.ndarray: A boolean mask where highly illuminated pixels are True.
    numpy.ndarray: A boolean mask where shadowed pixels are True.
    """

    data = data * scale_factor  # Scale the data using the provided scale factor.

    # Create a boolean mask for the illuminated region and the shadowed regions (where data is less than or equal to 0) respectively.
    return data > lit_threshold, data <= 0

def elevation_to_slope(elevation_data, pixel_size_x, pixel_size_y):
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

def plot_layers(data = [], title = [], cmap = [], colorbar_label = [], save_path = []):
    """
    Plots raster layers using matplotlib.
    
    Parameters:
    data (list of np.ndarray): The raster data to be plotted.
    title (list of str): The titles of the plots.
    cmap (list of str): The colormaps to be used for the plots.
    colorbar_label (list of str): The labels for the colorbars.
    """

    for i in range(len(data)):
        plt.figure(figsize=(10, 10))
        plt.imshow(data[i], cmap=cmap[i])
        plt.title(title[i])
        cbar = plt.colorbar()
        cbar.set_label(colorbar_label[i])
        
    plt.show()

# Read the illumination raster file and get its data and scale factor.
sun_vis_data, sun_vis_scale = read_raster(
    'data/SunVisibility(abgvis_85S_060M_201608).tiff'
    )

# Read the altitude raster file and get its raw data and scale factor.
raw_altitude_data, altitude_scale = read_raster(
    'data/Altitude-rasterize.tif'
    )

# Resample the altitude raster file to match the resolution of the illumination raster file.
resampled_altitude_data, resampled_pixel_size_x, resampled_pixel_size_y = resample_raster(
    'data/Altitude-rasterize.tif',
    'data/SunVisibility(abgvis_85S_060M_201608).tiff'
    )

# Calculate the slope of the resampled elevation data using the pixel sizes from the raw altitude data.
slope_data = elevation_to_slope(radius_to_elevation(resampled_altitude_data), resampled_pixel_size_x, resampled_pixel_size_y)

# Get the two light masks based on the illumination data and its scale factor.
highly_lit_mask, shadowed_mask = get_illumination_masks(sun_vis_data, sun_vis_scale)
print(highly_lit_mask.sum())

plot_layers(
    data = [radius_to_elevation(resampled_altitude_data), slope_data, highly_lit_mask, shadowed_mask],
    title = ['Elevation Map', 'Slope Map', 'Highly Lit Mask', 'Shadowed Mask'],
    cmap = ['terrain', 'viridis', 'gray', 'gray'],
    colorbar_label = ['Elevation (m)', 'Slope (degrees)', 'Highly Lit Pixels', 'Shadowed Pixels'],
)