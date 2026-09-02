"""

Takes the manifest.csv and calculates the imaging parameters for the subsamples idenified
    
"""
import pandas as pd
from cellpose import models
import matplotlib.pyplot as plt
import time
import numpy as np
from skimage.filters import threshold_otsu
import yaml

import argparse

from utils.ImageProcessing.subtract_background_median import subtract_background_median

manifest_df = {}

def main():
    #First, load relevant parameters from argv
    parser = argparse.ArgumentParser()
    parser.add_argument('--cp_resample', help="Cellpose resample argument", type=bool, default=True)
    parser.add_argument('--cp_batch_size', help="Cellpose batch size", type=int, default=64)
    parser.add_argument('--cp_min_size', help="Cellpose minimum object size", type=int, default=100)
    parser.add_argument('--manifest', help="Path to the manifest.csv file", type=str, default='./manifest.csv')
    args = vars(parser.parse_args())
    
    sample_images(
        cp_resample = args['cp_resample'],
        cp_batch_size= args['cp_batch_size'],
        cp_min_size= args['cp_min_size'],
        manifest= args['manifest']
    )
    

        
#Function to sample the images based on given paramters:
def sample_images(
    cp_resample: bool,
    cp_batch_size: int,
    cp_min_size: int,
    manifest: str
) -> None:
    
    manifest_df = pd.read_csv(manifest)
    
    #First, extract the list of filepaths for the otsu and cellpose images
    otsu_images_df = manifest_df[manifest_df['otsu_sample']==True]
    cellpose_images_df = manifest_df[manifest_df['cellpose_sample']==True]
    
    #First, get the cellpose parameters:
    cp_diameters = get_cellpose_diameter(
        cellpose_images_df, 
        resample=cp_resample, 
        cp_batch_size=cp_batch_size,
        cp_min_size=cp_min_size
        )
    cp_diameter_median = np.median(cp_diameters)
    
    #Next, get the otsu segmentation for the constitutive images
    constitutive_otsu = get_constitutive_otsu(otsu_images_df)
    constitutive_otsu_med = np.median(constitutive_otsu)
    
    #Finally, get the otsu segmentation for the reporter images
    reporter_otsu = get_reporter_otsu(otsu_images_df, constitutive_otsu_med)
    reporter_otsu_med = np.median(reporter_otsu)
    
    #Now, create the analysis_params.yaml file to store all of this information
    analysis_params = {
        'cellpose_diameters': [float(x) for x in cp_diameters],
        'cellpose_diameter_median': float(cp_diameter_median),
        'constitutive_otsu_vals': [float(x) for x in constitutive_otsu],
        'constitutive_otsu_median': float(constitutive_otsu_med),
        'reporter_otsu_vals': [float(x) for x in reporter_otsu],
        'reporter_otsu_median': float(reporter_otsu_med)
    }
    
    with open('analysis_params.yaml', "w") as f:
        f.write(yaml.dump(analysis_params))
    



#Function to get the cellpose-calculated diameters for a list of images
def get_cellpose_diameter(
        images_df: pd.DataFrame, 
        resample: bool, 
        cp_batch_size: int,
        cp_min_size: int
    ) -> list:
    #if there aren't any cellpose images, then return default values
    if len(images_df) == 0:
        print("No cellpose images were selected for sampling, using default value of 40")
        return([40])
    
    #create a list of all the cellpose filepaths
    cellpose_paths = images_df['CellMask'].tolist()
    
    #load each image to sample and place it in a list
    cellpose_images = []
    for path in cellpose_paths:
        cellpose_images.append(plt.imread(path))
    
    #run cellpose on this list
    print(f'Calculating optimal cellpose paramters for {len(cellpose_images)} images...')
    start_time = time.time()
    model = models.Cellpose(model_type='cyto3', gpu=True)
    masks, flows, styles, diams = model.eval(
        cellpose_images, 
        channels=[0,0], 
        diameter=None, 
        resample=resample, 
        batch_size=cp_batch_size,
        min_size = cp_min_size
    )
    print(f'Calculated a mean cell diameter of {np.round(np.mean(diams),2)} in {np.round(time.time()-start_time, 2)} seconds.')
    return diams

#Function to get the otsu thresholds for a set of constitutive images
def get_constitutive_otsu(images_df: pd.DataFrame) -> list:
    constitutive_paths = images_df['constitutive'].tolist()
    print(f'Calculating Otsu threshold for {len(constitutive_paths)} constitutive images...')
    otsu_thresholds = []
    for path in constitutive_paths:
        image = plt.imread(path)
        otsu_thresholds.append(threshold_otsu(image))
    print(f'Calculated a median constitutive threshold of {np.median(otsu_thresholds)}')
    return otsu_thresholds


#Function to get the otsu thresholds for objects in the reporter channel after they have been segmented using the constitutive channel
def get_reporter_otsu(images_df: pd.DataFrame, constitutive_threshold: int) -> list:
    print(f'Calculating Otsu threshold for {len(images_df)} reporter images...')
    otsu_thresholds = []
    for FOV in images_df.itertuples(index=False):
        constitutive_image = plt.imread(FOV.constitutive)
        reporter_image = plt.imread(FOV.reporter) 
        #Create a constitutive mask
        constitutive_mask = constitutive_image > constitutive_threshold
        #Use the constitutive mask to subtract the background from the reporter image
        reporter_image_filtered = subtract_background_median(reporter_image, constitutive_mask)
        #Now, apply the mask to the filtered image and calculate Otsu
        otsu_thresholds.append(threshold_otsu(reporter_image_filtered * constitutive_mask))
    print(f'Calculated a median reporter threshold of {np.median(otsu_thresholds)}')
    return(otsu_thresholds)

if __name__ == "__main__":
    main()