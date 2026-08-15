import numpy as np
import matplotlib.pyplot as plt

import FileProcessing as fp
import Regions as rg

# Constants for file paths
ALTITUDE_RASTER_PATH = "data/Altitude-rasterize.tif"
ILLUMINATION_RASTER_PATH = "data/SunVisibility(abgvis_85S_060M_201608).tiff"

# Constants for thresholds
PSR_THRESHOLD = 0 # The threshold for permanently shdaowed regions
PEL_THRESHOLD = 55 # The threshold for peaks of eternal light (percentage).

def main():
    # Load the altitude and illumination raster data
    altitude_data = fp.read_raster(ALTITUDE_RASTER_PATH)
    illumination_data, illumination_scale_factor = fp.read_raster(ILLUMINATION_RASTER_PATH)

    # Resample the altitude data to match the illumination data
    resampled_altitude_data, pixel_size_x, pixel_size_y = fp.resample_raster(ALTITUDE_RASTER_PATH, ILLUMINATION_RASTER_PATH)

    # Convert altitude to elevation
    elevation_data = fp.radius_to_elevation(resampled_altitude_data)

    # Scale illumination data
    scaled_illumination_data = fp.scale_illumination_data(illumination_data, illumination_scale_factor)

    # Calculate slope from elevation data
    slope_data = fp.elevation_to_slope(elevation_data, pixel_size_x=pixel_size_x, pixel_size_y=pixel_size_y)

    # Create a validity map based on the input layers
    valid_map = rg.validate_layers([scaled_illumination_data, elevation_data, slope_data])

    # Label regions in the illumination data according to the PSR and PEL thresholds
    PSR_regions, PSR_region_count = rg.label_regions(scaled_illumination_data, valid_map, threshold=PSR_THRESHOLD, greater_than=False)
    PEL_regions, PEL_region_count = rg.label_regions(scaled_illumination_data, valid_map, threshold=PEL_THRESHOLD, greater_than=True)

    # Find the area of labelled regions
    PSR_region_sizes, PSR_size_stats = rg.region_sizes(PSR_regions)
    PEL_region_sizes, PEL_size_stats = rg.region_sizes(PEL_regions)

    # Calculate distances from labeled regions
    distance_from_PSR = rg.calculate_distance(PSR_regions, 60)
    distance_from_PEL = rg.calculate_distance(PEL_regions, 60)

    PSR_region_data = rg.region_data(PSR_regions, PSR_region_count, layers={"illumination": scaled_illumination_data, "elevation": elevation_data, "slope": slope_data}, values={"size": PSR_region_sizes})
    PEL_region_data = rg.region_data(PEL_regions, PEL_region_count, layers={"illumination": scaled_illumination_data, "elevation": elevation_data, "slope": slope_data}, values={"size": PEL_region_sizes})

    filtered_PSR_data, omitted_PSR_data = rg.filter_region_data(PSR_region_data, "size", 10, greater_than=True)
    filtered_PEL_data, omitted_PEL_data = rg.filter_region_data(PEL_region_data, "size", 10, greater_than=True)

    print("PSR Region Data:\n", filtered_PSR_data)
    print("Omitted PSR Region Data:\n", omitted_PSR_data)
    print("PEL Region Data:\n", filtered_PEL_data)
    print("Omitted PEL Region Data:\n", omitted_PEL_data)

    # Plot the results
    fp.plot_layers(
        data=[elevation_data, scaled_illumination_data, slope_data, PSR_regions, PEL_regions, distance_from_PSR, distance_from_PEL],
        title=["Elevation Data", "Illumination Data", "Slope Data", "PSR Regions", "PEL Regions", "Distance from PSR Regions", "Distance from PEL Regions"],
        cmap=["terrain", "gray", "viridis", "plasma", "plasma", "magma", "magma"],
        colorbar_label=["Elevation (m)", "Illumination (%)", "Slope (degrees)", "Region Labels", "Region Labels", "Distance (pixels)", "Distance (pixels)"]
    )

main()