import skimage.morphology
import numpy as np
import pandas as pd
from skimage.filters import threshold_otsu


def measure_bacterial_signal(foreground_mask, intensity_image, props=None):
    """
    Measures bacterial signal properties from foreground and intensity images. This is an omnibus function for multiple bacterial images.
    
    Parameters:
    - foreground_mask: 2D numpy array where each bacterium is labeled with a unique integer.
    - intensity_image: 3D numpy array representing the intensity values of the image. This can include both the constitutive and reporter channels.
    - props: List of properties to extract using skimage.measure.regionprops_table. If None, a default set of properties will be used.
    
    Returns:
    - foreground_props_df: DataFrame containing the measured properties for each bacterium.
    
    """
    
    rng_seed = 406 #For reproducibility of skeletonization--note, this might break in future versions of numpy/skimage
    
    #Set default properties to extract if none are provided
    if props is None:
        props = [
            'label',
            'area',
            'centroid',
            'eccentricity',
            'intensity_mean',
            'intensity_max',
            'intensity_min',
            'intensity_std'
        ]
        
    #Create a skeletonized version of the foreground mask to help with length measurements
    skeleton_image = skimage.morphology.medial_axis(foreground_mask, rng=rng_seed)
    
    #get the lengths of each bacterium by counting the number of pixels in the skeleton that correspond to each label
    bacteria_lengths = np.unique(skeleton_image*foreground_mask, return_counts=True)
    
    #Now, extract properties using skimage and insert these into a dataframe    
    foreground_props_df = pd.DataFrame(skimage.measure.regionprops_table(foreground_mask, intensity_image=intensity_image, properties=props, separator='_'))
    
    
    #Add the lengths we have already taken
    foreground_props_df['length'] = bacteria_lengths[1][1:]  # Skip the background label (0)
    
    #Return the dataframe of measured properties
    return foreground_props_df


#A simple function to segment bacterial constitutive images using Otsu's thresholding
def segment_bacteria(bacteria_image, threshold=None, props=None):
    if threshold is None:
        threshold = threshold_otsu(bacteria_image)
        print(f"Calculated Otsu's threshold: {threshold}")
        
    #First, perform a binary opening of the mask to remove small artifacts
    #Here, we use a disk of radius 2 for the opening
    opened_mask = skimage.morphology.binary_opening(bacteria_image > threshold, skimage.morphology.disk(2))    
    constitutive_labels = skimage.measure.label(opened_mask)    
    return constitutive_labels

#Segments based on overlaps between bacteria and cell labels
def calculate_overlaps(bacteria_labels, cell_labels):
    
    bac_cell_overlaps = skimage.measure.label((bacteria_labels > 0) & (cell_labels > 0))
    label_reference_image = np.stack([cell_labels, bacteria_labels], axis=-1)

    label_props = [ 
        'label',
        'intensity_max',
    ]
    label_props_df = pd.DataFrame(skimage.measure.regionprops_table(bac_cell_overlaps, intensity_image=label_reference_image, properties=label_props, separator='_'))

    return bac_cell_overlaps, label_props_df.astype(np.uint64)


#A simple function to subtract the background from reporter images based on the foreground segmentation from the constitutive image
#NOTE: This could probably go in a separate utilities file
def subtract_background_median(image, labels):
    mask = labels > 0
    median_background = np.median(image[~mask])
    filtered_image = image - median_background
    filtered_image[filtered_image < 0] = 0
    return filtered_image
