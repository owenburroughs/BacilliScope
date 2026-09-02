"""
    Function to process an entire FOV from a cellmask image, and raw inputs
"""
import argparse
import pandas as pd
import numpy as np
from PIL import Image
import yaml

from skimage.morphology import binary_opening
from skimage.measure import label, regionprops_table
from skimage.morphology import disk

from tifffile import imwrite

from utils.ImageProcessing.BacteriaAnalysis import subtract_background_median, measure_bacterial_signal, segment_bacteria, calculate_overlaps

#Properties that we want to keep for cellpose masks
cellpose_props = [
            'label',
            'area',
            'centroid',
            'eccentricity',
        ]

#Function for the processing steps
def process_fov(
    cellpose_image_path: str,
    CellMask_image_path: str,
    constitutive_image_path: str,
    reporter_image_path: str,
    image_output_dir: str,
    parquet_output_dir: str,
    analysis_params_path: str,
    row: str,
    col: int,
    site: int,
    plate_id: str
):
    #Get analysis parameters
    with open(analysis_params_path) as f:
        analysis_params_dict = yaml.load(f, Loader=yaml.CLoader)
    
    #Import images
    cellpose_image_PIL = Image.open(cellpose_image_path)
    cellpose_image = np.array(cellpose_image_PIL)
    CellMask_image_PIL = Image.open(CellMask_image_path)
    CellMask_image = np.array(CellMask_image_PIL)
    constitutive_image_PIL = Image.open(constitutive_image_path)
    constitutive_image = np.array(constitutive_image_PIL)   
    reporter_image = np.array(Image.open(reporter_image_path))
    
    #Process cellpose image
    cellpose_props_df = pd.DataFrame(regionprops_table(cellpose_image, properties=cellpose_props, separator='_'))
    
    #Segment bacteria using constitutive channel
    constitutive_labels = segment_bacteria(bacteria_image= constitutive_image, threshold= analysis_params_dict['constitutive_otsu_median'])
    
    #Filter reporter image based on segmentations
    filtered_reporter_image = subtract_background_median(reporter_image, constitutive_labels)
    filtered_reporter_image = np.round(filtered_reporter_image).astype(np.uint16)
    
    #Stack the constitutive and reporter images for intensity value measurments
    intensity_image_stack = np.stack([constitutive_image, filtered_reporter_image], axis=-1)
    
    #Measure bacterial properties
    constitutive_props_df = measure_bacterial_signal(constitutive_labels, intensity_image_stack)
    
    #Measuring overlap signal
    constitutive_overlaps, const_overlap_labels_df = calculate_overlaps(constitutive_labels, cellpose_image)
    const_overlap_labels_df.columns=['label', 'cell_id', 'constitutive_id']
    const_overlap_measurements = measure_bacterial_signal(constitutive_overlaps, intensity_image_stack)
    labeled_const_overlap_props_df = const_overlap_measurements.merge(const_overlap_labels_df, how='right', on='label')
    
    #generate reporter image objects
    masked_reporter = filtered_reporter_image * (constitutive_labels > 0)
    reporter_labels = segment_bacteria(bacteria_image= masked_reporter, threshold= analysis_params_dict['reporter_otsu_median'])
    reporter_props_df = measure_bacterial_signal(reporter_labels, intensity_image_stack)
    
    #generate overlaps between the masked reporter and the cell/bac overlap objects
    reporter_overlaps, reporter_overlap_labels = calculate_overlaps(reporter_labels, constitutive_overlaps)
    reporter_overlap_labels.columns=['label', 'reporter_id', 'const_overlap_id']
    reporter_overlap_measurments = measure_bacterial_signal(reporter_overlaps, intensity_image_stack)
    labeled_rep_overlap_props_df = reporter_overlap_measurments.merge(reporter_overlap_labels, how='right', on='label')
    
    #save images into a merged FOV tiff
    FOV_id = f'{plate_id}_{row}_{col}_{site}'
    file_name = f'{image_output_dir}/{FOV_id}_merged.tif'
    image_files = [CellMask_image, constitutive_image, filtered_reporter_image, cellpose_image, constitutive_labels, reporter_labels, constitutive_overlaps, reporter_overlaps]
    stack = np.stack([np.asarray(arr).astype(np.uint16) for arr in image_files], axis=0)

    imwrite(
        file_name,
        stack,
        imagej=True,
        compression='deflate'
    )
    
    #Save dataframes into csv and parquet files
    cellpose_props_df = cellpose_props_df.assign(plate_id = plate_id, well_row = row, well_column = col, well_site = site)
    cellpose_props_df.rename(columns = {"label" : "cell_id"}, inplace=True)
    cellpose_props_df.to_parquet(f'{parquet_output_dir}/{FOV_id}_cellpose.parquet')
    
    constitutive_props_df = constitutive_props_df.assign(plate_id = plate_id, well_row = row, well_column = col, well_site = site)
    constitutive_props_df.rename(columns = {"label" : "constitutive_id"}, inplace=True)
    constitutive_props_df.to_parquet(f'{parquet_output_dir}/{FOV_id}_constitutive.parquet')
    
    reporter_props_df = reporter_props_df.assign(plate_id = plate_id, well_row = row, well_column = col, well_site = site)
    reporter_props_df.rename(columns = {"label" : "reporter_id"}, inplace= True)
    reporter_props_df.to_parquet(f'{parquet_output_dir}/{FOV_id}_reporter.parquet')
    
    labeled_const_overlap_props_df = labeled_const_overlap_props_df.assign(plate_id = plate_id, well_row = row, well_column = col, well_site = site)
    labeled_const_overlap_props_df.rename(columns = {"label" : "const_overlap_id"}, inplace=True)
    labeled_const_overlap_props_df.to_parquet(f'{parquet_output_dir}/{FOV_id}_constOverlap.parquet')
    
    labeled_rep_overlap_props_df = labeled_rep_overlap_props_df.assign(plate_id = plate_id, well_row = row, well_column = col, well_site = site)
    labeled_rep_overlap_props_df.rename(columns={"label" : "rep_overlap_id"}, inplace=True)
    labeled_rep_overlap_props_df.to_parquet(f'{parquet_output_dir}/{FOV_id}_repOverlap.parquet')
    

