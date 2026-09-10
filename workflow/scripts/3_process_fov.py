"""
    Function to process an entire FOV from a cellmask image, and raw inputs
"""
import argparse
import pandas as pd
import numpy as np
from PIL import Image
import json

from skimage.measure import regionprops_table
from tifffile import imwrite

from utils.BacteriaAnalysis import subtract_background_median, measure_bacterial_signal, segment_bacteria, calculate_overlaps

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from snakemake.iocontainers import snakemake

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
    analysis_params_path: str,
    
    merged_image_out: str,
    cellpose_parquet_out: str,
    constitutive_parquet_out: str,
    reporter_parquet_out: str,
    constOverlap_parquet_out: str,
    repOverlap_parquet_out: str,
    
    row: str,
    column: int,
    site: int,
    plate_id: str,
):
    #Get analysis parameters
    with open(analysis_params_path) as f:
        analysis_params_dict = json.load(f)
    
    #Import images
    cellpose_image = np.array(Image.open(cellpose_image_path))
    CellMask_image = np.array(Image.open(CellMask_image_path))
    constitutive_image = np.array(Image.open(constitutive_image_path))   
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
    image_files = [CellMask_image, constitutive_image, filtered_reporter_image, cellpose_image, constitutive_labels, reporter_labels, constitutive_overlaps, reporter_overlaps]
    stack = np.stack([np.asarray(arr).astype(np.uint16) for arr in image_files], axis=0)

    imwrite(
        merged_image_out,
        stack,
        imagej=True,
        compression='deflate'
    )
    
    #Save dataframes into csv and parquet files
    cellpose_props_df = cellpose_props_df.assign(plate_id = plate_id, well_row = row, well_column = column, well_site = site)
    cellpose_props_df.rename(columns = {"label" : "cell_id"}, inplace=True)
    cellpose_props_df.to_parquet(cellpose_parquet_out)
    
    constitutive_props_df = constitutive_props_df.assign(plate_id = plate_id, well_row = row, well_column = column, well_site = site)
    constitutive_props_df.rename(columns = {"label" : "constitutive_id"}, inplace=True)
    constitutive_props_df.to_parquet(constitutive_parquet_out)
    
    reporter_props_df = reporter_props_df.assign(plate_id = plate_id, well_row = row, well_column = column, well_site = site)
    reporter_props_df.rename(columns = {"label" : "reporter_id"}, inplace= True)
    reporter_props_df.to_parquet(reporter_parquet_out)
    
    labeled_const_overlap_props_df = labeled_const_overlap_props_df.assign(plate_id = plate_id, well_row = row, well_column = column, well_site = site)
    labeled_const_overlap_props_df.rename(columns = {"label" : "const_overlap_id"}, inplace=True)
    labeled_const_overlap_props_df.to_parquet(constOverlap_parquet_out)
    
    labeled_rep_overlap_props_df = labeled_rep_overlap_props_df.assign(plate_id = plate_id, well_row = row, well_column = column, well_site = site)
    labeled_rep_overlap_props_df.rename(columns={"label" : "rep_overlap_id"}, inplace=True)
    labeled_rep_overlap_props_df.to_parquet(repOverlap_parquet_out)
    
#-----------------------------------------------------------
# MAIN FUNCTION
#-----------------------------------------------------------   

if __name__ == "__main__":
    #We are running in the snakemake environment
    try:
        cellpose_image_path= snakemake.input['cellpose']
        CellMask_image_path= snakemake.input['cellmask']
        constitutive_image_path= snakemake.input['constitutive']
        reporter_image_path= snakemake.input['reporter']
        analysis_params_path= snakemake.input['analysis_params']
        
        merged_image_out= snakemake.output['merged_image']
        cellpose_parquet_out= snakemake.output['cellpose_parquet']
        constitutive_parquet_out= snakemake.output['constitutive_parquet']
        reporter_parquet_out= snakemake.output['reporter_parquet']
        constOverlap_parquet_out= snakemake.output['constOverlap_parquet']
        repOverlap_parquet_out = snakemake.output['repOverlap_parquet']
        
        FOV_id = snakemake.params['FOV_id']
        row= snakemake.params['row']
        column= snakemake.params['column']
        site= snakemake.params['site']
        plate_id= snakemake.params['plate_id']
    
    # We might be running from command line
    except NameError:
        parser = argparse.ArgumentParser()
        parser.add_argument('--cellpose_image', help="Path to cellpose labels image", type=str)
        parser.add_argument('--CellMask_image', help="Path to raw CellMask image", type=str)
        parser.add_argument('--constitutive_image', help="Path to constitutive image", type=str)
        parser.add_argument('--reporter_image', help="Path to reporter image", type=str)
        parser.add_argument('--image_output_dir', help="Path to image output directory", type=str)
        parser.add_argument('--parquet_output_dir', help="Path to image output directory", type=str)
        parser.add_argument('--analysis_params', help="Path to reporter image", type=str)
        parser.add_argument('--row', help="Row on plate of FOV", type=str)
        parser.add_argument('--column', help="Column on plate of FOV", type=int)
        parser.add_argument('--site', help="Site in well of FOV", type=int)
        parser.add_argument('--plate_id', help="ID of plate", type=str)
        args = vars(parser.parse_args())
        
        cellpose_image_path= args['cellpose_image']
        CellMask_image_path= args['CellMask_image']
        constitutive_image_path= args['constitutive_image']
        reporter_image_path= args['reporter_image']
        image_output_dir= args['image_output_dir']
        parquet_output_dir= args['parquet_output_dir']
        analysis_params_path= args['analysis_params']
        row= args['row']
        column= args['column']
        site= args['site']
        plate_id= args['plate_id']
        
        FOV_id = f'{plate_id}_{row}_{column}_{site}'
        
        merged_image_out= f'{image_output_dir}/{FOV_id}_merged.tif'
        cellpose_parquet_out= f'{parquet_output_dir}/{FOV_id}_cellpose.parquet'
        constitutive_parquet_out= f'{parquet_output_dir}/{FOV_id}_constitutive.parquet'
        reporter_parquet_out= f'{parquet_output_dir}/{FOV_id}_reporter.parquet'
        constOverlap_parquet_out= f'{parquet_output_dir}/{FOV_id}_constOverlap.parquet'
        repOverlap_parquet_out= f'{parquet_output_dir}/{FOV_id}_repOverlap.parquet'

    # Now, call the process_fov function    
    process_fov(
        cellpose_image_path= cellpose_image_path,
        CellMask_image_path= CellMask_image_path,
        constitutive_image_path= constitutive_image_path,
        reporter_image_path= reporter_image_path,
        analysis_params_path= analysis_params_path,
        
        merged_image_out= merged_image_out,
        cellpose_parquet_out= cellpose_parquet_out,
        constitutive_parquet_out=  constitutive_parquet_out,
        reporter_parquet_out= reporter_parquet_out,
        constOverlap_parquet_out= constOverlap_parquet_out,
        repOverlap_parquet_out= repOverlap_parquet_out,
        
        row= row,
        column= column,
        site= site,
        plate_id= plate_id,
    )
