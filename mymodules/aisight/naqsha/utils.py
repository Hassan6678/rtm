import random
from collections import namedtuple

# from dataclasses import dataclass, field

from pyproj import Transformer, Proj
from shapely.geometry import Point, Polygon
from shapely.ops import nearest_points, transform


# to handle the customer data inside the shapely.getometry.Point class
class CustomerPoint(Point):
    def __init__(self, *args, **kwargs):
        self.x_name = kwargs.pop("x_name", "")
        self.x_cust_code = kwargs.pop("x_cust_code", "")
        self.x_coordinates = kwargs.pop("x_coordinates", (None, None))
        
        self.x_flag = kwargs.pop("x_flag", None)
        self.x_sec = kwargs.pop("x_sec", "U")

        # self.x_channel = kwargs.pop("x_channel", None)
        # self.x_dist_code = kwargs.pop("x_dist_code", None)
        

        self.x_mta_id = kwargs.pop("x_mta_id", None)
        self.x_whitespace_id = kwargs.pop("x_whitespace_id", None)
        # self.x_boundary_id = kwargs.pop("x_boundary_id", None)

        super().__init__(*args, **kwargs)


# class to handle postion of customer and polygon coordinates
Coordinates = namedtuple("Coordinates", ["longitude", "latitude"])

def distance_in_meters(p1, p2):
    """
    distance in meters between two provided points
    """
    t_p1 = lnglat_to_meters(p1)
    t_p2 = lnglat_to_meters(p2)
    
    return t_p1.distance(t_p2)


def lnglat_to_meters(g):
    """
    param g: shapely object of type Point, Polygon
    """

    # 4326 => long/lat (spherical coordinates)
    # 3857 => meters (flat coordinates)

    # first is source coords system, second is destination coords system
    project_4326_3857 = Transformer.from_proj(Proj("epsg:4326"), Proj("epsg:3857"))

    # applying transformations, ".transform" we need to give us the property
    transformed_g = transform(project_4326_3857.transform, g)

    # normally the object we use are custom object with shapely.geometry -> Point & Polygon as parent. but transformation remova our custom attributes.
    # so to adjust missing attributes to newly build object we use "copy_na_attributes"  function written in this file

    return copy_na_attributes(g, transformed_g)


def meters_to_latlng(g):
    """
    param g: shapely object of type Point, Polygon
    """

    # 4326 => long/lat (spherical coordinates)
    # 3857 => meters (flat coordinates)

    # first is source coords system, second is destination coords system
    project_3857_4326 = Transformer.from_proj(Proj("epsg:3857"), Proj("epsg:4326"))

    # applying transformations
    transformed_g = transform(project_3857_4326.transform, g)

    # normally the object we use are custom object with shapely.geometry -> Point & Polygon as parent. but transformation remova our custom attributes.
    # so to adjust missing attributes to newly build object we use "copy_na_attributes"  function written in this file

    return copy_na_attributes(g, transformed_g)


def random_points_within(poly, num_points=1):
    points = []
    min_x, min_y, max_x, max_y = poly.bounds

    while len(points) < num_points:
        random_point = Point([random.uniform(min_x, max_x), random.uniform(min_y, max_y)])
        if random_point.within(poly):
            points.append(random_point)
    return points

# ================================================================================================= #
# ================================================================================================= #
# FUNCTIONS, WHICH ARE NOT DIRECTLY RELATED TO GEOMETRY WORKS, BUT OTHER FUNCTIONS USED THOSE OBJECTS

def copy_na_attributes(obj_from, obj_to):
    """
    This function copy copy_na_attributes from obj_From, which are not available (na) in obj_to
    """

    # get all the member of custom object using inspect module.
    for attr_n, attr_v in obj_from.__dict__.items():
        # 2nd condition is because of when i override the original classes to add custom attributes i name them all starting with "x_"
        if attr_n.startswith("x_"):
            setattr(obj_to, attr_n, attr_v)

    return obj_to


def get_intersecting_polygons(poly, sapolys):
    overlapping_polygons = []
    
    # intersecting polygon == ip, o_poly => overlapping polygon
    for ip in sapolys._str_tree.query(poly): 
        o_poly = ip.intersection(poly)
        if not o_poly.is_empty:
            if o_poly.geom_type == 'MultiPolygon':
                for so_poly in o_poly.geoms:
                    overlapping_polygons.append(copy_na_attributes(ip, so_poly))
            else:
                overlapping_polygons.append(copy_na_attributes(ip, o_poly))
        
    return overlapping_polygons