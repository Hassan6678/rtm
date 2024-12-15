from ..master_polygon import MasterPolygon

class WhiteSpace(MasterPolygon):
    _name = "whitespace"

    def __init__(self, *args, **kwargs):
        # calling parent class init
        super().__init__(*args, **kwargs)