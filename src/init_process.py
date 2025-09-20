
import json
import os
import random
import sys
from pathlib import Path
import yaml

import pandas as pd
import simplekml
from shapely.geometry import Polygon

from mymodules.utils import replace_placeholders
from mymodules.aisight.naqsha import SEC, Boundary
from mymodules.aisight.naqsha.utils import get_intersecting_polygons

# Import tessellation functions from local module
from tessellation import cluster_kmeans, voronoi_tesselation, post_adjustments, fuzzy_rename_columns

def make_kml_from_json(json_file: str, config: dict):
    """
    Create KML files from JSON polygon data for multi-tenant architecture.
    
    Args:
        json_file: Path to the JSON file containing polygon data
        config: Configuration dictionary with paths and settings
    """
    data = json.load(open(json_file))
    
    # Get the data directory from config
    data_dir = Path(config["paths"]["data"])
    
    for polygon in data:
        color = "%06x" % random.randint(0, 0xFFFFFF)
        color = f'99{color}'
        kml = simplekml.Kml()
        polyname = polygon['_id']
        folder = kml.newfolder(name=polyname)
        poly_cords = polygon['boundary']['coordinates']
        poly_cords = [tuple(x) for x in poly_cords[0]]
        poly_cords = tuple(poly_cords)
        
        if not Polygon(poly_cords).is_valid:
            poly_cords = Polygon(poly_cords).simplify(0.001).exterior.coords
        
        pol = folder.newpolygon(name=polygon['code'], outerboundaryis=poly_cords)
        
        if not Polygon(poly_cords).is_valid:
            print(f"Polygon {polygon['_id']} is not valid")
        
        pol.style.polystyle.color = color
        pol.style.polystyle.outline = 1
        pol.style.polystyle.fill = 1
        
        # Create area-specific directories using config-based paths
        area_id = polygon['_id']
        area_dir = data_dir / area_id
        
        # Create subdirectories
        for subdir in ['tifs', 'customers', 'kmls']:
            subdir_path = area_dir / subdir
            subdir_path.mkdir(parents=True, exist_ok=True)
            
        # Save KML file
        kml_path = area_dir / 'kmls' / 'boundary.kml'
        kml.save(str(kml_path))
        print(f"Created boundary KML for area: {area_id}")

def sec_extraction(sec_file: str, config: dict):
    """
    Extract SEC (Socio-Economic Classification) data and create KML files for each area.
    
    Args:
        sec_file: Path to the SEC file
        config: Configuration dictionary with paths and settings
    """
    sec = SEC(file=sec_file)
    data_dir = Path(config["paths"]["data"])
    
    # Find all boundary KML files in the data directory
    boundaries = list(data_dir.glob("*/kmls/boundary.kml"))
    print(f"Found {len(boundaries)} boundary files to process")

    def sec_kml(intersecting_polygons, kml):
        """Helper function to create SEC KML polygons"""
        # Create folders for different SEC categories
        folders = {
            'A': kml.newfolder(name='A'),
            'B': kml.newfolder(name='B'), 
            'C': kml.newfolder(name='C'),
            'D': kml.newfolder(name='D'),
            'E': kml.newfolder(name='E')
        }
        
        colors = {
            'A': simplekml.Color.lightgreen,
            'B': simplekml.Color.royalblue,
            'C': simplekml.Color.red,
            'D': simplekml.Color.yellow,
            'E': simplekml.Color.darkgreen
        }

        for poly in intersecting_polygons:
            try:
                poly_cords = tuple(poly.exterior.coords)
                
                if poly.x_folder in folders:
                    pol = folders[poly.x_folder].newpolygon(name='', outerboundaryis=poly_cords)
                    pol.style.polystyle.color = colors[poly.x_folder]
                    pol.style.polystyle.outline = 1
                    pol.style.polystyle.fill = 1
                else:
                    print(f"Unknown SEC category: {poly.x_folder}")
                    
            except Exception as ex:
                print(f"Error processing polygon: {ex}")

    # Process each boundary file
    for boundary_file in boundaries:
        try:
            kml = simplekml.Kml()
            
            # Load boundary and find intersecting SEC polygons
            boundary = Boundary(file=str(boundary_file))
            boundary_polygon = boundary._polygons[0]
            intersecting_polygons = get_intersecting_polygons(boundary_polygon, sec)
            
            # Create SEC KML
            sec_kml(intersecting_polygons, kml)
            
            # Extract area name from path
            area_name = boundary_file.parent.parent.name
            sec_kml_path = boundary_file.parent / 'sec.kml'
            kml.save(str(sec_kml_path))
            print(f"Created SEC KML for area: {area_name}")
            
        except Exception as ex:
            print(f"Error processing {boundary_file}: {ex}")

