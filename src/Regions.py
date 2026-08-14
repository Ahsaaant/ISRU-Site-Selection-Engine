import numpy as np, pandas as pd
from scipy import ndimage


def label_regions(data, threshold, greater_than=True):
    """
    Labels connected regions in the data that are above a certain threshold.

    Parameters:
    data (numpy.ndarray): The input data array.
    threshold (float): The threshold value to identify regions.
    greater_than (bool, optional): Whether to label regions greater than the threshold. Defaults to True.

    Returns:
    numpy.ndarray: An array with labeled regions.
    """
    # Create a binary mask where values above or below the threshold are True
    if greater_than:
        binary_mask = data >= threshold
    else:
        binary_mask = data <= threshold

    # Label connected regions in the binary mask using an 8-connectivity structure
    labeled_array, region_count = ndimage.label(binary_mask, structure=[[1,1,1], #type: ignore
                                                          [1,1,1],
                                                          [1,1,1]])
    
    return labeled_array, region_count  # Return the labeled array and the number of features (regions) found


def calculate_distance(labeled_array, units=1):
    """
    Calculates the distance of each pixel to the nearest labeled region in the input array.

    Parameters:
    labeled_array (numpy.ndarray): The labeled array of regions.
    units (float, optional): The scale factor for the distance calculation. Defaults to 1.

    Returns:
    numpy.ndarray: An array representing the distance between each region pair.
    """

    # Map of distance from the nearest labelled region
    distance_array = ndimage.distance_transform_edt(labeled_array == 0)  # type: ignore
    distance_array = np.where(distance_array == 0, np.nan, distance_array) #type: ignore
    distance_array *= units  # Scale the distances by the specified units

    return distance_array  # Return the distance array scaled by the specified units

def region_sizes(labeled_array):
    """
    Calculates the area of each labeled region in the input array.

    Parameters:
    labeled_array (numpy.ndarray): The labeled array of regions.

    Returns:
    size_array (numpy.ndarray): An array containing the sizes of each labeled region.
    size_stats (dict): A dictionary containing statistics about the sizes of the labeled regions.
    """

    size_array = np.bincount(labeled_array.flatten())[1:]  # Count the number of pixels in each labeled region not including the background (label 0)
    size_stats = {
        "total_regions": len(size_array),
        "largest_region_size": np.max(size_array),
        "smallest_region_size": np.min(size_array[size_array > 0]) if np.any(size_array > 0) else 0,
        "mean_region_size": np.mean(size_array)
    }
    return size_array, size_stats  # Return the sizes of each labeled region and the statistics

def region_data(labeled_array, region_count, layers={}, values={}):
    """
    Creates a table containing each region with the corresponding data from the given layers.

    Parameters:
    labeled_array (numpy.ndarray): The labeled array of regions.
    region_count (int): The number of labeled regions.
    layers (dict of numpy.ndarray): The dictionary of layers (illumination, slope, elevation, size) that we compute the data from.
    values (dict): The dictionary of values (size, etc.) that we get the data from.

    Returns:
    region_table (DataFrame): A DataFrame where rows represent regions and columns represent the data from each layer.
    """

    region_table = pd.DataFrame()
    region_table["region_id"] = np.arange(1, region_count + 1)  # Create a column for region IDs

    for layer_name, layer_data in layers.items():
        if layer_data is None:
            continue
        else:
            region_table[layer_name] = ndimage.mean(layer_data, labels=labeled_array, index=np.arange(1, region_count + 1))
    for value_name, value_data in values.items():
        if value_data is None:
            continue
        else:
            region_table[value_name] = value_data

    return region_table



# Test functions
if __name__ == "__main__":
    # Example data
    data = np.array([[0, 1, 2, 0],
                     [1, 2, 3, 1],
                     [0, 1, 2, 0],
                     [0, 0, 0, 0],
                     [3, 3, 3, 3]])
    threshold = 1
    greater_than = True

    # Example output
    labeled_regions, region_count = label_regions(data, threshold, greater_than)
    print("Labeled Regions:\n", labeled_regions)
    print("Number of Regions:", region_count)

    distance = calculate_distance(labeled_regions)  # Example usage with the same labeled array
    print("Distances from labelled regions:\n", distance)

    sizes, stats = region_sizes(labeled_regions)
    print("Region Sizes:", sizes)
    print("Region Size Statistics:", stats)

    layer = np.array([[8, 10, 30, 0],
                      [1, 28, 34, 12],
                      [0, 13, 2, 0],
                      [5, 1, 7, 9],
                      [3, 100, 99, 39]])
    
    region_data_dict = region_data(labeled_regions, region_count, layers={"illumination (%)": layer, "elevation": layer, "slope": None}, values={"size": None})
    print("Region Data:\n", region_data_dict)