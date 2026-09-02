from pathlib import Path

#A function to parse ImageXpress filenames and return the relevant metadata
def ImageXpressNameParser(filename):
    # Example filename: "EPS007_IncartaFormat/t1_F14_s2_w3_z1.tif"
    file_path = Path(filename)
    base = file_path.stem  # e.g., "t1_F14_s2_w3_z1"
    parts = base.split('_')
        
    return {
        'well_row': parts[1][0] ,
        'well_column': int(parts[1][1:]),
        'well_site': int(parts[2][1:]),
        'channel': int(parts[3][1:]),
        'path' : filename
    }