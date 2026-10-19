import numpy as np
import matplotlib.pyplot as plt

import FileProcessing as fp
import Regions as rg
import Analysis as an
import Display as dp

# Constants for file paths
ALTITUDE_RASTER_PATH = "data/Altitude-rasterize.tif"
ILLUMINATION_RASTER_PATH = "data/SunVisibility(abgvis_85S_060M_201608).tiff"

# Constants for thresholds
PSR_THRESHOLD = 0 # The threshold for permanently shdaowed regions
PEL_THRESHOLD = 55 # The threshold for peaks of eternal light (percentage).
REGION_SIZE_THRESHOLD = 10 # The minimum size (in pixels) of regions to be considered.
FEASIBLE_DISTANCE = 2000 # The maximum distance (in meters) between PSR and PEL regions to be considered as a pair.
SLOPE_THRESHOLD = 10 # The maximum average slope (in degrees) for a region to be considered feasible for ISRU operations.

# Constants for analysis
PIXEL_SIZE = 60 # The size of each pixel in meters.

# Weights fpr pair scoring
DISTANCE_WEIGHT = 1.0 # The weight for the distance score in the pair scoring
ILLUMINATION_WEIGHT = 1.0 # The weight for the illumination score in the pair scoring
SIZE_WEIGHT = 1.0 # The weight for the size score in the pair scoring

def main():
    # Load the altitude and illumination raster data
    # altitude_data = fp.read_raster(ALTITUDE_RASTER_PATH)
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
    distance_from_PSR = rg.calculate_distance(PSR_regions, PIXEL_SIZE)
    distance_from_PEL = rg.calculate_distance(PEL_regions, PIXEL_SIZE)

    # Get the data for each PSR and PEL region
    PSR_region_data = rg.region_data(PSR_regions, PSR_region_count, layers={"illumination": scaled_illumination_data, "elevation": elevation_data, "slope": slope_data}, values={"size": PSR_region_sizes})
    PEL_region_data = rg.region_data(PEL_regions, PEL_region_count, layers={"illumination": scaled_illumination_data, "elevation": elevation_data, "slope": slope_data}, values={"size": PEL_region_sizes})

    # Filter the regions based on minimum size and add the appropriate prefix
    size_filtered_PSR_data, omitted_PSR_data = rg.filter_region_data(PSR_region_data, "size", REGION_SIZE_THRESHOLD, greater_than=True, PSR_or_PEL="PSR_")
    size_filtered_PEL_data, omitted_PEL_data = rg.filter_region_data(PEL_region_data, "size", REGION_SIZE_THRESHOLD, greater_than=True, PSR_or_PEL="PEL_")

    # Filter the region based on maximum slope, do not re-apply the prefix
    slope_filtered_PSR_data, omitted_slope_PSR_data = rg.filter_region_data(size_filtered_PSR_data, "PSR_slope", SLOPE_THRESHOLD, greater_than=False)
    slope_filtered_PEL_data, omitted_slope_PEL_data = rg.filter_region_data(size_filtered_PEL_data, "PEL_slope", SLOPE_THRESHOLD, greater_than=False)

    # Pair the PSR's and PEL's based on th1eir region IDs and the distance between them
    paired_data = an.pair_tables(slope_filtered_PSR_data, PSR_regions, slope_filtered_PEL_data, PEL_regions, feasible_distance=FEASIBLE_DISTANCE, pixel_size=PIXEL_SIZE)
    scored_data = an.score_pairs(paired_data, distance_weight=DISTANCE_WEIGHT, illumination_weight=ILLUMINATION_WEIGHT, size_weight=SIZE_WEIGHT, illumination_threshold=PEL_THRESHOLD, feasible_distance=FEASIBLE_DISTANCE)
    print(scored_data)
    
    #Plot the results
    dp.plot_layers(
        data=[elevation_data, scaled_illumination_data, slope_data, PSR_regions, PEL_regions, distance_from_PSR, distance_from_PEL],
        title=["Elevation Data", "Illumination Data", "Slope Data", "PSR Regions", "PEL Regions", "Distance from PSR Regions", "Distance from PEL Regions"],
        cmap=["terrain", "gray", "viridis", "plasma", "plasma", "magma", "magma"],
        colorbar_label=["Elevation (m)", "Illumination (%)", "Slope (degrees)", "Region Labels", "Region Labels", "Distance (pixels)", "Distance (pixels)"],
        save_path="output/plots/"
    )

    # Plot the scored data
    dp.plot(
        table=scored_data,
        title="Scored Data",
        save_path="output/scored_data.png"
    )

    dp.map_pairs(
        raster=scaled_illumination_data,
        table=scored_data,
        PSR_ID_Map=PSR_regions,
        PEL_ID_Map=PEL_regions,
        title="Pair Locations",
        save_path="output/pair_locations.png"
    )

if __name__ == "__main__":
    main()