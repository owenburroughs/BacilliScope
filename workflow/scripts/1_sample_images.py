# ---------------------------------------------------------------
# STEP 1: SAMPLE IMAGES
#
# Take a list of all the images in a plate folder, subsample these,
# and generate our OTSU thresholds and (optionally) cellpose params.
# ---------------------------------------------------------------
import sys
import re
import random
import json
import numpy as np


from typing import TYPE_CHECKING
from PIL import Image
from skimage.filters import threshold_otsu
from utils.BacteriaAnalysis import subtract_background_median

if TYPE_CHECKING:
    from snakemake.iocontainers import snakemake
    
# ----------------------------------   
# UTILITY FUNCTIONS
# ----------------------------------
    
# ---------- Deterministic Subsample ------
# Given a list of images, deterministically subsample them based on the plate name
def deterministic_subsample(seed:str, number: int, list: list)->list:
    random.seed(seed) # set seed so this is deterministic
    return random.choices(list, k=number)

    
# ---------- ImageXpress assert images come from same plate ------------
def ImageXpressAssert(image1: str, image2: str)->None:
    name_re = re.compile(r'(?P<prefix>.*)_w(\d+)_(?P<suffix>.*)')
    image1_dict = name_re.search(image1).groupdict()
    image2_dict = name_re.search(image2).groupdict()
    assert image1_dict['prefix'] == image2_dict['prefix'] and image1_dict['suffix'] == image2_dict['suffix']


# ----------- Function to get the otsu thresholds for a set of constitutive images
def get_constitutive_otsu(FOVs: list) -> list:
    print(f'Calculating Otsu threshold for {len(FOVs)} constitutive images...')
    otsu_thresholds = []
    for FOV in FOVs:
        image = np.asarray(Image.open(FOV['constitutive']))
        otsu_thresholds.append(threshold_otsu(image))
    print(f'Calculated a median constitutive threshold of {np.median(otsu_thresholds)}')
    return otsu_thresholds


# -------------- Get the otsu thresholds for reporter channel after segmenting with constitutive channel
def get_reporter_otsu(FOVs: list, constitutive_threshold: int) -> list:
    print(f'Calculating Otsu threshold for {len(FOVs)} reporter images...')
    otsu_thresholds = []
    for FOV in FOVs:
        constitutive_image = np.asarray(Image.open(FOV['constitutive']))
        reporter_image = np.asarray(Image.open(FOV['reporter']))
        #Create a constitutive mask
        constitutive_mask = constitutive_image > constitutive_threshold
        #Use the constitutive mask to subtract the background from the reporter image
        reporter_image_filtered = subtract_background_median(reporter_image, constitutive_mask)
        #Now, apply the mask to the filtered image and calculate Otsu
        otsu_thresholds.append(threshold_otsu(reporter_image_filtered * constitutive_mask))
    print(f'Calculated a median reporter threshold of {np.median(otsu_thresholds)}')
    return(otsu_thresholds)


# ----------------------------------   
# MAIN FUNCTION 
# ----------------------------------

def sample_images(
    plate_directory: str,
    cellmask_images: list,
    constitutive_images: list,
    reporter_images: list,
    sample_proportion: float,
    params_file: str
):  
    # ------ First, create a list of all of our images ---------
    # For debugging and sanity checking, make sure that the consitutive and reporter images are from the same FOV
    FOVs = []
    for constitutive, reporter in zip(constitutive_images, reporter_images):
        ImageXpressAssert(constitutive, reporter)
        
        FOVs.append({
            'constitutive': constitutive,
            'reporter': reporter
        })
        
    # ------ Subsample the images to work on ----------
    sample_size = round(len(FOVs) * sample_proportion)
    sampled_FOVs = deterministic_subsample(plate_directory, sample_size, FOVs)
    
    # ------ Calculate thresholds ---------
    #First, get the otsu segmentation for the constitutive images
    constitutive_otsu = get_constitutive_otsu(sampled_FOVs)
    constitutive_otsu_med = np.median(constitutive_otsu)
    
    #Finally, get the otsu segmentation for the reporter images
    reporter_otsu = get_reporter_otsu(sampled_FOVs, constitutive_otsu_med)
    reporter_otsu_med = np.median(reporter_otsu)
    
    # ----- Save Analysis Params ----------
    analysis_params = {
        'constitutive_otsu_vals': [float(x) for x in constitutive_otsu],
        'constitutive_otsu_median': float(constitutive_otsu_med),
        'reporter_otsu_vals': [float(x) for x in reporter_otsu],
        'reporter_otsu_median': float(reporter_otsu_med)
    }
    
    print(analysis_params)
    
    with open(params_file, 'wt') as handle:
        json.dump(analysis_params, handle)

    
# ---------- MAIN FUNCTION ----------------
if __name__ == "__main__":
    try:
        sample_images(
            plate_directory= snakemake.input['plate_directory'],
            cellmask_images= snakemake.input['cellmask_images'],
            constitutive_images= snakemake.input['constitutive_images'],
            reporter_images= snakemake.input['reporter_images'],
            sample_proportion= snakemake.params['sample_proportion'],
            params_file= snakemake.output['params_file']
        )
    except NameError:
        sys.exit(0)