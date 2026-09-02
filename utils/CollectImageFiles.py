import os, re
from typing import Optional, Dict
from collections.abc import Callable

def CollectImageFiles(
    directory: str, #The directory we are searching for image files in
    FileNameParser: Callable[[str],dict], #The function that takes a given filename and returns the required pieces of information as K:V pairs
    doRecursiveFolderSearch: bool=False, #Whether to search all child directories in the passed directory
    filetypeMatchRegex: Optional[str]=None, #A regular expression that files must satisfy to be included. "String"
) -> list:
    
    # Convert relative path to absolute path based on the caller's working directory
    directory = os.path.abspath(directory)
    
    #Create a list of the filenames
    files =[]
    if (doRecursiveFolderSearch):
        files = [os.path.join(root, file) for root, _, files in os.walk(directory) for file in files] #Are we recursively looking through all subfolders?
    else:
        files = [directory+'/'+f for f in os.listdir(directory) if os.path.isfile(directory+'/'+f)] #Or are we just looking through the passed directory
        
    print("Loaded " + str(len(files)) + " total files.")
        
    #Filter out any non-matching filenames if we are doing matching
    if (filetypeMatchRegex is not None):
        regex = re.compile(filetypeMatchRegex, re.IGNORECASE)
        files = [f for f in files if regex.match(f)]
        print("Filtered down to " + str(len(files)) + " total file[s] with regex.")
        
    #Search through each filename and generate a list of all image files we want
    fileInfo = []
    for filename in files:
        print("Processing file: " + filename)
        try:
            parsedFilename = FileNameParser(filename)
            print("Parsed filename:")
            print(parsedFilename)
            #Make sure this is a valid filename
            if(
                isinstance(parsedFilename.get("Row"), str) and
                isinstance(parsedFilename.get("Column"), int) and
                isinstance(parsedFilename.get("UniqueSiteID"), str) and
                isinstance(parsedFilename.get("ROI"), int) and
                isinstance(parsedFilename.get("Zplane"), int) and
                isinstance(parsedFilename.get("Timepoint"), int) and
                isinstance(parsedFilename.get("Channel"), str) and
                isinstance(parsedFilename.get("PlateID"), str) and
                isinstance(parsedFilename.get("Path"), str)
            ):
                fileInfo.append(parsedFilename)
            else:
                raise Exception("Filename parsing failed for " + filename)
        except Exception as e:
            #If there was an error parsing the filename, just skip it
            #This could be due to a bad file or an unexpected format
            print("Error parsing filename: " + filename)
            print(e)
            continue
    return fileInfo 