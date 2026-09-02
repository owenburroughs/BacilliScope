'''
This script ingests all of the data from a folder and prepares a snakemake pipeline for HTS screen analysis
I am using Gooey to create a GUI to make this process easier and more streamlined

Inputs:
    Str: Folder path containing the image files to ingest
    Str: Output folder path
    Str: Human-readable plate ID
    Date: Run Date
    int: Sanger library plate number
    list: uninfected control wells
    list: reporter control wells
    float: Sampling proportion for Otsu thresholds
    int: number of FOVs to sample cellpose radii from (can be 0)
    
Outputs:
    [output folder]: creates a new folder in the output directory that is named the succinct run ID
    manifest.csv: a csv file containing one FOV per line with the filepaths for the constitutive, burden, and reporter images.
        This will also mark the FOVs to be used for random sampling.
    config.yaml: a yaml file with the information required for the snakemake pipeline
    snakefile: a copy of the master snakefile in the output directory that is configured to process the run

'''
from gooey import GooeyParser
from gooey import Gooey
from typing import TypedDict
import datetime
import shutil
import yaml
import os
import pandas as pd
import string
import secrets

from utils.HTS_CollectImageFiles import HTS_CollectImageFiles 
from utils.parsers.ImageXpressNameParser import ImageXpressNameParser

#Define the folder parameters for type checking purposes
class FolderParams(TypedDict, total=True):
    input_folder: str
    output_folder: str
    sanger_plate: int
    plate_name: str
    acquisition_date: datetime.date
    otsu_sample: int
    cellpose_sample: int
    control_virus: list
    reporter_control: list
    uninfected: list
    
#Set variables for each of the channel indicies
#NOTE: this could be collected from the user at runtime instead of being hardcoded
channel_indicies= {
    1: "CellMask",
    2: "constitutive",
    3: "reporter"
}

##This is the main function that is called when the script is run as a standalone item. This passes arguments to the processing function ingest_folder()
@Gooey
def main() -> None:
    #Initialize the parser
    #Note: I am using GooeyParser, which is a drop-in replacement for argparse. This code can be modified to work with vanilla argparse by removing the "widget" keywords from arguments.
    parser = GooeyParser(
        description='Configure options for an HTS Bacilliscope run.'
    )
    
    #Add arguments
    parser.add_argument('--input_folder', '-i', help="The parent folder for raw HTS images", widget='DirChooser')
    parser.add_argument('--output_folder', '-o', help="Parent folder to store analysis output", widget='DirChooser')
    parser.add_argument('--sanger_plate', '-p', help="Int: Plate ID in the Sanger library", widget='IntegerField', type=int)
    parser.add_argument('--plate_name',  '-n', help="Str: The human-readable name for the plate", type=str)
    parser.add_argument('--acquisition_date', '-d', help="The date the plate was acquired on (ISO 8601)", default="1970-01-01", widget='DateChooser')
    parser.add_argument('--control_virus', '-s', help="Wells containing WT bug and control virus, separated by commas. E.g., 'O17,O18,O19'", default="O17,O18,O19")
    parser.add_argument('--reporter_control', '-r', help="Wells containing the reporter control and control virus, separated by commas. E.g., 'O20,O21,O22'", default="O21,O21,O22")
    parser.add_argument('--uninfected', '-u', help="Uninfected wells containing control virus, separated by commas. E.g., 'O23,O24", default='O23,O24')
    parser.add_argument('--otsu_sample', '-t', help="The number of FOVs to sample for Otsu thresholds", default='10', widget='IntegerField', gooey_options={'min': 0, 'max': 1000}, type=int)
    parser.add_argument('--cellpose_sample', '-c', help="The number of FOVs to sample for Cellpose parameters", default='5', widget='IntegerField', gooey_options={'min': 0, 'max': 1000}, type=int)

    args = vars(parser.parse_args())
    
    #Parse the well list arguments into dictionaries
    args['control_virus'] = parse_well_list(args['control_virus'])
    args['reporter_control'] = parse_well_list(args['reporter_control'])
    args['uninfected'] = parse_well_list(args['uninfected'])
    
    #Parse the date into a datetime type
    args['acquisition_date'] = datetime.date.fromisoformat(args['acquisition_date'])
    
    #parse integer values

    ingest_folder(args)

#Function to take a list of wells as a comma-separated string and return a validated list
def parse_well_list(wells: str) -> list:
    well_strings = wells.replace(" ", "").split(",")
    well_tuples = []
    
    for string in well_strings:
        row = string[0]
        column = int(string[1:])
        well_tuples.append((row,column))
        
    return well_tuples

