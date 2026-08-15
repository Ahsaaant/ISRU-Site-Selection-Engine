import rasterio, numpy as np, matplotlib.pyplot as plt
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


def scale_illumination_data(data, scale_factor):
    """
    Scale the data of the illumination raster to get a percentage of time that each pixel is illuminated.
    
    Parameters:
    data (numpy.ndarray): The raster data.
    scale_factor (float): The scale factor for the raster data.

    Returns:
    numpy.ndarray: An array representing the illumination of the pixels.
    """

    # Scale the data and convert it to a percentage
    return (data * scale_factor) * 100


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
        # if save_path[i]:
        #     plt.savefig(save_path[i], dpi=300, bbox_inches='tight')
    plt.show()

# Test the functions
if __name__ == "__main__":
    # Example usage of the functions
    altitude_raster_path = "data/Altitude-rasterize.tif"
    illumination_raster_path = "data/SunVisibility(abgvis_85S_060M_201608).tiff"

    # Read raster data
    illumination_data, illumination_scale_factor = read_raster(illumination_raster_path)
    
    # Resample raster data
    resampled_altitude_data, pixel_size_x, pixel_size_y = resample_raster(altitude_raster_path, illumination_raster_path)
    
    # Convert altitude to elevation
    elevation_data = radius_to_elevation(resampled_altitude_data)
    
    # Scale illumination data
    scaled_illumination_data = scale_illumination_data(illumination_data, illumination_scale_factor)
    
    # Calculate slope from elevation data
    slope_data = elevation_to_slope(elevation_data, pixel_size_x, pixel_size_y)
    
    # Plot the layers
    plot_layers(
        data=[elevation_data, scaled_illumination_data, slope_data],
        title=["Elevation Data", "Illumination Data", "Slope Data"],
        cmap=["terrain", "gray", "viridis"],
        colorbar_label=["Elevation (m)", "Illumination (%)", "Slope (degrees)"]
    )