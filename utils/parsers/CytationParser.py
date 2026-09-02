import os
#from PIL import Image
#import xmltodict
from datetime import datetime

#Parse the filenames for the Cytation 5
def CytationParser(filename):
    basename = os.path.basename(filename)[:-4] #all of these files must end in .tif so I can just remove that
    nameComponents = basename.split("_")
    
    Row = nameComponents[0][0]
    Column = int(nameComponents[0][1:])
    Timepoint = int(nameComponents[5])
    
    #The FOV appears as the form [ROI]Z[Z-plane]
    raw_fov = nameComponents[3].split("Z")
    
    if len(raw_fov) > 1:
        #This means we have more than one Z position in our data
        ROI = int(raw_fov[0])
        Zplane = int(raw_fov[1])
    else:
        ROI = int(raw_fov[0])
        Zplane = 1
    
    return {
        "Row":nameComponents[0][0], 
        "Column":int(nameComponents[0][1:]),
        "Well":nameComponents[0], 
        "ROI": ROI,
        'Zplane': Zplane, 
        "Timepoint":int(nameComponents[5]), 
        "PlateID":"OSB001", 
        "Channel":nameComponents[4],
        "Path":filename   
    }
    
    
#Old code, Do not use
def Old():
    try:
        with Image.open(filename) as img:
            exifdata = img.getexif()
            #The ImageDescription tag will always be "0x010e" in the exif data
            img_data = xmltodict.parse(exifdata.get(0x010e))
    except:
        date_time = None
        LEDIntensity = None
        CameraGain = None
        BrightnessLevel = None 
        ObjectiveSize = None
    else:
         #parse the date and time from the metadata as a python time object
        date_time = datetime.strptime(img_data["BTIImageMetaData"]["ImageReference"]["Date"] + " " + img_data["BTIImageMetaData"]["ImageReference"]["Time"], "%m/%d/%y %H:%M:%S")
    
        #Extract the image capture settings
        LEDIntensity = img_data["BTIImageMetaData"]["ImageAcquisition"]["LEDIntensity"]
        CameraGain = img_data["BTIImageMetaData"]["ImageAcquisition"]["CameraGain"] 
        BrightnessLevel = img_data["BTIImageMetaData"]["ImageAcquisition"]["BrightnessLevel"]
        ShutterSpeedMS = img_data["BTIImageMetaData"]["ImageAcquisition"]["ShutterSpeedMS"]
        ObjectiveSize = img_data["BTIImageMetaData"]["ImageAcquisition"]["ObjectiveSize"]


    return{
        "Row":nameComponents[0][0], 
        "Column":nameComponents[0][1:], 
        "ROI":int(nameComponents[3]), 
        "Timepoint":int(nameComponents[5]), 
        "PlateID":"OSB001", 
        "Channel":nameComponents[4],
        "Path":filename,
        "DateTime":date_time,
        "LEDIntensity":LEDIntensity,
        "CameraGain":CameraGain,
        "BrightnessLevel":BrightnessLevel,
        "ShutterSpeedMS":ShutterSpeedMS,
        "ObjectiveSize":ObjectiveSize
    }



