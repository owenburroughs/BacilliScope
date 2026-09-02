# A helper function to annotate a dataframe of sanger library wells with the corresponding genes
import pandas as pd

def annotate_well_genes(
    library_annotation_file: str,
    dataframe
):
    library_annotation_df = pd.read_csv(library_annotation_file)
    
    return dataframe.merge(library_annotation_df, how='left', on=['plate_number', 'well_row', 'well_column'])
