import json
import requests

# third party
from shapely.geometry import Point
from shapely.strtree import STRtree
from tqdm import tqdm

# our code
from .base import Coordinates, SAPolygon
from .kml_reader import KMLReader


class MasterPolygon:
    poly_address = {}

    def __init__(self, *args, **kwargs):
        # this object is required by "from_kml" method
        self.kml_reader = KMLReader(*args, **kwargs)

        # get ip of nominatum server for address retrival of polygons
        self.notminatum_ip = kwargs.get("nominatum_ip", None)

        # all poygons of one sepcific class is cached in list of SAPolygon format
        self._polygons = self.from_kml()

        # add addresses to the polygons
        # self.add_address_data("http://192.168.10.50:8080")
        # self.add_address_data("https://nominatim.openstreetmap.org")

        # polygons are cached in the form of STR-TREE (Spatial Indexing)
        self._str_tree = STRtree(self._polygons)

    def from_kml(self):
        # we only need Polygon type
        placemarks = []

        # data in kml_reader is list of Placemarks
        for indx, placemark in enumerate(self.kml_reader.data):

            sa_polygon = SAPolygon(placemark.coordinates)
            # setting custom attributes
            sa_polygon.x_class = self._name  # passed by child class
            sa_polygon.x_id = indx
            sa_polygon.x_coordinates = placemark.coordinates
            sa_polygon.x_name = placemark.name
            sa_polygon.x_folder = placemark.folders[-1]

            if sa_polygon.is_valid and not sa_polygon._is_empty:
                placemarks.append(sa_polygon)

        return placemarks

    def get_containing_polygon(self, p: Point):

        # run a search on all polygons via self._str_tree
        containing_polygon = [poly for poly in self._str_tree.query(p) if poly.contains(p)]

        # if list is not empty return the polygon at first position || otherwise return None
        if containing_polygon:
            # this will return a polygon of SAPolygon type.
            return containing_polygon[0]

    def add_population_data(self, ptif_o):
        # sapoly => SAPolygon Object
        for sapoly in self._polygons:

            sapoly_population = ptif_o.get_population(sapoly)
            sapoly.x_population = sapoly_population

    def add_address_data(self, notminatum_ip):
        for indx, poly in enumerate(self._polygons):
            # latitude was bigger and longitude was lesser so we after checking on map we assigned
            poly_center = Coordinates(longitude=poly.centroid.x, latitude=poly.centroid.y)

            # res = requests.get(
            # f'{notminatum_ip}/reverse?accept-language=en&format=json&zoom=18&addressdetails=1&lat={center_coords.latitude}&lon={center_coords.longitude}',
            # timeout=2.5)

            res = requests.get(
                f"{notminatum_ip}/reverse?accept-language=en&format=json&zoom=18&addressdetails=1&lat={poly_center.latitude}&lon={poly_center.longitude}",
                timeout=5,
            )

            res_dict = res.json()
            poly.x_address = res_dict["display_name"] if res_dict["display_name"] else ""

        print(f"Addresses added to {self._name} polygons.")

    def add_sec_data(self, sec_o):
        # sapoly: SAPolygon
        print("Propagating SEC . . .")
        for sapoly in self._polygons:
            sapoly_sec = sec_o.get_polygon_sec_by_population(sapoly)
            sapoly.x_sec = sapoly_sec

    def get_polygon_by_name(self, val=""):
        for poly in self._polygons:
            if poly.x_name == val:
                return poly
        return None

    def get_polygon_by_id(self, val=""):
        for poly in self._polygons:
            if poly.x_id == val:
                return poly
        return None

    def to_dict(self, by="id"):

        _dict = {}

        if by == "id":
            for poly in self._polygons:
                _dict[poly.x_id] = {
                    "id": poly.x_id,
                    "folder": poly.x_folder,
                    "name": poly.x_name,
                    "coordinates": poly.x_coordinates,
                    "population": poly.x_population,
                    "sec": poly.x_sec,
                    "ofclass": poly.x_class,
                    "address": poly.x_address,
                    # custom atributes fo
                    "center": Coordinates(longitude=poly.centroid.x, latitude=poly.centroid.y),
                }
        elif by == "name":
            for poly in self._polygons:
                _dict[poly.x_name] = {
                    "id": poly.x_id,
                    "folder": poly.x_folder,
                    "name": poly.x_name,
                    "coordinates": poly.x_coordinates,
                    "population": poly.x_population,
                    "sec": poly.x_sec,
                    "ofclass": poly.x_class,
                    "address": poly.x_address,
                    # custom atributes fo
                    "center": Coordinates(longitude=poly.centroid.x, latitude=poly.centroid.y),
                }

        return _dict

    @classmethod
    def from_dict(cls, json_file=""):
        # creatin""g object by reading json file

        # this variable is to cache all the data we got from the json file
        data_dict = None

        with open(json_file, "w") as f:
            data_dict = json.load(f)

        for k, v in data_dict.items():
            pass

        """ 
        !NOTE:  Init function is not written in a way to use a dict to create a object from polygons, i think we need add more method to add polygons to
        these calsses like from_kml, from_json, etc and simmilarly , to_json, to_kml, 
        """
