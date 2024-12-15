from datetime import date
from time import time

from copy import deepcopy

import pandas as pd
import numpy as np
from dateutil.relativedelta import relativedelta


timestamp_to_pydate = lambda ts: ts.py_todatetime().date()
timestamp_to_str = lambda ts: ts.strftime('%m-%y')


def get_datewise_dict(s: date, e: date, skeleton=0,  freq="MS"):

    # a datetime index according to provided datetime
    datetime_index = pd.date_range(start=s, end=e, freq=freq)

    # create an empty Dataframe from the datetime_index
    datetime_df = pd.DataFrame(index=datetime_index)

    return dict.fromkeys(datetime_df.index.map(timestamp_to_str), deepcopy(skeleton))


def makesure_every_date(df: pd.DataFrame, s: date = None , e: date = None):
    """
    This takes a data frame which must have a "date" column of type "datetime64[ns]". this will make sure that present months must have all the days in data,
    this helps us when we take groupby on the basis of date.
    """

    if "date" in df.select_dtypes([np.datetime64]).columns:
        # date named column must be presen and should be of type np.datetime64
        df.index = df.date 
    elif df.index.dtype.kind == "M":
        pass
    else:
        print("No column or index is found of type np.datetime")
        raise NotImplementedError
        
    # change the index name, so it will not conflicted with the date column
    df.index.rename("index", inplace=True)

    # if min & max date is not provided get the 
    min_date = s if s else df.date.min().date()
    max_date = e if e else df.date.max().date()

    # what soever date is provided we will move to first day of min_date and last day of max_date.
    span_start: date = min_date + relativedelta(day=1)
    span_end: date = max_date + relativedelta(day=31)

    # a datetime index according to provided datetime
    daterange_df = pd.DataFrame(index = pd.date_range(start=span_start, end=span_end))

    # merge with daterange_df to makesure every date
    datetime_df = daterange_df.merge(df, how="left", left_index=True, right_index=True, validate="1:m")

    # create a date column, because in some code portion i am using date column instead of index only
    datetime_df["date"] = datetime_df.index

    return datetime_df
