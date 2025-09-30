import numbers
import sys

import numpy as np
import pandas as pd

from mymodules.aisight.naqsha import Boundary, SEC, WhiteSpace
from mymodules.aisight.naqsha.polygons.tif.population_tif import PopulationTif

def setup(dir, add_popuatlion=False, add_sec=True,):
    global ptif
    global sec
    global boundary
    global mta
    global whitespace
    global routes

    ptif = PopulationTif(file=dir / "tifs" / "population.tif")
    sec = SEC(file=dir / "kmls" / "sec.kml", ptif=ptif)
    sec.add_population_data(ptif)

    boundary = Boundary(file=dir / "kmls" / "boundary.kml")
    boundary.add_sec_data(sec)
    boundary.add_population_data(ptif)

    # mta_file = dir / "kmls" / "mta.kml"
    # mta = MTA(file=mta_file) if mta_file.exists() else None
    # mta.add_sec_data(sec)
    # mta.add_population_data(ptif)

    whitespace_file = dir / "kmls" / "whitespace_.kml"
    whitespace = WhiteSpace(file=whitespace_file) if whitespace_file.exists() else None
    whitespace.add_sec_data(sec)
    whitespace.add_population_data(ptif)

    # routes = Routes(file=dir / "kmls" / "routes.kml")
    # routes.add_sec_data(sec)
    # routes.add_population_data(ptif)

    return (
        boundary,
        # mta,
        ptif,
        # routes,
        sec,
        whitespace,
    )


def get_location_flag(p):
    if not boundary.is_in_boundary(p):
        # customer is out of boundary
        return "OB"
    else:
        return "OK"


def assign_polygons(p):
    if p.is_valid and not p.is_empty:
        return {
            "mta": mta.get_containing_polygon(p).x_id if mta.get_containing_polygon(p) else np.nan,
            "whitespace": whitespace.get_containing_polygon(p).x_id if whitespace.get_containing_polygon(p) else np.nan,
            "aisight_route": routes.get_containing_polygon(p).x_name.upper() if routes.get_containing_polygon(p) else np.nan,
            "sec": sec.get_point_sec(p),
            "flag": get_location_flag(p),
        }
    else:
        return {"flag": np.nan}


def get_new_coords(p, fmcg_rcode, aisight_rcode):
    if isinstance(fmcg_rcode, numbers.Complex) and not pd.isnull(fmcg_rcode):
        fmcg_rcode = str(int(fmcg_rcode))
    elif isinstance(fmcg_rcode, str) and pd.isnull(fmcg_rcode):
        fmcg_rcode = fmcg_rcode.strip()

    to_return = dict.fromkeys(["route_status", "route", "n_latitude", "n_longitude"], np.nan)

    if aisight_rcode != fmcg_rcode:
        # they are null, we are not
        if (not pd.isnull(aisight_rcode)) and (pd.isnull(fmcg_rcode)):
            to_return.update(
                {
                    "route_status": "aisight",
                    "route": aisight_rcode,
                    "n_longitude": p.x,
                    "n_latitude": p.y,
                }
            )

        # we are null, they are not
        elif (pd.isnull(aisight_rcode)) and (not pd.isnull(fmcg_rcode)):
            try:
                route_poly = [p for p in routes._polygons if p.x_name == fmcg_rcode][0]
                random_p = random_points_within(route_poly)[0]

                to_return.update({
                        "route_status": "fmcg",
                        "route": fmcg_rcode,
                        "n_longitude": random_p.x,
                        "n_latitude": random_p.y,
                    })
            except IndexError as ie:
                to_return.update({
                        "route_status": "error_fmcg",
                        "route": fmcg_rcode,
                        "n_longitude": p.x,
                        "n_latitude": p.y,
                    })

        # "we and they" are not null but also not on the same page
        elif (not pd.isnull(aisight_rcode)) and (not pd.isnull(fmcg_rcode)):
            try:
                route_poly = [p for p in routes._polygons if p.x_name == fmcg_rcode][0]
                random_p = random_points_within(route_poly)[0]

                to_return.update({
                        "route_status": "fmcg",
                        "route": fmcg_rcode,
                        "n_longitude": random_p.x,
                        "n_latitude": random_p.y,
                    })
            except IndexError as ie:
                to_return.update({
                        "route_status": "error_aisight",
                        "route": aisight_rcode,
                        "n_longitude": p.x,
                        "n_latitude": p.y,
                    })
    else:
        # Good !!! "we and they" are on same page, Yaay...
        to_return.update({
                "route": fmcg_rcode,
                "route_status": "same",
                "n_longitude": p.x,
                "n_latitude": p.y,
            })

    return to_return
