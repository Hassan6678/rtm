from configparser import ConfigParser
from pathlib import Path
import subprocess, sys
# import json, pickle
from mymodules.utils import *

import yaml


# base directory
BASE_DIR = Path(__file__).parent.resolve()

with open("config.yaml", "r") as yf:
    config = yaml.safe_load(yf)

# just to add collect script available on path
# sys.path.append(Path(config["paths"]["mymodules"]).resolve())
# from mymodules.myscripts import collect

# reading config from yaml
company = config["analysis"]["company"]
country = config["analysis"]["country"]
area_name = config["analysis"]["area"]

config['paths'] = replace_placeholders(config['paths'], company, country)

# logs folder
logs_dir = Path(config["paths"][company][country]["logs"]).resolve()
logs_dir.mkdir(parents=True, exist_ok=True)

if area_name == "all":
    data_directory = Path(config["paths"][company][country]['data'])
    exclude_cities = config["analysis"]["exclude"]

    for _id in data_directory.glob("**/boundary.kml"):
        area_name = _id.parent.parent.name

        if area_name in exclude_cities:
            continue
        # changing this, because this config will be passed to subprocess
        config["analysis"]["area"] = area_name
        
        config_yaml = yaml.dump(config, default_flow_style=False)

        # starting a subprocess to run the stockouts
        print(area_name)
        print(f"\nStarting analysis for {area_name.capitalize()}")

        with open(logs_dir/f"{area_name}_logs.txt", "w") as log_file:
            sub_process = subprocess.run(["python", "rtm_analysis.py", config_yaml], stdout=log_file, universal_newlines=True)

        print(f"Finished analysis for {area_name.capitalize()}\n")
else: 
    data_directory = Path(config["paths"][company][country]['data'])

    config_yaml = yaml.dump(config, default_flow_style=False)

    # starting a subprocess to run the stockouts
    print(f"\nStarting analysis for {area_name.capitalize()}")

    with open(logs_dir/f"{area_name}_logs.txt", "w") as log_file:
        sub_process = subprocess.run(["python", "rtm_analysis.py", config_yaml], stdout=log_file, universal_newlines=True)

    print(f"Finished analysis for {area_name.capitalize()}\n")
