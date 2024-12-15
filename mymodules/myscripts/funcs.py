import json
from pathlib import Path
from datetime import date, datetime

import numpy as np
import pandas as pd

def date_to_str(d):
    if isinstance(d, (date, datetime, pd.Timestamp, pd.DatetimeIndex)):
        return f"{d.year}-{d.month}-{d.day}"
    else:
        raise Exception(
            "Date of type {type(d)} is passed, which is not handeled by default."
        )


def get_monthwise_dict(start: date, end: date, child_keys:list = None):
    # a datetime index according to provided datetime
    datetime_index = pd.date_range(start=start, end=end, freq="MS")

    # create an empty Dataframe from the datetime_index
    datetime_df = pd.DataFrame(index=datetime_index)

    if child_keys:
        default_value = dict.fromkeys(child_keys, 0)
    else:
        default_value = 0


    return dict.fromkeys(datetime_df.index.map(date_to_str), default_value)


def makesure_every_date(df: pd.DataFrame, start: date, end: date):
    """
    This will make sure that we have all the days (date) are present in the analysis daterange.
    """

    # a datetime index according to provided datetime
    datetime_index = pd.date_range(start=start, end=end)

    # create an empty Dataframe from the datetime_index
    datetime_df = pd.DataFrame(index=datetime_index)

    # merging to make sure that dataframe provided by the company (aisight client e.g., pmi/bat) has all the dates present in analysis daterange.
    # CONSTRAINTS: this will merge on index, and index should be DateTimeIndex of pandas library.
    complete_df = datetime_df.merge(df, how="left", right_index=True, left_index=True)
    complete_df.index.rename("index", inplace=True)

    return complete_df


def dict_to_json(d: dict, save_to: Path):
    # Internal class for saving dataframe obect to json
    class NpEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, (set, tuple, np.ndarray)):
                return list(obj)
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)

            # overirding the default function
            return super(NpEncoder, self).default(obj)

    with open(save_to, "w") as f:
        d_str = json.dumps(d, cls=NpEncoder)

        # handling NaN by replacing them
        d_str = d_str.replace("NaN", "null")

        f.write(d_str)
