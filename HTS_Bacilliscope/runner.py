#import internal libraries
from DatabaseTools.SimpleSQLQueryHander import execute_SQL_query
from ProcessROI import process_ROI
from DatabaseTools.SaveToDB import save_overlaps_to_db, save_bacteria_to_db, save_cells_to_db, import_rois_to_db
from FileHandlingUtils.HTS_CollectImageFiles import HTS_CollectImageFiles
from FileHandlingUtils.ImageXpressNameParser import ImageXpressNameParser
from ImageAnalysis.BacteriaAnalysis import segment_bacterial_constitutive, calculate_overlaps, measure_bacterial_signal, subtract_background_median

#import external libraries
import duckdb
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from tifffile import imwrite
from tqdm import tqdm
from pqdm.threads import pqdm
import gc

#Open a connection to the database
Database_path = "Lenti_1_3_4_2.db"
con = duckdb.connect(Database_path, read_only=False)
print(con.execute("SHOW TABLES").fetchall())

###Main processing loop
#Take an input directory and collect all image files recursively
search_directory = "/Volumes/Owen_BrattonLab/EPS007/EPS007-2"
output_directory = "/Volumes/Owen_BrattonLab/Hit_2_masks/"
Images = pd.DataFrame(HTS_CollectImageFiles(directory=search_directory, FileNameParser=ImageXpressNameParser, filetypeMatchRegex=".*\\.TIF$", doRecursiveFolderSearch=True))
Images['well'] = Images['well_row'].astype(str) + Images['well_column'].astype(str)
save_images = False


#Identify unique ROIs based on the plate characteristics
ROIs = Images.groupby(['well', 'well_site', 'plate_name']).first().reset_index()

#Import ROIs to database, and get their assigned labels
ROI_labels = import_rois_to_db(con, execute_SQL_query, ROIs)
ROI_labels['well'] = ROI_labels['well_row'].astype(str) + ROI_labels['well_column'].astype(str)


#Collect images and feed them to the ROI processor
def FeedROI(roi):
    #We collect all of the images in the roi
    site_images = Images[(Images['well'] == roi['well']) & (Images['well_site'] == roi['well_site']) & (Images['plate_name'] == roi['plate_name'])]

    #Unless something is terribly wrong, there should be three of these
    assert(len(site_images) == 3)

    #Now, load the images
    cellmask_image = plt.imread(site_images[site_images['channel'] == 1]['path'].values[0])
    constitutive_image = plt.imread(site_images[site_images['channel'] == 2]['path'].values[0])
    reporter_image = plt.imread(site_images[site_images['channel'] == 3]['path'].values[0])
    
    #Now, look up the roi ID that was used in the database
    roi_id = ROI_labels[(ROI_labels['well'] == roi['well']) & (ROI_labels['well_site'] == roi['well_site']) & (ROI_labels['plate_name'] == roi['plate_name'])]['roi_id'].values[0]
    
    process_ROI(cellmask_image, constitutive_image, reporter_image, roi_id, save_images=save_images, db_connection=Database_path)
    
    del cellmask_image
    del constitutive_image
    del reporter_image
    
    gc.collect()
    

pqdm(ROIs.to_dict('records'), FeedROI, n_jobs=8)



#Close the database connection
con.close()
