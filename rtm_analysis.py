import sys
from functools import reduce
from pathlib import Path
import multiprocessing as mp

from shapely.geometry import Polygon

import pandas as pd
import numpy as np

import yaml

def calculate_SEC(SEC_data, p:Path):
    output_dict = []
    for i in SEC_data:
        coordinates = SEC_data[i]['coordinates']
        output_dict.append({
            "coordinates": [
                {"lat": i[1], "lng": i[0]} for i in coordinates
            ],
            "sec": SEC_data[i]['folder'],
            "population" : SEC_data[i]['population'],
            "area": 0,
        })
    utils.to_json(output_dict, p / "sec_polygons.json")
    print("SEC Polygons Completed .")

def calculate_population_density(boundary,ptif,p:Path):
    boundary_polygon = boundary._polygons[0]
    TIF_data = ptif.to_dict()
    output_dict = []
    for i in TIF_data:
        x, y = TIF_data[i]['position']
        coordinates = TIF_data[i]['coordinates']
        population = TIF_data[i]['population']
        pixel_poly = Polygon(coordinates)
        area_percent = (
            pixel_poly.intersection(boundary_polygon).area / pixel_poly.area
        )
        population_pct = int(round(population*area_percent))
        color_code = (population_pct / 100) * 255
        color_code = hex(int(color_code)).split('x')[-1].zfill(2)
        
        if population_pct > 100: color = f'ff0000ff'
        else: color = f'ff0000{color_code}'
        output_dict.append({
            "id" : f"{x}_{y}",
            "coordinates": [
                {"lat": i[1], "lng": i[0]} for i in coordinates
            ],
            "population" : population,
            "color" : color
        })
    
    utils.to_json(output_dict, p / "population_density.json")
    print("Population Density Completed .")

def calculate_whitespace(config, ws_data, area_name, p:Path):
    customers_file = Path(config["paths"]["data"]) / area_name / "customers" / "customers.csv"
    census_file = Path(config["paths"]["data"]) / area_name / "customers" / "census_customers.csv"

    customers = pd.read_csv(customers_file)
    census = pd.read_csv(census_file)

    output_json = {
        "locations": [],
    }
    for i in ws_data:
        coordinates = ws_data[i]['coordinates']
        id = ws_data[i]['id']
        sec = ws_data[i]['sec']
        population = ws_data[i]['population']
        address = ws_data[i]['address']
        censusCount = census[census["whitespace"] == id].customer_code.nunique()
        outletCount = customers[customers["whitespace"] == id].customer_code.nunique()

        flag = "EMPTY"
        if outletCount > 0:
            if outletCount > censusCount:
                flag = "COVERED"
            elif censusCount > 0:
                flag = "SA Census"
        
        output_json["locations"].append({
            "_id": id,
            "boundary": {
                "polygon": coordinates
            },
            "data": {
                "flag": flag,
                "stores": outletCount,
                "census_store": censusCount,
                "address": address,
                "population": round(population),
                "household" : population//6.5,
                "SEC": sec,
            }
        })
    
    utils.to_json(output_json, p / "whitespace_data.json")
    print("Whitespace Calculation Completed .")

def make_customer_mapping(): pass

def make_sec_grid(): pass


if __name__ == "__main__":
    # analysis configuration file
    config = yaml.safe_load(sys.argv[1],)

    # add my module to the path variables
    # sys.path.append(Path(config["paths"]["mymodules"]).resolve())

    # from mymodules.aisight.naqsha import *
    # from mymodules.aisight.tareekh import *

    from mymodules.myscripts import kml_mapper, utils

    debug = True if config["process"]["debug"] else False

    company = config["analysis"]["company"]
    country = config["analysis"]["country"]
    area_name = config["analysis"]["area"]

    geo_dir = Path(config["paths"]['data']).resolve() / area_name

    output_folder = Path(config["paths"]['output']).resolve() / area_name
    output_folder.mkdir(parents=True, exist_ok=True)

    # sec_file = output_folder / "sec_polygons.json"
    # population_density_file = output_folder / "population_density.json"

    # if sec_file.exists() and population_density_file.exists():
    #     print("From Disk: SEC & Population density Loaded & Saved Successfully !!!")
    #     # gracefully closing the script
    #     sys.exit()

    population_scale = float(config["geo"]["tif"]["scale"])

    # kml mappers
    boundary, ptif, sec, whitespace = kml_mapper.setup(geo_dir)

    # Updating global config to make it working
    globals().update({   
            "to_json": utils.to_json,
        })

    # MP Variables
    jobs = []
    pipe_list = []

    calculate_SEC(sec.to_dict(), output_folder)
    calculate_population_density(boundary,ptif,output_folder)
    calculate_whitespace(config, whitespace.to_dict(), area_name, output_folder)

    print("\n... ||= FINISHED =|| ...\n")
