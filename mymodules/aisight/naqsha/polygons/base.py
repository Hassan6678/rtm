from collections import namedtuple

from shapely.geometry import Polygon
# from shapely.geos import TopologicalError


## BASE CLASSES DEFINITIONS ##

# class to handle postion of customer and polygon coordinates
Coordinates = namedtuple("Coordinates", ["longitude", "latitude"])

# creating a sub class to hold data for each populationtif pixel inside the shapely.polygon object it self
class PixelPolygon(Polygon):
    def __init__(self, *args, **kwargs):

        # creating custom attribute to hold data related to population.tif pixel
        self.x_population = kwargs.pop("x_population", 0)  # pixel raster (population data), dict.pop method will remove the key afterwards
        self.x_position = kwargs.pop("x_position", (0, 0))  # pixel position in rater_array, dict.pop method will remove the key afterwards

        # remove the values from **kwrags because, shapely.Polygon __init__ doesnot work by using *args & **kwargs
        super().__init__(*args, **kwargs)

# this subclass (SurveyAuto Polygon) to deal with polygon data of (whitespace, mta, sec, boundary)
class SAPolygon(Polygon):
    def __init__(self, *args, **kwargs):

        # creating custom attribute to hold data related to population.tif pixel
        self.x_id = kwargs.pop("x_id", 0)
        self.x_folder = kwargs.pop("x_folder", "")  # folder which contains the placemark
        self.x_name = kwargs.pop("x_name", "")  # name of the placemark (polygons) seen in google earth
        self.x_coordinates = kwargs.pop("x_coordinates", [])
        self.x_population = kwargs.pop("x_population", 0)  # pixel raster (population data), dict.pop method will remove the key afterwards
        self.x_sec = kwargs.pop("x_sec", {})  # sec information for specific polygon,
        self.x_class = kwargs.pop("x_class", "")
        self.x_address = kwargs.pop("x_address", "")

        # remove the values from **kwrags because, shapely.Polygon __init__ doesnot work by using *args & **kwargs
        super().__init__(*args, **kwargs)
