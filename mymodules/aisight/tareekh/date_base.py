from datetime import date, datetime
from dateutil.relativedelta import relativedelta


date_to_Ym = lambda x: x.strftime("%Y-%m")


def get_date_span(d: date, n: int = 0, included:bool = True):
    """
    Get the start date and end date of "n" months forward or backward, from the month mentioned in "d" argument.
    :param d: current date, this is used to get the current month value
    :param n: how many months we want to look forwad or backward, e.g., n=4 means we want start date and end date of next four month span
    :return: tuple(start_date:date, end_date:date)
    """

    if included:
    
        if n > 0:
            # this will look ahead to create a date span

            span_start: date = d + relativedelta(day=1)
            span_end: date = d + relativedelta(months=n) + relativedelta(day=31)

        elif n < 0:
            # this will look backward to create a date span

            span_start: date = d + relativedelta(months=n) + relativedelta(day=1)
            span_end: date = d + relativedelta(day=31)

        else:
            # this will return the span consisted of month mentioned in the "d" arguemnt.

            span_start: date = d + relativedelta(day=1)
            span_end: date = d + relativedelta(day=31)
    
    else:

        if n > 0:
            # this will look ahead to create a date span

            span_start: date = d + relativedelta(months=1) + relativedelta(day=1)
            span_end: date = d + relativedelta(months=n) + relativedelta(day=31)

        elif n < 0:
            # this will look backward to create a date span

            span_start: date = d + relativedelta(months=n) + relativedelta(day=1)
            span_end: date = d + relativedelta(months=-1) + relativedelta(day=31)

        else:
            # this will return the span consisted of month mentioned in the "d" arguemnt.

            span_start: date = d + relativedelta(day=1)
            span_end: date = d + relativedelta(day=31)

    return (span_start, span_end)


def get_date_iterator(s: date, e: date, reverse=False):
    """
    Get the iterator of dates between two dates.
    :param s: start date
    :param e: end date
    :param reverse: move from start to end OR end to start
    :return: iterator of dates between the two dates
    """

    # assigning "s" to "dt" a temporary variable (date_temporary), so we will not loose the orignal values passed to function in debugging.
    dt = s

    # convert d1 & d2 to  
    while dt <= e:
        to_yield = get_date_span(dt, n=0)
        dt += relativedelta(months=1)
        yield(to_yield)


def get_days_inbetween(s: date, e: date):
    """
    Get the number of days between two dates.
    :param s: start date
    :param e: end date
    :return: number of days between the two dates
    """

    # +1 is added because below calcualtion missed one day from the date gap.
    return abs(e - s).days + 1