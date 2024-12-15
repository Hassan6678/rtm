from shapely.geometry import Point

from ..master_polygon import MasterPolygon


class Boundary(MasterPolygon):
    _name = "boundary"

    def __init__(self, *args, **kwargs):
        # calling parent class init
        super().__init__(*args, **kwargs)

    def is_in_boundary(self, p: Point):
        # check if a given point is in boundary or not
        containing_polygons = self._str_tree.query(p)
        for cp in containing_polygons:
            if cp.contains(p):
                return True
        return False
