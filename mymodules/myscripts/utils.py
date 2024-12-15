import json
import datetime
import numbers
from pathlib import Path

import numpy as np
import pandas as pd


class MyJsonEncoder1(json.JSONEncoder):
    _date_format = r"%Y-%m-%d"
    _round_to = 4

    def _preprocess_data(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.strftime(self._date_format)

        # checking numeric and then rounding off
        elif isinstance(obj, numbers.Number):
            if obj != obj: 
                return None
            elif isinstance(obj, bool):
                return obj
            else:
                return round(obj, self._round_to)

        elif isinstance(obj, pd.Timestamp):
            return obj.date().strftime(self._date_format)

        elif isinstance(obj, dict):
            return {self._preprocess_data(k): self._preprocess_data(v) for k, v in obj.items()}

        elif isinstance(obj, list):
            return [self._preprocess_data(i) for i in obj]
        
        elif isinstance(obj, set):
            return [self._preprocess_data(i) for i in obj]

        return obj

    def iterencode(self, obj, _one_shot=True):
        return super().iterencode(self._preprocess_data(obj), _one_shot)

    def default(self, obj):
        if isinstance(obj, datetime.date):
            return obj.strftime(self._date_format)
        
        elif isinstance(obj, set):
            return list(obj)
        
        elif isinstance(obj, np.ndarray):
            return [self._preprocess_data(v) for v in obj]
        
        elif isinstance(obj, np.integer):
            return int(obj)
        
        elif isinstance(obj, np.floating):
            return round(float(obj), self._round_to)
        
        elif pd.isnull(obj):
            return None

        return super(MyJsonEncoder1, self).default(obj)


# to json file with compatible casting
def to_json(d: dict, p: Path):
    with open(p, "w") as jf:
        json_str = json.dumps(d, cls=MyJsonEncoder1)
        jf.write(json_str)

# to raw json, no transformation will be applied
def to_rjson(d: dict, p: Path):
    with open(p, "w") as jf:
        json_str = json.dumps(d)
        jf.write(json_str)

def get_json_compatiable_dict(d: dict):
    json_str = json.dumps(d, cls=MyJsonEncoder1)
    json_dict = json.loads(json_str)
    return json_dict
