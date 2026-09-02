import numpy as np
'''
A simple function to subtract the background from reporter images based on the foreground segmentation from the constitutive image

    image: the image to be processes
    labels: a labeled image showing foreground and background as zero and non-zero values
    
    returns -> filtered version of image

'''

def subtract_background_median(
    image: np.ndarray, 
    labels:np.ndarray
) -> np.ndarray:
    
    mask = labels > 0
    median_background = np.median(image[~mask])
    filtered_image = image - median_background
    filtered_image[filtered_image < 0] = 0
    return filtered_image