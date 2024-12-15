from shapely.geometry import Polygon

# this subclass (PMIAreaPolygon) deal with polygon data of (PMI polygon of areas)
class PMIAreaPolygon(Polygon):
    def __init__(self, *args, **kwargs):

        # creating custom attribute to hold data related to population.tif pixel
        self.x_id = kwargs.pop("x_id", 0)
        self.x_zone = kwargs.pop("x_zone", None)
        self.x_city = kwargs.pop("x_city", None)
        self.x_region = kwargs.pop("x_region", None)
        self.x_area = kwargs.pop("x_area", None)
        
        # remove the values from **kwrags because, shapely.Polygon __init__ doesnot work by using *args & **kwargs
        super().__init__(*args, **kwargs)
        