def main():
    #First, load relevant parameters from argv
    parser = argparse.ArgumentParser()
    parser.add_argument('--cellpose_image', help="Path to cellpose labels image", type=str)
    parser.add_argument('--CellMask_image', help="Path to raw CellMask image", type=str)
    parser.add_argument('--constitutive_image', help="Path to constitutive image", type=str)
    parser.add_argument('--reporter_image', help="Path to reporter image", type=str)
    parser.add_argument('--image_output_dir', help="Path to image output directory", type=str)
    parser.add_argument('--parquet_output_dir', help="Path to image output directory", type=str)
    parser.add_argument('--analysis_params', help="Path to reporter image", type=str)
    parser.add_argument('--row', help="Row on plate of FOV", type=str)
    parser.add_argument('--col', help="Column on plate of FOV", type=int)
    parser.add_argument('--site', help="Site in well of FOV", type=int)
    parser.add_argument('--plate_id', help="ID of plate", type=str)
    args = vars(parser.parse_args())
    
    process_fov(
        cellpose_image_path= args['cellpose_image'],
        CellMask_image_path= args['CellMask_image'],
        constitutive_image_path= args['constitutive_image'],
        reporter_image_path= args['reporter_image'],
        image_output_dir= args['image_output_dir'],
        parquet_output_dir= args['parquet_output_dir'],
        analysis_params_path= args['analysis_params'],
        row= args['row'],
        col= args['col'],
        site= args['site'],
        plate_id= args['plate_id']
    )

if __name__ == "__main__":
    main()
    # process_fov(
    #     cellpose_image_path= '/Users/owenburroughs/Desktop/Personal_Skaar_Lab/EPS007_Code/Test_Output/AVI0G830_TestPlate/cellpose_masks/AVI0G830_A_6_2_cellpose.tif',
    #     CellMask_image_path= '/Users/owenburroughs/Desktop/Personal_Skaar_Lab/EPS007_Code/Test_Dataset/t1_A06_s2_w1_z1.tif',
    #     constitutive_image_path= '/Users/owenburroughs/Desktop/Personal_Skaar_Lab/EPS007_Code/Test_Dataset/t1_A06_s2_w2_z1.tif',
    #     reporter_image_path= '/Users/owenburroughs/Desktop/Personal_Skaar_Lab/EPS007_Code/Test_Dataset/t1_A06_s2_w3_z1.tif',
    #     image_output_dir= '/Users/owenburroughs/Desktop/Personal_Skaar_Lab/EPS007_Code/Test_Output/AVI0G830_TestPlate/merged_FOVs',
    #     parquet_output_dir= '/Users/owenburroughs/Desktop/Personal_Skaar_Lab/EPS007_Code/Test_Output/AVI0G830_TestPlate/parquet',
    #     analysis_params_path= '/Users/owenburroughs/Desktop/Personal_Skaar_Lab/EPS007_Code/Test_Output/AVI0G830_TestPlate/analysis_params.yaml',
    #     row= 'A',
    #     col= 6,
    #     site= 2,
    #     plate_id= 'AVI0G830'
    # )