def census_customer_check(census_file: str, client_file: str, config: dict):
    """
    Process census and client data for each area in the multi-tenant architecture.
    
    Args:
        census_file: Path to the census data file
        client_file: Path to the client data file  
        config: Configuration dictionary with paths and settings
    """
    data_dir = Path(config["paths"]["data"])
    
    # Get all area IDs from the data directory
    area_ids = [d.name for d in data_dir.iterdir() if d.is_dir()]
    
    # Process census data
    if census_file and Path(census_file).exists():
        print(f"Processing census data from: {census_file}")
        master_df = pd.read_csv(census_file)
        master_df.rename(columns={'_id': 'customer_code', 'Lat': 'latitude', 'Lng': 'longitude'}, inplace=True)
        
        for area_id in area_ids:
            try:
                # Filter data for this area
                df = master_df[master_df.apply(lambda r: r.str.contains(area_id, case=False).any(), axis=1)]
                print(f"Area {area_id}: {df.shape[0]} census records")
                
                # Save to area-specific directory
                output_path = data_dir / area_id / 'customers' / 'census_customer.csv'
                df.to_csv(output_path, index=False)
                print(f"Saved census data for area: {area_id}")
                
            except Exception as ex:
                print(f"Error processing census data for area {area_id}: {ex}")
    
    # Process client data
    if client_file and Path(client_file).exists():
        print(f"Processing client data from: {client_file}")
        
        # Try to read as Excel first, then CSV
        try:
            master_df = pd.read_excel(client_file)
        except:
            master_df = pd.read_csv(client_file)
            
        master_df.rename(columns={'_id': 'customer_code'}, inplace=True)
        
        for area_id in area_ids:
            try:
                # Filter data for this area
                df = master_df[master_df.apply(lambda r: r.str.contains(area_id, case=False).any(), axis=1)]
                print(f"Area {area_id}: {df.shape[0]} client records")
                
                # Save to area-specific directory
                output_path = data_dir / area_id / 'customers' / 'input_customer.csv'
                df.to_csv(output_path, index=False)
                print(f"Saved client data for area: {area_id}")
                
            except Exception as ex:
                print(f"Error processing client data for area {area_id}: {ex}")
    
    print("Census and client data processing completed")

def generate_whitespace_tessellation(config: dict):
    """
    Generate whitespace KML files using tessellation based on census data and boundary files.
    
    Args:
        config: Configuration dictionary with paths and settings
    """
    data_dir = Path(config["paths"]["data"])
    
    # Find all areas with boundary KML files
    areas = []
    for area_dir in data_dir.iterdir():
        if area_dir.is_dir():
            boundary_file = area_dir / "kmls" / "boundary.kml"
            census_file = area_dir / "customers" / "census_customer.csv"
            
            if boundary_file.exists() and census_file.exists():
                areas.append({
                    'area_id': area_dir.name,
                    'boundary_file': boundary_file,
                    'census_file': census_file,
                    'whitespace_file': area_dir / "kmls" / "whitespace.kml"
                })
    
    print(f"Found {len(areas)} areas for whitespace tessellation")
    
    for area in areas:
        try:
            area_id = area['area_id']
            boundary_file = area['boundary_file']
            census_file = area['census_file']
            whitespace_file = area['whitespace_file']
            
            print(f"Processing tessellation for area: {area_id}")
            
            # Check if whitespace already exists
            if whitespace_file.exists():
                print(f"Whitespace KML already exists for {area_id}, skipping...")
                continue
            
            # Load boundary polygon
            from mymodules.aisight.naqsha import KMLReader
            kml_reader = KMLReader(file=str(boundary_file))
            boundary_poly = Polygon(kml_reader.data[0].coordinates)
            
            # Load census data
            customers_df = pd.read_csv(census_file)
            customers_df = fuzzy_rename_columns(customers_df)
            
            # Check if we have enough data for clustering
            if len(customers_df) < 3:
                print(f"Not enough census data for {area_id}, copying boundary as whitespace...")
                import shutil
                shutil.copy2(boundary_file, whitespace_file)
                continue
            
            if "longitude" not in customers_df.columns or "latitude" not in customers_df.columns:
                print(f"Missing coordinate columns for {area_id}, copying boundary as whitespace...")
                import shutil
                shutil.copy2(boundary_file, whitespace_file)
                continue
            
            # Perform clustering
            customers_df, centers_df = cluster_kmeans(df=customers_df, config={})
            
            # Generate tessellation
            polys, center_X = voronoi_tesselation(boundary=boundary_poly, centers_df=centers_df)
            
            # Post-process and save
            post_adjustments(
                polys=polys, 
                boundary_poly=boundary_poly, 
                center_X=center_X, 
                save_path=str(whitespace_file)
            )
            
            print(f"Generated whitespace KML for area: {area_id}")
            
        except Exception as ex:
            print(f"Error processing tessellation for area {area_id}: {ex}")
            # Fallback: copy boundary as whitespace
            try:
                import shutil
                shutil.copy2(boundary_file, whitespace_file)
                print(f"Created fallback whitespace for area: {area_id}")
            except:
                print(f"Failed to create fallback whitespace for area: {area_id}")
    
    print("Whitespace tessellation processing completed")


