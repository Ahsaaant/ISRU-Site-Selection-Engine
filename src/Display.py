import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


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

def plot(table, title, save_path):
    """
    Plots the score table using matplotlib.
    
    Parameters:
    table (pandas.DataFrame): The data to be plotted.
    title (str): The title of the plot.
    save_path (str): The path to save the plots.
    """

    # Chart setup and configuration
    plt.figure(figsize=(10, 6))
    plt.xlabel("Pair ID")
    plt.ylabel("Total Score")
    plt.title(title)

    # Weighted contribution of each criterion
    distance = table["distance_score"] * table["distance_percent"] / 100
    illumination = table["illumination_score"] * table["illumination_percent"] / 100
    size = table["size_score"] * table["size_percent"] / 100

    plt.bar(table.index, distance, width=0.4, color='red', label='Distance')
    plt.bar(table.index, illumination, width=0.4, bottom=distance, color='green', label='Illumination')
    plt.bar(table.index, size, width=0.4, bottom=distance + illumination, color='blue', label='Size')

    plt.legend(title="Score segment")

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    plt.show()


if __name__ == "__main__":
    # Example usage of the functions

    # Example score table
    example_data = pd.DataFrame({
        "Pair_ID": ["PSR1_PEL1", "PSR2_PEL1", "PSR3_PEL2", "PSR4_PEL1", "PSR5_PEL3"],
        "distance": [10, 20, 5, 15, 25],
        "PEL_illumination": [60, 70, 80, 90, 50],
        "PSR_size": [100, 200, 150, 300, 250],
        "distance_score": [0.8, 0.6, 0.9, 0.7, 0.5],
        "illumination_score": [0.6, 0.7, 0.9, 0.8, 0.5],
        "size_score": [0.7, 0.8, 0.9, 0.6, 0.4],
        "total_score": [0.8, 0.6, 0.9, 0.7, 0.5],
        "distance_percent": [20, 30, 10, 25, 15],
        "illumination_percent": [30, 25, 40, 35, 20],
        "size_percent": [50, 45, 50, 40, 65]
    }).set_index("Pair_ID")

    plot(table=example_data, title="Example Score Data", save_path="output/example_score_data.png")