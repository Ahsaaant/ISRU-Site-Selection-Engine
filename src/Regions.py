import numpy as np
from scipy import ndimage

def label_regions(data, threshold):
    """
    Labels connected regions in the data that are above a certain threshold.

    Parameters:
    data (numpy.ndarray): The input data array.
    threshold (float): The threshold value to identify regions.

    Returns:
    numpy.ndarray: An array with labeled regions.
    """
    # Create a binary mask where values above the threshold are True
    binary_mask = data > threshold
    
    # Label connected regions in the binary mask using an 8-connectivity structure
    labeled_array, region_count = ndimage.label(binary_mask, structure=[[1,1,1], #type: ignore
                                                          [1,1,1],
                                                          [1,1,1]])
    
    return labeled_array, region_count  # Return the labeled array and the number of features (regions) found

def calculate_distance(labeled_array_one, labeled_array_two):
    """
    Calculates the distance between regions and their closest opposites (e.g highly lit and permanently shadowed).

    Parameters:
    labeled_array_one (numpy.ndarray): The first labeled array.
    labeled_array_two (numpy.ndarray): The second labeled array.

    Returns:
    numpy.ndarray: An array representing the distance between each region pair.
    """
    # Calculate the distance transform for both labeled arrays
    distance_one = ndimage.distance_transform_edt(labeled_array_one == 0)  # type: ignore
    distance_two = ndimage.distance_transform_edt(labeled_array_two == 0)  # type: ignore
    
    # Calculate the absolute difference between the two distance transforms
    distance_difference = np.abs(distance_one - distance_two) # type: ignore
    
    return distance_difference  # Return the distance difference array

# Test functions
if __name__ == "__main__":
    # Example data
    data = np.array([[0, 1, 2, 0],
                     [1, 2, 3, 1],
                     [0, 1, 2, 0],
                     [0, 0, 0, 0],
                     [3, 3, 3, 3]])
    threshold = 1.5

    # Example output
    labeled_regions, region_count = label_regions(data, threshold)
    print("Labeled Regions:\n", labeled_regions)
    print("Number of Regions:", region_count)

    distance = calculate_distance(labeled_regions, labeled_regions)  # Example usage with the same labeled array
    print("Distance Difference:\n", distance)
    