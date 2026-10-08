import numpy as np, pandas as pd
from scipy import ndimage

def pair_tables(PSR_Table, PSR_Array, PEL_Table, PEL_Array, feasible_distance, pixel_size=60):
    """
    Pairs the PSR and PEL tables based on their region IDs and the distance between them as well as the illuminatino of the PELand the size of the PSR.

    Parameters:
    PSR_Table (pd.DataFrame): The table containing PSR region data.
    PSR_Array (np.ndarray): The array containing PSR region data.
    PEL_Table (pd.DataFrame): The table containing PEL region data.
    PEL_Array (np.ndarray): The array containing PEL region data.
    feasible_distance (float): The maximum distance between PSR and PEL regions to be considered as a pair.
    pixel_size (float): The size of each pixel in meters.

    Returns:
    pd.DataFrame: A new DataFrame containing paired PSR and PEL data.
    """

    pairs = []
    # For each PEL, find all the PSRs within the feasible distance and create a new table with the paired data.
    for PEL_region_id in PEL_Table.index:
        PEL_region_mask = PEL_Array != PEL_region_id
        distance = ndimage.distance_transform_edt(input=PEL_region_mask, sampling=pixel_size)
        minimum_distance = ndimage.minimum(input=distance, labels=PSR_Array, index=PSR_Table.index)

        for PSR_region_id, dist in zip(PSR_Table.index, minimum_distance):
            if dist <= feasible_distance:
                pairs.append({"Pair_ID": f"PSR_{PSR_region_id} to PEL_{PEL_region_id}", "PEL_ID": PEL_region_id, "PSR_ID": PSR_region_id, "distance": dist, "PEL_illumination": PEL_Table.loc[PEL_region_id, "PEL_illumination"], "PSR_size": PSR_Table.loc[PSR_region_id, "PSR_size"]})

    # Create the pandas DataFrame from the pairs list and set the index to "Pair_ID". If no pairs are found, return an empty DataFrame.            
    try:
        paired_table = pd.DataFrame(pairs).set_index("Pair_ID")
    except KeyError:
        paired_table = pd.DataFrame(pairs)
        print("No pairs found within the feasible distance. Returning an empty DataFrame.")

    return paired_table

def score_pairs(paired_table, distance_weight=1.0, illumination_weight=1.0, size_weight=1.0):
    """
    Scores the paired PSR and PEL regions based on their distance, PEL illumination, and PSR size.

    Parameters:
    paired_table (pd.DataFrame): The table containing paired PSR and PEL data.

    Returns:
    pd.DataFrame: A new DataFrame containing the scored pairs and ranked from best to worst.
    """

    # Normalize illumination values to match the magnitude of the size values.
    ILLUMINATION_BALANCE = 5

    # Calculate the score for each pair based on distance, PEL illumination, and PSR size.
    paired_table["score"] = (distance_weight * (1 / (paired_table["distance"] + 1))) + (illumination_weight * ILLUMINATION_BALANCE * paired_table["PEL_illumination"]) + (size_weight * paired_table["PSR_size"])
    
    # Rank the pairs from best to worst based on their score.
    paired_table = paired_table.sort_values("score", ascending=False)
    return paired_table

if __name__ == "__main__":
    # Test use of each function with example data
    Example_PSR_Table = pd.DataFrame({
        'region_id': [1, 2, 3],
        'illumination': [0, 0, 0],
        'elevation': [100, 200, 300],
        'slope': [5, 10, 15],
        'PSR_size': [50, 100, 150]
    }).set_index('region_id')

    Example_PSR_Array = np.array([[1, 1, 0, 3],
                                  [1, 1, 3, 0],
                                  [0, 0, 2, 2],
                                  [0, 0, 2, 2]])

    Example_PEL_Table = pd.DataFrame({
        'region_id': [1, 2],
        'PEL_illumination': [60, 70],
        'elevation': [400, 500],
        'slope': [20, 25],
        'size': [200, 250]
    }).set_index('region_id')

    Example_PEL_Array = np.array([[0, 0, 1, 1],
                                  [0, 0, 1, 1],
                                  [2, 2, 0, 0],
                                  [2, 2, 0, 0]])

    example_distance = 70

    print(pair_tables(Example_PSR_Table, Example_PSR_Array, Example_PEL_Table, Example_PEL_Array, example_distance))