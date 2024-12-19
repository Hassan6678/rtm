import sys
from functools import reduce
from pathlib import Path
import multiprocessing as mp
import pickle
import json
from time import sleep

import pandas as pd
import numpy as np
from tqdm import tqdm
import yaml

def calculate_SEC(): pass
def calculate_population_density(): pass
def calculate_whitespace(): pass
def make_customer_mapping(): pass


if __name__ == "__main__":
    # analysis configuration file
    config = yaml.safe_load(sys.argv[1],)

    # add my module to the path variable
    sys.path.append(Path(config["paths"]["mymodules"]).resolve())

    from mymodules.aisight.naqsha import *
    from mymodules.aisight.tareekh import *

    from mymodules.myscripts import kml_mapper, utils

    debug = True if config["process"]["debug"] else False

    company = config["analysis"]["company"]
    country = config["analysis"]["country"]
    area_name = config["analysis"]["area"]

    geo_dir = Path(config["paths"][company][country]['data']).resolve() / area_name

    output_folder = Path(config["paths"][company][country]['output']).resolve() / area_name
    output_folder.mkdir(parents=True, exist_ok=True)

    sec_file = output_folder / "sec_polygons.json"
    population_density_file = output_folder / "population_density.json"

    if sec_file.exists() and population_density_file.exists():
        print("From Disk: SEC & Population density Loaded & Saved Successfully !!!")
        # gracefully closing the script
        sys.exit()

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

     
    print("\n... ||= FINISHED =|| ...\n")