##Example metadata for a cytation5 image:
# {
#     "BTIImageMetaData": {
#         "@Version": "34",
#         "System": {
#             "Gen5": {
#                 "Version": "3.12.08"
#             },
#             "Reader": {
#                 "Model": "Cytation5",
#                 "SerialNumber": "1706232",
#                 "BasecodeVersion": "2.07"
#             },
#             "Camera": {
#                 "Model": "Grasshopper3 GS3-U3-14S5M",
#                 "ColorCamera": "FALSE",
#                 "UprightImager": "FALSE",
#                 "SerialNumber": "17105694",
#                 "Firmware": "2.6.3.2",
#                 "Driver": "USB Camera Driver (PGRUsbCam.sys) - 2.7.3.84",
#                 "DriverVersion": "USB Camera Driver (PGRUsbCam.sys) - 2.7.3.84",
#                 "SaturationLevel": "65520"
#             }
#         },
#         "ImageReference": {
#             "Experiment": "S:\\Data\\Research\\Skaar Lab\\Owen\\20250201_OSB001_KineticBa.xpt",
#             "Plate": "Plate 1",
#             "DataSet": "GFP 469,525",
#             "OriginalFilename": "E:\\250201_164233_20250201_OSB001_KineticBa\\250201_164712_Plate 1\\B2_03_2_1_GFP_014.tif",
#             "Date": "02/01/25",
#             "Time": "20: 00: 10",
#             "Daylight": "FALSE",
#             "ImageStatus": "ImageOk",
#             "PlateType": "Costar 96 clear bottom black side",
#             "WellShape": "Circle",
#             "WellDiameterMicrons": "6350",
#             "Vessel": "1",
#             "Well": "B2",
#             "ReadStepIndex": "2",
#             "MeasurementIndex": "1",
#             "MeasurementTotal": "3",
#             "KineticStartDate": "02/01/25",
#             "KineticStartTime": "20: 00: 04",
#             "KineticStartDaylight": "FALSE",
#             "KineticSequence": "13",
#             "KineticTimeMs": "11550000",
#             "KineticReadsTotal": "121",
#             "KineticIntevalMs": "60000",
#             "HorizontalIndex": "1",
#             "HorizontalTotal": "2",
#             "HorizontalOffsetMicrons": "-197",
#             "RegistrationHorizontalOffsetMicrons": "0",
#             "ReadStepImageHorizOffsetMicrons": "0",
#             "HorizontalSpacingMicrons": "394",
#             "VerticalIndex": "1",
#             "VerticalTotal": "3",
#             "VerticalOffsetMicrons": "291",
#             "RegistrationVerticalOffsetMicrons": "0",
#             "ReadStepImageVertOffsetMicrons": "0",
#             "ReadStepImageZReferenceMicrons": "3226.300000",
#             "RegistrationImages": "0",
#             "VerticalSpacingMicrons": "291",
#             "ZStackStepSizeMicrons": "0",
#             "ZStackTotal": "1",
#             "ZStackFocalPosition": "1",
#             "ZStackPosition": "1"
#         },
#         "ImageAcquisition": {
#             "Binning": "None",
#             "PixelWidth": "1224",
#             "PixelHeight": "904",
#             "ImageWidthMicrons": "394",
#             "ImageHeightMicrons": "291",
#             "ReducedFieldOfView": "Standard",
#             "ObjectiveSize": "20",
#             "DisplayedObjectiveSize": "20x",
#             "ObjectiveBTIPartNumber": "1320517",
#             "ObjectiveMfg": "Olympus",
#             "NumericalAperture": "0.45",
#             "ObjectivePSFSigma": "0.806",
#             "Temperature": {
#                 "Status": "DirectFromReader",
#                 "Value": "37"
#             },
#             "ColorBrightField": "FALSE",
#             "Channel": {
#                 "@Color": "GFP",
#                 "BrightField": "FALSE",
#                 "PhaseContrast": "FALSE",
#                 "ExcitationWavelength": "469",
#                 "EmissionWavelength": "525",
#                 "RedStainFactor": "0",
#                 "GreenStainFactor": "100",
#                 "BlueStainFactor": "22"
#             },
#             "FocalHeightMicrons": "3226.3",
#             "FocalMetricRatio": "-1",
#             "LaserBottomElevation": "FALSE",
#             "BottomElevationMicrons": "3218",
#             "ReversePlateOrientation": "FALSE",
#             "LEDIntensity": "10",
#             "ShutterSpeedMS": "50",
#             "CameraGain": "15.6",
#             "BrightnessLevel": "50",
#             "ContrastLevel": "33",
#             "VibrationCV": "0",
#             "VibrationImagesAcquired": "1",
#             "RDOP22XVersion": "3.12.08.0"
#         },
#         "ImageProcessing": {
#             "EliminatePixelsOutsideOfWell": "FALSE"
#         },
#         "Diagnostics": {
#             "Diag1": "CAPTURE\\/CAPTURE: 39.15",
#             "OffsetMsec": "11553016",
#             "FlIlluminationCorrectEnabled": "FALSE"
#         }
#     }
# }