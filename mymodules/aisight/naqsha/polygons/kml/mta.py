from ..master_polygon import MasterPolygon

class MTA(MasterPolygon):
    _name = "mta"

    def __init__(self, *args, **kwargs):
        # calling parent class init
        super().__init__(*args, **kwargs)