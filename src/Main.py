import FileProccesing as fp
import Regions as rg

ALTITUDE_RASTER_PATH = "data/Altitude-rasterize.tif"
ILLUMINATION_RASTER_PATH = "data/SunVisibility(abgvis_85S_060M_201608).tiff"
LABEL_THRESHOLD = 0.0001

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

    # Label regions in the illumination data above a certain threshold
    labeled_regions, region_count = rg.label_regions(scaled_illumination_data, threshold=LABEL_THRESHOLD, greater_than=True)

    # Calculate distances from labeled regions
    distance_array = rg.calculate_distance(labeled_regions, 60)

    # Plot the results
    fp.plot_layers(data=[elevation_data, scaled_illumination_data, slope_data, labeled_regions, distance_array],
                   title=["Elevation", "Scaled Illumination", "Slope", "Labeled Regions", "Distance from Regions"],
                   cmap=["terrain", "gray", "viridis", "nipy_spectral", "plasma"],
                   colorbar_label=["Elevation (m)", "Illumination (%)", "Slope (degrees)", "Region Labels", "Distance (meters)"],
                   save_path=["output/elevation.png", "output/illumination.png", "output/slope.png", "output/labeled_regions.png", "output/distance.png"])

main()