import os, re
from typing import Optional, Dict
from collections.abc import Callable

def HTS_CollectImageFiles(
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
        try:
            parsedFilename = FileNameParser(filename)

            #Make sure this is a valid filename
            if(
                isinstance(parsedFilename.get("well_row"), str) and
                isinstance(parsedFilename.get("well_column"), int) and
                isinstance(parsedFilename.get("well_site"), int) and
                isinstance(parsedFilename.get("channel"), int) and
                isinstance(parsedFilename.get("plate_name"), str) and
                isinstance(parsedFilename.get("plate_number"), int) and
                isinstance(parsedFilename.get("path"), str)
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