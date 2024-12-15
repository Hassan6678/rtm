from ..master_polygon import MasterPolygon


class Routes(MasterPolygon):
    _name = "routes"

    def __init__(self, *args, **kwargs):
        # calling parent class init
        super().__init__(*args, **kwargs)
