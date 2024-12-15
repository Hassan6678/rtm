# standard library
from copy import deepcopy

# third party libs
from shapely.geometry import Point

# our code
from ..master_polygon import MasterPolygon


class SEC(MasterPolygon):
    _name = "sec"

    def __init__(self, *args, **kwargs):
        
        try:
            self.ptif = kwargs["ptif"]
        except KeyError as ke:
            print("SEC class requires PopulationTif object to proceed.")
            raise
        
        # calling parent class init
        super().__init__(*args, **kwargs)

        # create a default dictionary containing all the sec name as keys and zero as their default values
        self.sec_dict = self.default_sec_dict()


    # A dictionary containing all sec names, so can be assigned to all polygons.

    def default_sec_dict(self):
        # an empty set to keep all the unique sec names present in .kml as folders
        kml_sec_folders = set()
        for mypoly in self._polygons:
            kml_sec_folders.add(mypoly.x_folder)

        # create a dict from keys and assign them zero value by default
        sec_dict = dict.fromkeys(sorted(kml_sec_folders), 0)
        return sec_dict

    def normalize_sec_dict(self, sec_dict):
        k = sec_dict.keys()
        # because dict.values() return dict.values type object which cant be used for division
        v = list(sec_dict.values())

        # v_sum = sum(v)
        normalized_v = [single_value/sum(v) for single_value in v]
        normalized_sec_dict = dict(zip(k, normalized_v))
        return normalized_sec_dict


    # Operations on Polygon

    def get_polygon_sec_by_population(self, poly):
        _sec_dict = deepcopy(self.sec_dict)

        # str_tree query function will return all the intersecting polygons (from self._str_tree) in the tree with the poly provided
        intersecting_polygons = self._str_tree.query(poly)

        for mypoly in intersecting_polygons:

            # # check if intersecting, then go for calculating the intersection area (computational intensive), other wise ignore
            # if mypoly.intersects(poly):   # this return bool: True for intersecting, and False for not intersecting
            #     # how much of poly area is mapping to the sec polygon
            #     # overlap_area = ( poly.intersection(sec_polygon).area * 100 ) / poly.area  # use *100 for actual percentage like 78%
            #     # overlap_area = poly.intersection(poly_obj).area / poly.area  # this for actually calculating the intersecting area
            # this return a polygon consisting of intersection area
            overlap_poly = mypoly.intersection(poly)
            overlap_poly_population = self.ptif.get_population(overlap_poly)

            if overlap_poly.area > 0:
                # / poly_population
                _sec_dict[mypoly.x_folder] += overlap_poly_population

        # if the polygon (poly) passed has zero overlap with any of the sec polygon. which will left us the sec dict unchanged
        # so we can apply other nearby checks to provide sec to that polygon
        if _sec_dict == self.sec_dict:
            _sec_dict = self.get_polygon_sec_by_population_nearby(poly)

        # we want to normalized the population based _sec_dict to have values between zero and one.
        _sec_dict = self.normalize_sec_dict(_sec_dict)
        return _sec_dict

    def get_polygon_sec_by_population_nearby(self, poly):
        _sec_dict = deepcopy(self.sec_dict)

        # if no sec polygon interest with the given polygon, then find the nearest
        nearest_mypoly = self._str_tree.nearest(poly)
        # and assign its sec to the given polygon
        _sec_dict[nearest_mypoly.x_folder] += 1.0

        return _sec_dict

    def get_polygon_sec_by_area(self, poly):
        _sec_dict = deepcopy(self.sec_dict)

        # str_tree query function will return all the intersecting polygons (from self._str_tree) in the tree with the poly provided
        intersecting_polygons = self._str_tree.query(poly)

        for mypoly in intersecting_polygons:

            # check if intersecting, then go for calculating the intersection area (computational intensive), other wise ignore
            # this return bool: True for intersecting, and False for not intersecting
            if mypoly.intersects(poly):
                # how much of poly area is mapping to the sec polygon
                # overlap_area = ( poly.intersection(sec_polygon).area * 100 ) / poly.area  # use *100 for actual percentage like 78%
                # this for actually calculating the intersecting area
                overlap_area = mypoly.intersection(poly).area / poly.area
                if overlap_area > 0:
                    _sec_dict[mypoly.x_folder] += overlap_area

        # if the polygon (poly) passed has zero overlap with any of the sec polygon. which will left us the sec dict unchanged
        # so we can apply other nearby checks to provide sec to that polygon
        if _sec_dict == self.sec_dict:
            _sec_dict = self.get_polygon_sec_by_area_nearby(poly)

        # we want to normalized the area based _sec_dict to have values between zero and one.
        _sec_dict = self.normalize_sec_dict(_sec_dict)
        return _sec_dict

    def get_polygon_sec_by_area_nearby(self, poly):
        _sec_dict = deepcopy(self.sec_dict)

        # if no sec polygon interest with the given polygon, then find the nearest
        nearest_mypoly = self._str_tree.nearest(poly)
        # and assign its sec to the given polygon
        _sec_dict[nearest_mypoly.x_folder] += 1.0

        return _sec_dict


    # Operations on Point.

    def get_point_sec(self, p: Point):
        # sec value which will be assigned to the point, default is ""
        _sec_name = ""

        # str_tree query function will return all the intersecting polygons (from self._str_tree) in the tree with the poly provided
        intersecting_polygons = self._str_tree.query(p)

        for mypoly in intersecting_polygons:

            # check if given point exist in a sec polygon
            # this return bool: True for intersecting, and False for not intersecting
            if mypoly.contains(p):
                _sec_name = mypoly.x_folder
                return _sec_name

        # below condition will only be true, when customer point will not present in any of sec polygon
        if _sec_name == "":
            _sec_name = self.get_point_sec_nearby(p)

        return _sec_name

    def get_point_sec_nearby(self, p):
        # take point if not of shapely.geometry.Point class, covert
        p = p if isinstance(p, Point) else Point(p)

        # sec value which will be assigned to the point, default is ""
        _sec_name = ""

        # if point is not in any sec file then get the nearest sec polygon and assign that to the point
        nearest_mypoly = self._str_tree.nearest(p)

        _sec_name = nearest_mypoly.x_folder

        return _sec_name