#Function to create a random ID for a plate of length N. Cyptographically secure but not by necessity
def create_random_id(length: int) -> str:
    #return 'AVI0G830'
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(length))

    
#Function to take the parameters for a plate and create the necessary files for a snakemake run
#In headless mode, this function can be run directly without calling main()
def ingest_folder(params: FolderParams):
    #Begin by scanning the input folder for the image files that we want
    image_files = HTS_CollectImageFiles(params['input_folder'], ImageXpressNameParser, doRecursiveFolderSearch=True, filetypeMatchRegex=".*\\.TIF$")
    
    images_df = pd.DataFrame(image_files)
    
    #create a new unique identifier for this run
    run_id = create_random_id(8)
    
    #create a new column that contains a single identifier for each FOV, including the run ID
    images_df['FOV_id'] = run_id + '_' + images_df['well_row'] + "_" + images_df['well_column'].astype(str) + "_" + images_df['well_site'].astype(str)
    
    #For all unique sites, extract the pathnames for each channel
    unique_sites = (images_df.groupby('FOV_id')
                    .first()
                    .reset_index()
                    .drop(labels=['channel','path'], axis=1)
                    .merge(
                        images_df.assign(channel=images_df['channel'].map(channel_indicies))
                        .pivot_table(index='FOV_id', columns='channel', values='path', aggfunc='first')
                        .reset_index(),
                        on='FOV_id',
                        how='left'
                        )
                    )
    
    #subsample FOVs for otsu thresholding
    unique_sites['otsu_sample'] = unique_sites['FOV_id'].isin(unique_sites["FOV_id"].sample(n=params['otsu_sample']))
    
    #subsample FOVs for cellpose parameter calculation
    unique_sites['cellpose_sample'] = unique_sites['FOV_id'].isin(unique_sites["FOV_id"].sample(n=params['cellpose_sample']))
    
    #create new columns for the duckdb FOVs database
    unique_sites['well_type'] = 'gene_target'
    unique_sites['plate_id'] = run_id
    unique_sites['plate_name'] = params['plate_name']
    unique_sites['plate_number'] = params['sanger_plate']
    unique_sites['acquisition_date'] = params['acquisition_date']
    
    #add control virus wells
    for well_row, well_column in params['control_virus']:
        mask = (
            (unique_sites['well_row'] == well_row) &
            (unique_sites['well_column'] == well_column)
        )
        unique_sites.loc[mask, 'well_type'] = 'control_virus'
        
    #add reporter control wells
    for well_row, well_column in params['reporter_control']:
        mask = (
            (unique_sites['well_row'] == well_row) &
            (unique_sites['well_column'] == well_column)
        )
        unique_sites.loc[mask, 'well_type'] = 'reporter_control'
    
    #add uninfected wells
    for well_row, well_column in params['uninfected']:
        mask = (
            (unique_sites['well_row'] == well_row) &
            (unique_sites['well_column'] == well_column)
        )
        unique_sites.loc[mask, 'well_type'] = 'uninfected'
        
    #####Create outputs######
    #First, create output folders#
    output_folder = f'{params["output_folder"]}/{run_id}_{params['plate_name'].replace(" ","")}'
    if not os.path.exists(output_folder): #Main output folder
        os.makedirs(output_folder)
    
    if not os.path.exists(f'{output_folder}/cellpose_masks'): #Subfolder for cellpose masks
        os.makedirs(f'{output_folder}/cellpose_masks')
        
    if not os.path.exists(f'{output_folder}/merged_FOVs'): #Subfolder for merged FOVs 
        os.makedirs(f'{output_folder}/merged_FOVs')
        
    if not os.path.exists(f'{output_folder}/parquet'): #Subfolder for parquets 
        os.makedirs(f'{output_folder}/parquet')
        
    #manifest.csv#
    unique_sites.to_csv(f'{output_folder}/manifest.csv', index=False)
    
    #snakefile#
    with open(f'{os.path.dirname(__file__)}/snakefile.template') as f: snakefile = f.read() #Get the contents of the snakefile template
    
    with open(f'{output_folder}/snakefile', 'w') as f:
        f.write(f'configfile: \"{output_folder}/config.yaml\"\n') #Add the location of our config.yaml to the first line
        f.write(snakefile) #Add the contents of the template snakefile
    
    #config.yaml#
        snakemake_config = {
            'scripts_path': os.path.dirname(__file__),
            'output_folder': output_folder,
            'run_id': run_id,
            'cp_resample': False,
            'cp_batch_size': 64,
            'cp_min_size': 100,
            'cp_image_pool_size': 16
        }
        
    with open(f'{output_folder}/config.yaml', 'w') as f:
        f.write(yaml.dump(snakemake_config))
    
    return
    
    
test_params = {'input_folder': '/Users/owenburroughs/Desktop/Personal_Skaar_Lab/EPS007_Code/Test_Dataset', 
               'output_folder': '/Users/owenburroughs/Desktop/Personal_Skaar_Lab/EPS007_Code/Test_Output', 
               'sanger_plate': '3', 
               'plate_name': 'TestPlate', 
               'acquisition_date': datetime.date(1970, 1, 1),
               'otsu_sample': 10,
               'cellpose_sample': 1, 
               'control_virus': parse_well_list('A1, O18, O19'), 
               'reporter_control': parse_well_list('A2, O21, O22'), 
               'uninfected': parse_well_list('A3, O24')
}    

    
if __name__ == "__main__":
    main()
    #ingest_folder(test_params)