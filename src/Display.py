import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy import ndimage


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
        if save_path[i]:
            os.makedirs(os.path.dirname(save_path[i]), exist_ok=True)
            plt.savefig(save_path[i], dpi=300, bbox_inches='tight')
    plt.show()

def plot_chart(top_n_pairs, table, title, save_path):
    """
    Plots the score table using matplotlib.
    
    Parameters:
    table (pandas.DataFrame): The data to be plotted.
    title (str): The title of the plot.
    save_path (str): The path to save the plots.

    Returns:
    pandas.DataFrame: The input table, unchanged.
    """

    # Cut the table to the top 5 pairs.
    if len(table) > top_n_pairs:
        table = table.nlargest(top_n_pairs, "total_score")
    elif len(table) == 0:
        print("No pairs to plot.")
        return table
    
    # Chart setup and configuration
    plt.figure(figsize=(10, 6))
    plt.xlabel("Pair ID")
    plt.ylabel("Total Score")
    plt.title(title)

    # Weighted contribution of each criterion
    distance = table["total_score"] * table["distance_percent (%)"] / 100
    illumination = table["total_score"] * table["illumination_percent (%)"] / 100
    size = table["total_score"] * table["size_percent (%)"] / 100

    plt.bar(table.index, distance, width=0.4, color='red', label='Distance')
    plt.bar(table.index, illumination, width=0.4, bottom=distance, color='green', label='Illumination')
    plt.bar(table.index, size, width=0.4, bottom=distance + illumination, color='blue', label='Size')

    plt.legend(title="Score segment")

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    plt.show()

    return table

def map_pairs(top_n_pairs, raster, table, PSR_ID_Map, PEL_ID_Map, title="Pair Locations", save_path=None):
    """
    Maps the scored pairs onto the raster to visualize their locations.
    """
    if len(table) == 0:
        print("No pairs to map.")
        return pd.DataFrame()

    # Cut the table to the top 5 pairs.
    if len(table) > top_n_pairs:
        table = table.nlargest(top_n_pairs, "total_score")

    # Get the PSR and PEL IDs from the table by splitting the Pair_ID column
    Pair_IDs = [(int(row.split(" to ")[0].replace("PSR_", "")), int(row.split(" to ")[1].replace("PEL_", ""))) for row in table.index]

    # Go through the rasters and if an ID matches then keep it else set it to 0
    PSR_location = np.where(np.isin(PSR_ID_Map, [pair[0] for pair in Pair_IDs]), PSR_ID_Map, 0)
    PEL_location = np.where(np.isin(PEL_ID_Map, [pair[1] for pair in Pair_IDs]), PEL_ID_Map, 0)

    # Find the closest point between each pairing, then use it to find the midpoint
    points = []
    for PSR_ID, PEL_ID in Pair_IDs:
        # Distance from every pixel to this PEL, and the coordinates of the PEL pixel it is nearest to
        distance, (nearest_row, nearest_col) = ndimage.distance_transform_edt(PEL_ID_Map != PEL_ID, return_indices=True) # type: ignore

        # The PSR pixel closest to the PEL, and the PEL pixel it is closest to
        PSR_rows, PSR_cols = np.nonzero(PSR_ID_Map == PSR_ID)
        closest = np.argmin(distance[PSR_rows, PSR_cols])
        PSR_row, PSR_col = PSR_rows[closest], PSR_cols[closest]
        PEL_row, PEL_col = nearest_row[PSR_row, PSR_col], nearest_col[PSR_row, PSR_col]

        points.append({"PSR_row": PSR_row, "PSR_col": PSR_col,
                       "PEL_row": PEL_row, "PEL_col": PEL_col,
                       "mid_row": (PSR_row + PEL_row) / 2, "mid_col": (PSR_col + PEL_col) / 2})

    mapped_data = pd.DataFrame(points, index=table.index)

    # Plot the raster with only the paired regions overlaid (0 is masked so it is transparent)
    plt.figure(figsize=(10, 10))
    plt.imshow(raster, cmap="gray")
    plt.imshow(np.ma.masked_equal(PSR_location, 0), cmap="Blues", alpha=0.6)
    plt.imshow(np.ma.masked_equal(PEL_location, 0), cmap="autumn", alpha=0.6)

    # Line between the closest points of each pair, with the midpoint marked
    for pair_id, row in mapped_data.iterrows():
        plt.plot([row["PSR_col"], row["PEL_col"]], [row["PSR_row"], row["PEL_row"]], color="white", linewidth=1)
        plt.annotate(str(pair_id), (row["mid_col"], row["mid_row"]), textcoords="offset points", color="white", fontsize=8) 

    # scatter takes (x, y) = (col, row)
    midpoints = plt.scatter(mapped_data["mid_col"], mapped_data["mid_row"], c=table["total_score"], cmap="viridis", edgecolors="white", s=60, zorder=3)
    plt.colorbar(midpoints, label="Total Score")
    plt.title(title)

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    plt.show()

    return mapped_data


if __name__ == "__main__":
    # Example usage of the functions

    # Example score table
    example_data = pd.DataFrame({
        "Pair_ID": ["PSR_1 to PEL_1", "PSR_2 to PEL_1", "PSR_3 to PEL_2", "PSR_4 to PEL_1", "PSR_5 to PEL_3"],
        "distance": [10, 20, 5, 15, 25],
        "PEL_illumination": [60, 70, 80, 90, 50],
        "PSR_size": [100, 200, 150, 300, 250],
        "distance_score": [0.8, 0.6, 0.9, 0.7, 0.5],
        "illumination_score": [0.6, 0.7, 0.9, 0.8, 0.5],
        "size_score": [0.7, 0.8, 0.9, 0.6, 0.4],
        "total_score": [0.8, 0.6, 0.9, 0.7, 0.5],
        "distance_percent (%)": [20, 30, 10, 25, 15],
        "illumination_percent (%)": [30, 25, 40, 35, 20],
        "size_percent (%)": [50, 45, 50, 40, 65]
    }).set_index("Pair_ID")

    example_PSR_Map = np.array([[1, 1, 0, 0, 4, 4],
                                [1, 1, 0, 0, 4, 4],
                                [0, 0, 0, 0, 0, 0],
                                [2, 2, 0, 0, 5, 5],
                                [2, 2, 0, 0, 5, 5],
                                [0, 0, 3, 3, 0, 0]])

    example_PEL_Map = np.array([[0, 0, 1, 1, 0, 0],
                                [0, 0, 1, 1, 0, 0],
                                [0, 0, 0, 0, 0, 0],
                                [0, 0, 2, 2, 0, 0],
                                [0, 0, 0, 0, 0, 0],
                                [3, 3, 0, 0, 3, 3]])

    map_pairs(top_n_pairs=5, raster=np.zeros(example_PSR_Map.shape), table=example_data, PSR_ID_Map=example_PSR_Map, PEL_ID_Map=example_PEL_Map)