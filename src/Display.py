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

def plot_graph(data=[], titles=[], x_labels=[], y_labels=[], save_path=[]):
    """
    Plots graphs using matplotlib.
    
    Parameters:
    data (list of tuples): The data to be plotted, where each tuple contains (x, y) values.
    titles (list of str): The titles of the plots.
    x_labels (list of str): The labels for the x-axes.
    y_labels (list of str): The labels for the y-axes.
    save_path (list of str): The paths to save the plots.
    """

    for i in range(len(data)):
        plt.figure(figsize=(10, 6))
        plt.plot(data[i][0], data[i][1])
        plt.title(titles[i])
        plt.xlabel(x_labels[i])
        plt.ylabel(y_labels[i])
        if save_path[i]:
            plt.savefig(save_path[i], dpi=300, bbox_inches='tight')
    plt.show()