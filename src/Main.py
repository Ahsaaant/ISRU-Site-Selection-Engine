import FileProccesing as fp
import Regions as rg

# Constants for file paths
ALTITUDE_RASTER_PATH = "data/Altitude-rasterize.tif"
ILLUMINATION_RASTER_PATH = "data/SunVisibility(abgvis_85S_060M_201608).tiff"

# Constants for thresholds
PSR_THRESHOLD = 0 # The threshold for permanently shdaowed regions
PEL_THRESHOLD = 75 # The threshold for peaks of eternal light (percentage).

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

    # Label regions in the illumination data according to the PSR and PEL thresholds
    PSR_regions, region_count = rg.label_regions(scaled_illumination_data, threshold=PSR_THRESHOLD, greater_than=False)
    PEL_regions, region_count = rg.label_regions(scaled_illumination_data, threshold=PEL_THRESHOLD, greater_than=True)

    # Calculate distances from labeled regions
    distance_from_PSR = rg.calculate_distance(PSR_regions, 60)
    distance_from_PEL = rg.calculate_distance(PEL_regions, 60)

    # Plot the results
    fp.plot_layers(data=[scaled_illumination_data, PSR_regions, distance_from_PSR, PEL_regions, distance_from_PEL, slope_data, elevation_data],
                   title=["Scaled Illumination", "Labeled Regions", "Distance from PSR", "Labeled Regions", "Distance from PEL", "Slope", "Elevation"],
                   cmap=["gray", "nipy_spectral", "plasma", "nipy_spectral", "plasma", "terrain", "viridis"],
                   colorbar_label=["Illumination (%)", "PSR Regions", "Distance (meters)", "PEL Regions", "Distance (meters)", "Slope (degrees)", "Elevation (meters)"],
                   save_path=["output/illumination.png", "output/psr_regions.png", "output/distance_from_psr.png", "output/pel_regions.png", "output/distance_from_pel.png", "output/slope.png", "output/elevation.png"])

main()