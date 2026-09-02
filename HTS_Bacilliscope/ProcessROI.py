#import internal libraries
from DatabaseTools.SimpleSQLQueryHander import execute_SQL_query
from DatabaseTools.SaveToDB import save_overlaps_to_db, save_bacteria_to_db, save_cells_to_db, import_rois_to_db
from FileHandlingUtils.HTS_CollectImageFiles import HTS_CollectImageFiles
from FileHandlingUtils.ImageXpressNameParser import ImageXpressNameParser
from ImageAnalysis.MacophageAnalysis import segment_macrophages
from ImageAnalysis.BacteriaAnalysis import segment_bacterial_constitutive, calculate_overlaps, measure_bacterial_signal, subtract_background_median

#import external libraries
import duckdb
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from tifffile import imwrite
from tqdm import tqdm
from prefect import task
from prefect.futures import wait
from prefect.task_runners import ThreadPoolTaskRunner


#PROCESS EACH ROI
def process_ROI(cellmask_image, constitutive_image, reporter_image, roi_id, db_connection, save_images=False):
    #First, create a cursor to allow for safe database transactions
    con = duckdb.connect(db_connection, read_only=False)
       
    #Segment macrophages
    cell_masks, cell_props_df = segment_macrophages(cellmask_image, diameter=45, resample=False)
    
    #Save cell measurements to database
    cell_labels_db = save_cells_to_db(con, execute_SQL_query, roi_id, cell_props_df)
    
    #Segment bacteria using constitutive channel
    constitutive_labels = segment_bacterial_constitutive(constitutive_image, threshold=4000)
    filtered_reporter_image = subtract_background_median(reporter_image, constitutive_labels)
    
    intensity_image_stack = np.stack([constitutive_image, filtered_reporter_image], axis=-1)
    
    #Measure bacterial properties
    bacteria_props_df = measure_bacterial_signal(constitutive_labels, intensity_image_stack)
    
    #Save bacterial measurements to database
    bacteria_labels_db = save_bacteria_to_db(con, execute_SQL_query, roi_id, bacteria_props_df)
    
    #Measuring overlap signal
    bac_cell_overlaps, overlap_labels = calculate_overlaps(constitutive_labels, cell_masks)

    #change overlap labels to be descriptive
    overlap_labels.columns=['label', 'cell_label', 'bacteria_label']

    #measure overlaps
    overlap_measurements = measure_bacterial_signal(bac_cell_overlaps, intensity_image_stack)

    #merge the overlap labels
    labeled_overlap_measurements = overlap_measurements.merge(overlap_labels, how='right', on='label')
    
    #Add cell IDs to the overlap measurements
    labeled_overlap_measurements = labeled_overlap_measurements.merge(
        cell_labels_db[["label", "cell_id"]],
        left_on='cell_label',
        right_on='label',
    )
    
    #Add bacteria IDs to the overlap measurements
    labeled_overlap_measurements = labeled_overlap_measurements.merge(
        bacteria_labels_db[["label", "bacteria_id"]],
        left_on='bacteria_label',
        right_on='label',
    )

        
    #Save overlap measurements to database
    save_overlaps_to_db(con, execute_SQL_query, roi_id, labeled_overlap_measurements)
    
    con.close()
    
    if save_images:
        #Optionally, save output images for verification
        return np.stack([cellmask_image, constitutive_image, filtered_reporter_image, cell_masks.astype(np.uint16), constitutive_labels.astype(np.uint16)], axis=0)
    else:
        return None