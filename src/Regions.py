import numpy as np
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
    
    return distance_array  # Return the distance array scaled by the specified units


# Test functions
if __name__ == "__main__":
    # Example data
    data = np.array([[0, 1, 2, 0],
                     [1, 2, 3, 1],
                     [0, 1, 2, 0],
                     [0, 0, 0, 0],
                     [3, 3, 3, 3]])
    threshold = 1

    # Example output
    labeled_regions, region_count = label_regions(data, threshold, False)
    print("Labeled Regions:\n", labeled_regions)
    print("Number of Regions:", region_count)

    distance = calculate_distance(labeled_regions)  # Example usage with the same labeled array
    print("Distances from labelled regions:\n", distance)
    