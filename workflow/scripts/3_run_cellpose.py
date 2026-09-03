"""
    3_run_cellpose.py
    
    A script that runs cellpose in user-defined batch sizes based on a set of input files in manifest.csv
   
   inputs: 
   
   outputs: 
"""

import argparse
from cellpose import models
import pandas as pd
from itertools import batched
from matplotlib.pyplot import imread
from PIL import Image
import yaml
from yaml import CLoader as Loader
import time
import numpy as np
import gc

def run_cellpose(
    cp_image_pool_size: int,
    cp_batch_size: int,
    cp_min_size: int,
    cp_resample: bool,
    manifest: str,
    analysis_params: str,
    output_folder: str
    ) -> None:
    
    #load manifest.csv 
    manifest_df = pd.read_csv(manifest)
    
    #load analysis_params.yaml
    with open(analysis_params) as f:
        analysis_params_dict = yaml.load(f, Loader=Loader)
    
    #create a tuple where the first value is a list of all FOV_ids, and the second value is the corresponding filepaths for the CellMask image
    cellpose_images = manifest_df[['FOV_id','CellMask']]
    
    #If the image pool size is 0, this means that we aren't processing in batches and should process everything immediately
    if cp_image_pool_size == 0: cp_image_pool_size = len(cellpose_images)
    
    #Instantiate cellpose
    model = models.Cellpose(model_type='cyto3', gpu=True)    
    
    #Process images in batches
    print(f'Running cellpose on {len(cellpose_images)} images in batches of size {cp_image_pool_size}')
    for image_pool in batched(cellpose_images.itertuples(index=False, name=None), cp_image_pool_size):
        start_time = time.time()
        #Load all images from a single pool into a list
        cellpose_images = []
        for image in image_pool:
            cellpose_images.append(imread(image[1]))
        
        #Run cellpose on these images
        masks, flows, styles, diams = model.eval(
            cellpose_images, 
            channels=[0,0], 
            diameter=analysis_params_dict['cellpose_diameter_median'], 
            resample=cp_resample, 
            batch_size=cp_batch_size,
            min_size = cp_min_size
        )
        
        assert(len(masks) == len(image_pool)) #Make sure that every image in the pool has a corresponding mask
        
        #Save cellpose results as new files
        for mask, pool_item in zip(masks, image_pool):
            image = Image.fromarray(mask)
            image.save(f'{output_folder}/{pool_item[0]}_cellpose.tif', compression="tiff_adobe_deflate")
            
        run_time = np.round(time.time() - start_time, 2)
        print(f'Processed {len(image_pool)} images in {run_time} seconds. Averaged {np.round(run_time / len(image_pool),2)} seconds per image.')
        
        #Free up memory for next batch
        masks = []
        flows = []
        styles = []
        gc.collect()


def main():
    #First, load relevant parameters from argv
    parser = argparse.ArgumentParser()
    parser.add_argument('--cp_image_pool_size', help="Number of images to process with cellpose simultaneously", type=int, default=16)
    parser.add_argument('--cp_batch_size', help="Cellpose batch size", type=int, default=64)
    parser.add_argument('--cp_min_size', help="Cellpose minimum object size", type=int, default=100)
    parser.add_argument('--cp_resample', help="Cellpose resample argument", type=bool, default=True)
    parser.add_argument('--output_folder', help="Folder to output cellpose masks", type=str)
    args = vars(parser.parse_args())
    
    run_cellpose(
        cp_image_pool_size=args['cp_image_pool_size'],
        cp_batch_size=args['cp_batch_size'],
        cp_min_size=args['cp_min_size'],
        cp_resample=args['cp_resample'],
        analysis_params='analysis_params.yaml', #We can hard-code this in this case because snakemake will ensure that it exists
        manifest = 'manifest.csv', #We can hard-code this in this case because snakemake will ensure that it exists
        output_folder = args['output_folder']      
        )

if __name__ == "__main__":
    main()
    
    # run_cellpose(
    #     cp_image_pool_size=0,
    #     cp_batch_size=16,
    #     cp_min_size=100,
    #     cp_resample=False,
    #     analysis_params= '/Users/owenburroughs/Desktop/Personal_Skaar_Lab/EPS007_Code/Test_Output/AVI0G830_TestPlate/analysis_params.yaml',
    #     manifest = '/Users/owenburroughs/Desktop/Personal_Skaar_Lab/EPS007_Code/Test_Output/AVI0G830_TestPlate/manifest.csv',
    #     output_folder='/Users/owenburroughs/Desktop/Personal_Skaar_Lab/EPS007_Code/Test_Output/AVI0G830_TestPlate/cellpose_masks'        
    #     )
    