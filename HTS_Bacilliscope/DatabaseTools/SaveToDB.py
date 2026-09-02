import pandas as pd
from prefect import task

#IMPORT BATCH of ROIS TO DATABASE
def import_rois_to_db(con, SQL_handler, roi_df):
    """
    Inserts a batch of ROIs into the DuckDB database and returns the inserted data as a dataframe.
    Args:
        con: DuckDB connection object or cursor
        SQL_handler: function to execute SQL queries taking a connection/cursor and a query string as input
        roi_list: list of dictionaries, each containing 'plate_name', 'plate_number', 'well_row', 'well_column', acquisition_date, update_timestamp (optional)
    """
    
    update_timestamp = pd.Timestamp.now()

    #Insert the dataframe into the DuckDB database
    SQL_handler(con, f"""         
        INSERT INTO ROIs 
            (
            plate_name, 
            plate_number, 
            well_row, 
            well_column,
            well_site,
            update_timestamp
            )
        SELECT 
            plate_name,
            plate_number,
            well_row,
            well_column,
            well_site,
            '{update_timestamp}'
        FROM 
            dataframe
    """
    , dataframe=roi_df)

    #Extract the inserted data for correct label assignment
    database_df = SQL_handler(con, f"""
        SELECT * FROM ROIs WHERE update_timestamp = '{update_timestamp}';
    """).df()
    
    return database_df

#SAVE CELL MEASUREMENTS TO DATABASE
def save_cells_to_db(con, SQL_handler, roi_id, cell_props_df):
    """
    Inserts cell properties into the DuckDB database and returns the inserted data as a dataframe.
    Args:
        con: DuckDB connection object or cursor
        SQL_handler: function to execute SQL queries taking a connection/cursor and a query string as input
        roi_id: integer well identifier
        cell_props_df: pandas dataframe of cell properties to insert into the database
    """

    #Insert the dataframe into the DuckDB database
    SQL_handler(con, f"""         
        INSERT INTO cells 
            (roi_id, area, centroid_0, centroid_1, eccentricity, label)
        SELECT 
        {roi_id}::INTEGER,
        area, 
        centroid_0, 
        centroid_1, 
        eccentricity, 
        label 
    FROM 
        dataframe
    """
    , dataframe=cell_props_df)

    #Extract the inserted data for correct label assignment
    database_df = SQL_handler(con, f"""
        SELECT * FROM cells WHERE roi_id = {roi_id}::INTEGER;
    """).df()
    
    return database_df


#SAVE BACTERIAL MEASUREMENTS TO DATABASE
def save_bacteria_to_db(con, SQL_handler, roi_id, bacteria_props_df):
    """
    Inserts bacterial properties into the DuckDB database and returns the inserted data as a dataframe.
    Args:
        con: DuckDB connection object or cursor
        SQL_handler: function to execute SQL queries taking a connection/cursor and a query string as input
        roi_id: integer well identifier
        bacteria_props_df: pandas dataframe of bacterial properties to insert into the database
        
        """

    #Insert the dataframe into the DuckDB database
    SQL_handler(con, f"""         
        INSERT INTO bacteria (
            roi_id, 
            label, 
            area, 
            centroid_0, 
            centroid_1, 
            eccentricity, 
            intensity_mean_0, 
            intensity_mean_1, 
            intensity_max_0, 
            intensity_max_1, 
            intensity_min_0, 
            intensity_min_1, 
            intensity_std_0, 
            intensity_std_1, 
            length
            )
        SELECT 
            {roi_id}::INTEGER,
            label,
            area,
            centroid_0,
            centroid_1,
            eccentricity,
            intensity_mean_0,
            intensity_mean_1,
            intensity_max_0,
            intensity_max_1,
            intensity_min_0,
            intensity_min_1,
            intensity_std_0,
            intensity_std_1,
            length
        FROM 
            dataframe
    """
    , dataframe=bacteria_props_df)

    #Extract the inserted data for correct label assignment
    database_df = SQL_handler(con, f"""
        SELECT * FROM bacteria WHERE roi_id = {roi_id}::INTEGER;
    """).df()
    
    return database_df


#SAVE OVERLAP MEASUREMENTS TO DATABASE
def save_overlaps_to_db(con, SQL_handler, roi_id, overlap_props_df):
    """
    Inserts bacterial properties into the DuckDB database and returns the inserted data as a dataframe.
    Args:
        con: DuckDB connection object or cursor
        SQL_handler: function to execute SQL queries taking a connection/cursor and a query string as input
        roi_id: integer well identifier
        overlap_props_df: pandas dataframe of bacterial properties to insert into the database
        
        """

    #Insert the dataframe into the DuckDB database
    SQL_handler(con, f"""         
        INSERT INTO cell_bac_overlaps (
            roi_id,
            cell_id,
            bacteria_id, 
            label, 
            area, 
            centroid_0, 
            centroid_1, 
            eccentricity, 
            intensity_mean_0, 
            intensity_mean_1, 
            intensity_max_0, 
            intensity_max_1, 
            intensity_min_0, 
            intensity_min_1, 
            intensity_std_0, 
            intensity_std_1, 
            length
            )
        SELECT 
            {roi_id}::INTEGER,
            cell_id,
            bacteria_id,
            label,
            area,
            centroid_0,
            centroid_1,
            eccentricity,
            intensity_mean_0,
            intensity_mean_1,
            intensity_max_0,
            intensity_max_1,
            intensity_min_0,
            intensity_min_1,
            intensity_std_0,
            intensity_std_1,
            length
        FROM 
            dataframe
    """
    , dataframe=overlap_props_df)
    
    return