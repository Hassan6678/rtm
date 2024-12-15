import imp
import json
from shapely.geometry import Point
from shapely.strtree import STRtree
from .utils import PMIAreaPolygon
        
class PMIAreas:
    def __init__(self, json_file) -> None:
        self._polygons = self.polygons_from_file(json_file)
        
        # polygons are cached in the form of STR-TREE (Spatial Indexing)
        self._str_tree = STRtree(self._polygons)
    
    def polygons_from_file(self, json_file):
        polygon_counter = 1
        data = None
        _polygons = []
        
        with open(json_file, 'rb') as f:
            data = json.load(f)
        
        
        for zone in data:
            zone_children = zone["children"]
            
            for city in zone_children:
                city_children = city["children"]
                
                for region in city_children:
                    region_children = region["children"]
                    
                    for area in region_children:
                        coords = area["geometry"]["coordinates"]
                        area_polygon = PMIAreaPolygon(coords)
                        
                        area_polygon.x_id = polygon_counter
                        area_polygon.x_zone = zone["value"]
                        area_polygon.x_city = city["value"]
                        area_polygon.x_region = region["value"]
                        area_polygon.x_area = area["value"]                    
                
                        _polygons.append(area_polygon)
                        # change the id 
                        polygon_counter+= 1
                    
        return _polygons

    def get_containing_polygon(self, p):
        # take point if not of shapely.geometry.Point class, covert to it
        geo_point = p if isinstance(p, Point) else Point(p)

        # run a search on all polygons via self._str_tree
        containing_polygon = [poly for poly in self._str_tree.query(geo_point) if poly.contains(geo_point)]

        # if list is not empty return the polygon at first position || otherwise return None
        if containing_polygon:

            # NOTE return only id of polygon not the actual polygon
            # return containing_polygon[0].x_id
            return containing_polygon[0].x_area
        else:
            return None

    def query_polygons(self, zone=None, city=None, region=None, area=None):
        selected_polygons = []

        for poly in self._polygons:
            if (poly.x_city == city) and (poly.x_area == area):
            # if (poly.x_zone == zone) and  (poly.x_city == city) and (poly.x_region==region) and (poly.x_area == area):
                selected_polygons.append(poly.x_id)
        
        return selected_polygons
