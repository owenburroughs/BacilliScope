#Import requirements
import os
import duckdb

def InitializeValuesDatabaseV110(
        db_path: str, 
        remove_existing: bool = True,
        db_name: str = None,
        create_ART_indexes: bool = False
        ) -> None:

    '''
        Initializes the valuesdatabase schema for Bacilliscope using schema version 1.1.0.
        The values database is designed to store quantitative measurements extracted from images, as opposed to databases that store raw images or metadata about the plates.
        
        NOTE: Schema version 1.1.0 is NOT stable. It is subject to change as new features are added.
        Internal compatibility is NOT guaranteed between versions. Use at your own risk.
        
        Parameters:
            db_path (str): Path to the DuckDB database file.
            remove_existing (bool): If True, removes existing database file before initialization.
            db_name (str): Optional name for the database. If None, uses the file name.
            
        Returns:
            None
    '''

    #remove the database file if requested by the user
    if remove_existing:
        print("Removing existing")
        if os.path.exists(db_path):
            os.remove(db_path)
        if os.path.exists(db_path + ".wal"):
            os.remove(db_path + ".wal")
            
    #if a database name is not provided, use the file name as default
    if db_name is None:
        db_name = os.path.basename(db_path)

    # Ensure directory exists
    directory = os.path.dirname(db_path)
    if directory and not os.path.exists(directory):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
    #connect to the database
    con = duckdb.connect(db_path, read_only=False)
    
    
    try:    
    # ---- METADATA TABLE ----
        '''
            The metadata table MUST contain a 'schema_version' key to indicate the version of the schema used.
            Additional metadata can be added as needed. Which metadata is required is based on the schema version
        '''
        
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS __meta__ (
            key TEXT PRIMARY KEY,
            value JSON
        );
        """)
        
        con.execute(f"""
        INSERT INTO __meta__ (key, value) VALUES
            ('schema_version', '"1_0_0"'),
            ('database_name', '"{db_name}"'),
            ('created_at', current_timestamp)
        """)
        

    # ---- FOVs TABLE ----
        con.execute("""
        CREATE TABLE IF NOT EXISTS FOVs (
            plate_id    CHAR(8), --the auto-generated, 8-character plate ID
            well_row    CHAR(1), --row of the well (single capital letter)
            well_column INTEGER, --column of the well (single integer)
            well_site   INTEGER, --site of the FOV within the well (single integer)
            
            PRIMARY KEY (plate_id, well_row, well_column, well_site),
            
            plate_name  VARCHAR, --the human-readable name of the plate
            acquisition_date    TIMESTAMP, --the date that the images were acquired
            plate_number    INTEGER, --corresponds to the number of the physical plate in the library, used for gene lookup
            
            well_type   VARCHAR DEFAULT 'gene_target', --defaults to "gene_target" but can be set to a control type
            marker_symbol   VARCHAR, --the marker symbol for the gene target of the well guide
            mgi_gene_id VARCHAR, --the mgi gene id for the gene target of the well guide
            entrez_id   VARCHAR, --entrez id of the gene target for the well guide
            gene_product    VARCHAR, --the gene product of the gene target for the well guide            
        );
        """)

    # ---- CELLS TABLE ----
        con.execute("""
        CREATE TABLE IF NOT EXISTS cells (
            plate_id    CHAR(8), --the auto-generated, 8-character plate ID
            well_row    CHAR(1), --row of the well (single capital letter)
            well_column INTEGER, --column of the well (single integer)
            well_site   INTEGER, --site of the FOV within the well (single integer)
            cell_id BIGINT, --the local cell id that is assigned by skimage
            
            PRIMARY KEY (plate_id, well_row, well_column, well_site, cell_id),
            
            FOREIGN KEY (plate_id, well_row, well_column, well_site)
                REFERENCES FOVs(plate_id, well_row, well_column, well_site),
            
            area        DOUBLE, --from skimage
            centroid_0  DOUBLE, --from skimage, X value of centroid
            centroid_1  DOUBLE, --from skimage, Y value of centroid
            eccentricity    DOUBLE, --from skimage
        );
        """)

    # ---- CONSTITUTIVE TABLE----
        con.execute("""
        CREATE TABLE IF NOT EXISTS constitutive (
            plate_id    CHAR(8), --the auto-generated, 8-character plate ID
            well_row    CHAR(1), --row of the well (single capital letter)
            well_column INTEGER, --column of the well (single integer)
            well_site   INTEGER, --site of the FOV within the well (single integer)
            constitutive_id BIGINT, --the local cell id that is assigned by skimage
            
            PRIMARY KEY (plate_id, well_row, well_column, well_site, constitutive_id),
            
            FOREIGN KEY (plate_id, well_row, well_column, well_site)
                REFERENCES FOVs(plate_id, well_row, well_column, well_site),
            
            area  DOUBLE, -- area of the segnemted region
            centroid_0 DOUBLE, -- X coordinate of centroid
            centroid_1  DOUBLE, -- Y coordinate of centroid
            eccentricity DOUBLE, -- eccentricity of the segmented region
            intensity_mean_0 DOUBLE, -- mean intensity in the segmented region for constitutive channel
            intensity_mean_1 DOUBLE, -- mean intensity in the segmented region for reporter channel
            intensity_max_0  DOUBLE, -- max in the constitutive channel
            intensity_max_1 DOUBLE, -- max in the reporter channel
            intensity_min_0 DOUBLE, -- min in the constitutive channel
            intensity_min_1 DOUBLE, -- min in the reporter channel
            intensity_std_0 DOUBLE, -- std dev in the constitutive channel
            intensity_std_1 DOUBLE, -- std dev in the reporter channel
            length DOUBLE -- this is actually an integer now, but keeping as double for forwards compatibility
        );
        """)
        
    # ---- REPORTER TABLE----
        con.execute("""
        CREATE TABLE IF NOT EXISTS reporter (
            plate_id    CHAR(8), --the auto-generated, 8-character plate ID
            well_row    CHAR(1), --row of the well (single capital letter)
            well_column INTEGER, --column of the well (single integer)
            well_site   INTEGER, --site of the FOV within the well (single integer)
            reporter_id BIGINT, --the local cell id that is assigned by skimage
            
            PRIMARY KEY (plate_id, well_row, well_column, well_site, reporter_id),
            
            FOREIGN KEY (plate_id, well_row, well_column, well_site)
                REFERENCES FOVs(plate_id, well_row, well_column, well_site),
            
            area  DOUBLE, -- area of the segnemted region
            centroid_0 DOUBLE, -- X coordinate of centroid
            centroid_1  DOUBLE, -- Y coordinate of centroid
            eccentricity DOUBLE, -- eccentricity of the segmented region
            intensity_mean_0 DOUBLE, -- mean intensity in the segmented region for constitutive channel
            intensity_mean_1 DOUBLE, -- mean intensity in the segmented region for reporter channel
            intensity_max_0  DOUBLE, -- max in the constitutive channel
            intensity_max_1 DOUBLE, -- max in the reporter channel
            intensity_min_0 DOUBLE, -- min in the constitutive channel
            intensity_min_1 DOUBLE, -- min in the reporter channel
            intensity_std_0 DOUBLE, -- std dev in the constitutive channel
            intensity_std_1 DOUBLE, -- std dev in the reporter channel
            length DOUBLE -- this is actually an integer now, but keeping as double for forwards compatibility
        );
        """)

    # ---- CONSTITUTIVE OVERLAPS TABLE----
        con.execute("""
        CREATE TABLE IF NOT EXISTS cell_bac_overlaps (
            plate_id    CHAR(8), --the auto-generated, 8-character plate ID
            well_row    CHAR(1), --row of the well (single capital letter)
            well_column INTEGER, --column of the well (single integer)
            well_site   INTEGER, --site of the FOV within the well (single integer)
            const_overlap_id BIGINT, --the local cell id that is assigned by skimage
            cell_id BIGINT, --id of the parental cell for this overlap
            constitutive_id BIGINT, --id of the parental constitutive object for this overlap
            
            PRIMARY KEY (plate_id, well_row, well_column, well_site, const_overlap_id),
            
            FOREIGN KEY (plate_id, well_row, well_column, well_site, cell_id)
                REFERENCES cells (plate_id, well_row, well_column, well_site, cell_id),
            
            FOREIGN KEY (plate_id, well_row, well_column, well_site, constitutive_id)
                REFERENCES constitutive (plate_id, well_row, well_column, well_site, constitutive_id),
            
            area  DOUBLE, -- area of the segnemted region
            centroid_0 DOUBLE, -- X coordinate of centroid
            centroid_1  DOUBLE, -- Y coordinate of centroid
            eccentricity DOUBLE, -- eccentricity of the segmented region
            intensity_mean_0 DOUBLE, -- mean intensity in the segmented region for constitutive channel
            intensity_mean_1 DOUBLE, -- mean intensity in the segmented region for reporter channel
            intensity_max_0  DOUBLE, -- max in the constitutive channel
            intensity_max_1 DOUBLE, -- max in the reporter channel
            intensity_min_0 DOUBLE, -- min in the constitutive channel
            intensity_min_1 DOUBLE, -- min in the reporter channel
            intensity_std_0 DOUBLE, -- std dev in the constitutive channel
            intensity_std_1 DOUBLE, -- std dev in the reporter channel
            length DOUBLE -- this is actually an integer now, but keeping as double for forwards compatibility
        );
        """)
        # ---- REPORTER OVERLAPS TABLE----
        con.execute("""
        CREATE TABLE IF NOT EXISTS reporter_overlaps (
            plate_id    CHAR(8), --the auto-generated, 8-character plate ID
            well_row    CHAR(1), --row of the well (single capital letter)
            well_column INTEGER, --column of the well (single integer)
            well_site   INTEGER, --site of the FOV within the well (single integer)
            rep_overlap_id BIGINT, --the local cell id that is assigned by skimage
            reporter_id BIGINT, --id of the parental cell for this overlap
            const_overlap_id BIGINT, --id of the parental constitutive object for this overlap
            
            PRIMARY KEY (plate_id, well_row, well_column, well_site, rep_overlap_id),
            
            FOREIGN KEY (plate_id, well_row, well_column, well_site, reporter_id)
                REFERENCES reporter (plate_id, well_row, well_column, well_site, reporter_id),
            
            FOREIGN KEY (plate_id, well_row, well_column, well_site, const_overlap_id)
                REFERENCES cell_bac_overlaps (plate_id, well_row, well_column, well_site, const_overlap_id),
            
            area  DOUBLE, -- area of the segnemted region
            centroid_0 DOUBLE, -- X coordinate of centroid
            centroid_1  DOUBLE, -- Y coordinate of centroid
            eccentricity DOUBLE, -- eccentricity of the segmented region
            intensity_mean_0 DOUBLE, -- mean intensity in the segmented region for constitutive channel
            intensity_mean_1 DOUBLE, -- mean intensity in the segmented region for reporter channel
            intensity_max_0  DOUBLE, -- max in the constitutive channel
            intensity_max_1 DOUBLE, -- max in the reporter channel
            intensity_min_0 DOUBLE, -- min in the constitutive channel
            intensity_min_1 DOUBLE, -- min in the reporter channel
            intensity_std_0 DOUBLE, -- std dev in the constitutive channel
            intensity_std_1 DOUBLE, -- std dev in the reporter channel
            length DOUBLE -- this is actually an integer now, but keeping as double for forwards compatibility
        );
        """)

        # Commit all changes to ensure they're persisted
        con.commit()
        print("Schema initialized successfully.")
        
        print(con.execute("SHOW TABLES").fetchall())
        
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        raise
    finally:
        con.close()
        print("Database connection closed.")

    