def main():
    """
    Main function to run the initialization process for RTM analysis.
    Supports multi-tenant architecture with configurable company and country.
    """
    # Load configuration
    with open("config.yaml", "r") as yf:
        config = yaml.safe_load(yf)
    
    # Replace placeholders in config paths
    company = config["analysis"]["company"]
    country = config["analysis"]["country"]
    config['paths'] = replace_placeholders(config['paths'], company, country)
    
    print(f"Initializing RTM process for {company.upper()} - {country.upper()}")
    print(f"Data directory: {config['paths']['data']}")
    print(f"Raw directory: {config['paths']['raw']}")
    
    # Get raw data directory
    raw_dir = Path(config["paths"]["raw"])
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    # Look for area JSON file in raw directory
    area_json_files = list(raw_dir.glob("*area*.json"))
    if area_json_files:
        area_json_file = area_json_files[0]  # Take the first one found
        print(f"Found area JSON file: {area_json_file}")
        
        # Step 1: Create KML files from JSON
        print("\n=== Step 1: Creating KML files from JSON ===")
        make_kml_from_json(str(area_json_file), config)
        
        # Step 2: Extract SEC data
        print("\n=== Step 2: Extracting SEC data ===")
        # Look for SEC file in raw directory
        sec_files = list(raw_dir.glob("*sec*.kml")) + list(raw_dir.glob("*SEC*.kml"))
        if sec_files:
            sec_file = sec_files[0]
            print(f"Found SEC file: {sec_file}")
            sec_extraction(str(sec_file), config)
        else:
            print("No SEC file found in raw directory")
        
        # Step 3: Process census and client data
        print("\n=== Step 3: Processing census and client data ===")
        # Look for census and client files
        census_files = list(raw_dir.glob("*census*.csv")) + list(raw_dir.glob("*CENSUS*.csv"))
        client_files = list(raw_dir.glob("*client*.xlsx")) + list(raw_dir.glob("*client*.csv"))
        
        census_file = census_files[0] if census_files else None
        client_file = client_files[0] if client_files else None
        
        if census_file:
            print(f"Found census file: {census_file}")
        if client_file:
            print(f"Found client file: {client_file}")
            
        census_customer_check(str(census_file) if census_file else None, 
                            str(client_file) if client_file else None, 
                            config)
        
        # Step 4: Generate whitespace tessellation
        print("\n=== Step 4: Generating whitespace tessellation ===")
        generate_whitespace_tessellation(config)
        
        print("\n=== Initialization completed successfully! ===")
        print("You can now run the main RTM analysis using: python runner.py")
        
    else:
        print("No area JSON file found in raw directory")
        print("Please ensure you have a file with 'area' in the name in the raw directory")

if __name__ == "__main__":
    main()