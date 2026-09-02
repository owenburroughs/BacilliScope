#In general, I hate object-orientated patterns like this, but I need to instantiate the model for all CellPose operations, so this is what I am stuck with
import skimage
import pandas as pd
from cellpose import models
from prefect import task


def segment_macrophages(image, diameter=None, resample=True, props=None):
    model = models.Cellpose(model_type='cyto3', gpu=True)
    
    #First, segment the macrophages using cellpose
    masks, flows, styles, diams = model.eval(image, diameter=diameter, channels=[0,0], resample=resample, min_size=100)
    
    #Set default properties to extract if none are provided
    if props is None:
        props = [
            'label',
            'area',
            'centroid',
            'eccentricity',
        ]

    #Now, extract properties using skimage and insert these into a dataframe
    cell_props_df = pd.DataFrame(skimage.measure.regionprops_table(masks, properties=props, separator='_'))
    
    #Clean up memory
    del model

    #returns the generated masks, and the dataframe of how the date were inserted    
    return masks, cell_props_df           
    