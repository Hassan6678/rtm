import json
import pandas as pd

from shapely.strtree import STRtree

# loading population tif class
from .tif.population_tif import PopulationTif

# loading all the polygons
from .polygons.sec import SEC
from .polygons.mta import MTA
from .polygons.whitespace import WhiteSpace
from .polygons.boundary import Boundary

# all the base setting for the project and files
from .config import *

# all the custom things we need like overidded class
from .utils import *


class Customers:
    def __init__(self, customer_csv=None) -> None:
        # if path is not provided explicitly then used the default present in the config file
        customer_csv = customers_infile if customer_csv == None else customer_csv

        cust_df = pd.read_csv(customer_csv, usecols=customer_columns)
        # cust_df.rename(columns=cust_cols, inplace=True)

        # only records where both longitude and latitude is present
        # cust_df = cust_df[(cust_df["longitude"].notnull()) & (cust_df["latitude"].notnull())]

        # load the all the kml_data in the form of class objects (mta, whitespace, boundary) & make interactions
        self.cache_populate_maps_data()

        # cahche the customers in the list form
        self._cust_points = self.cache_populate_customers(cust_df)

        # cache the customers in STRTree form
        self._str_tree = STRtree(self._cust_points)

    def cache_populate_maps_data(self):
        # creating a population tif object
        ptif = PopulationTif(tif_file=population_tif)

        # create sec polygons [SELF.SEC]
        self.sec = SEC(**{"kml_file": sec_kml, "ptif": ptif, "sec_o": None})

        # create boundary polygons [SELF.BOUNDARY]
        self.boundary = Boundary(
            **{"kml_file": boundary_kml, "ptif": ptif, "sec_o": self.sec})

        # create mta polygons [SELF.MTA]
        self.mta = MTA(
            **{"kml_file": mta_kml, "ptif": ptif, "sec_o": self.sec})

        # create whitespace [SELF.WHITESPACE]
        self.whitespace = WhiteSpace(
            **{"kml_file": whitespace_kml, "ptif": ptif, "sec_o": self.sec})

    def cache_populate_customers(self, cust_df):
        cust_points = []
        for row_indx, row in cust_df.iterrows():
            cust_coords = Coordinates(
                longitude=row["longitude"], latitude=row["latitude"])
            cust_point = CustomerPoint(cust_coords)

            cust_point.x_coordinates = cust_coords
            # cust_point.x_name = row["customer_name"]
            # cust_point.x_dist_code = row["distributor_code"]
            cust_point.x_cust_code = row["customer_code"]
            # cust_point.x_channel = row["channel"]

            location_flag = self.get_location_flag(cust_coords)
            cust_point.x_loc_flag = location_flag

            if location_flag == "OK":
                cust_point.x_sec = self.sec.get_point_sec(cust_point)
                cust_point.x_mta_id = self.mta.get_containing_polygon(
                    cust_point)
                cust_point.x_whitespace_id = self.whitespace.get_containing_polygon(
                    cust_point)

            cust_points.append(cust_point)

        return cust_points

    def customers_in_polygon(self, poly):
        containing_points = self._str_tree.query(poly)
        # this return list of CustomerPoint type objects which contains all the information
        return [cp for cp in containing_points if poly.contains(cp)]

    def get_location_flag(self, p):
        if pd.isnull(p.longitude) or pd.isnull(p.latitude):
            # coordinates are incomplete, one or both are missing
            return 'M'
        elif p.longitude == 0 or p.latitude == 0:
            # one of the coordinates is zero or both are zero
            return 'Z'
        elif not self.boundary.is_in_boundary(p):
            # customer is out of boundary
            return 'OB'
        else:
            return 'OK'

    def to_files(self):

        customers_csv_path = str(
            CUSTOMER_FOLDER / f"customers.csv")
        mappings_path = str(CUSTOMER_FOLDER / f"mappings.json")

        all_cust = []

        for c in self._cust_points:
            all_cust.append(
                {
                    # "distributor_code": c.x_dist_code,
                    "customer_code": c.x_cust_code,
                    # "customer_name": c.x_name,
                    # "channel": c.x_channel,
                    "longitude": c.x_coordinates.longitude,
                    "latitude": c.x_coordinates.latitude,
                    "sec": c.x_sec,
                    "mta_id": c.x_mta_id,
                    "whitespace_id": c.x_whitespace_id,
                    "loc_flag": c.x_loc_flag,
                }
            )

        df = pd.DataFrame(all_cust)
        df.to_csv(customers_csv_path, index=False)

        # ? Special Work for BAT CODE
        # ------------------------------------------------------------
        special_path = str(f"../Data/{city}/findings/customers.csv")

        df.rename(columns={"customer_code": "RCS_CODE"}, inplace=True)
        df.to_csv(special_path, index=False)

        # -------------------------------------------------------------

        mappings = {"mta": self.mta.to_dict(), "whitespace": self.whitespace.to_dict(
        ), "sec": self.sec.to_dict(), "boundary": self.boundary.to_dict()}

        with open(mappings_path, "w") as f:
            json.dump(mappings, f)

        # ? Special Work for BAT CODE
        # ---------------------------------------------------------------------
        special_mappings_path = str(f"../Data/{city}/findings/mappings.json")

        with open(special_mappings_path, "w") as f:
            json.dump(mappings, f)
        # ----------------------------------------------------------------------

        print(f"File Written Successfully in {CUSTOMER_FOLDER}")
