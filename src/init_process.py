
import json
import random
import sys
from pathlib import Path
import shutil
import yaml
import multiprocessing as mp

import pandas as pd
import simplekml
from shapely.geometry import Polygon

from mymodules.utils import replace_placeholders
from mymodules.aisight.naqsha import SEC, Boundary, KMLReader
from mymodules.aisight.naqsha.utils import get_intersecting_polygons
from mymodules.aisight.naqsha.polygons.tif.optimized_population_tif import extract_tif_for_areas

from .tessellation import cluster_kmeans, voronoi_tesselation, post_adjustments, fuzzy_rename_columns

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
    This is the legacy sequential version for backward compatibility.
    
    Args:
        sec_file: Path to the SEC file
        config: Configuration dictionary with paths and settings
    """
    sec = SEC(file=sec_file)
    data_dir = Path(config["paths"]["data"])
    
    # Find all boundary KML files in the data directory
    boundaries = list(data_dir.glob("*/kmls/boundary.kml"))
    print(f"Found {len(boundaries)} boundary files to process")

    # Process each boundary file
    for boundary_file in boundaries:
        try:
            # Use the same logic as the multiprocessing version
            success, area_name = process_single_area_sec(boundary_file, sec, data_dir)
            if not success:
                print(f"Failed to process SEC for area: {area_name}")
            
        except Exception as ex:
            area_name = boundary_file.parent.parent.name
            print(f"Error processing {boundary_file}: {ex}")

def census_customer_check(census_file: str, client_file: str, config: dict):
    """
    Process census and client data for each area in the multi-tenant architecture.
    This is the legacy sequential version for backward compatibility.
    
    Args:
        census_file: Path to the census data file
        client_file: Path to the client data file  
        config: Configuration dictionary with paths and settings
    """
    data_dir = Path(config["paths"]["data"])
    
    # Get all area IDs from the data directory
    area_ids = [d.name for d in data_dir.iterdir() if d.is_dir()]
    
    print(f"Processing census and client data for {len(area_ids)} areas...")
    
    # Process each area using the multiprocessing function logic
    for area_id in area_ids:
        try:
            success, processed_area_id, results = process_single_area_census_client(
                area_id, census_file, client_file, data_dir
            )
            if not success:
                print(f"Failed to process census/client data for area: {processed_area_id}")
        except Exception as ex:
            print(f"Error processing census/client data for area {area_id}: {ex}")
    
    print("Census and client data processing completed")

def generate_whitespace_tessellation(config: dict):
    """
    Generate whitespace KML files using tessellation based on census data and boundary files.
    This is the legacy sequential version for backward compatibility.
    
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
    
    # Process each area using the multiprocessing function logic
    for area in areas:
        try:
            success, area_id = process_single_area_whitespace(area)
            if not success:
                print(f"Failed to process whitespace tessellation for area: {area_id}")
                
        except Exception as ex:
            area_id = area['area_id']
            print(f"Error processing tessellation for area {area_id}: {ex}")
    
    print("Whitespace tessellation processing completed")


def process_tif_extraction(config: dict):
    """
    Extract TIF data for all areas using optimized processing.
    This function handles large TIF files by extracting only relevant portions.
    
    Args:
        config: Configuration dictionary with paths and settings
    """
    data_dir = Path(config["paths"]["data"])
    
    # Get global TIF file path from config
    global_tif_path = config["paths"].get("global_tif")
    
    if not global_tif_path:
        print("No global TIF file path specified in config")
        return False
    
    global_tif_path = Path(global_tif_path)
    
    if not global_tif_path.exists():
        print(f"Global TIF file not found: {global_tif_path}")
        return False
    
    print(f"Using global TIF file: {global_tif_path}")
    
    # Get all area IDs
    area_ids = [d.name for d in data_dir.iterdir() if d.is_dir()]
    
    if not area_ids:
        print("No areas found for TIF extraction")
        return False
    
    print(f"Processing TIF extraction for {len(area_ids)} areas")
    
    # Collect boundary file paths for all areas (use GDAL cutline for exact clipping)
    area_cutlines = {}
    for area_id in area_ids:
        boundary_file = data_dir / area_id / "kmls" / "boundary.kml"
        if boundary_file.exists():
            try:
                # Keep file path; optimized extractor will use cutline for precise mask
                area_cutlines[area_id] = boundary_file
                print(f"Registered boundary for area: {area_id}")
            except Exception as e:
                print(f"Error loading boundary for area {area_id}: {e}")
        else:
            print(f"Boundary file not found for area: {area_id}")
    
    if not area_cutlines:
        print("No valid boundaries found for TIF extraction")
        return False
    
    # Get TIF processing parameters from config
    tif_scale = config.get("geo", {}).get("tif", {}).get("scale", 1.0)
    buffer_degrees = config.get("geo", {}).get("tif", {}).get("buffer_degrees", 0.01)
    
    print(f"TIF scale: {tif_scale}, Buffer: {buffer_degrees} degrees")
    
    # Extract TIF data for all areas
    results = extract_tif_for_areas(
        global_tif_path=global_tif_path,
        area_cutlines=area_cutlines,
        output_base_dir=data_dir,
        scale=tif_scale,
        buffer_degrees=buffer_degrees
    )
    
    # Report results
    successful = sum(1 for success in results.values() if success)
    failed = len(results) - successful
    
    print(f"\nTIF extraction completed:")
    print(f"✅ Successful: {successful} areas")
    print(f"❌ Failed: {failed} areas")
    
    if failed > 0:
        failed_areas = [area_id for area_id, success in results.items() if not success]
        print(f"Failed areas: {failed_areas}")
    
    return successful > 0


def process_single_area_sec(boundary_file: Path, sec: SEC, data_dir: Path):
    """
    Process SEC extraction for a single area (for multiprocessing).
    
    Args:
        boundary_file: Path to the boundary KML file
        sec: SEC object with polygon data
        data_dir: Data directory path
    """
    try:
        kml = simplekml.Kml()
        
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

        # Load boundary and find intersecting SEC polygons
        boundary = Boundary(file=str(boundary_file))
        boundary_polygon = boundary._polygons[0]
        intersecting_polygons = get_intersecting_polygons(boundary_polygon, sec)
        
        # Create SEC KML polygons
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

        # Save SEC KML
        sec_kml_path = boundary_file.parent / 'sec.kml'
        kml.save(str(sec_kml_path))
        
        area_name = boundary_file.parent.parent.name
        print(f"Created SEC KML for area: {area_name}")
        return True, area_name
        
    except Exception as ex:
        area_name = boundary_file.parent.parent.name
        print(f"Error processing SEC for {area_name}: {ex}")
        return False, area_name

def process_single_area_census_client(area_id: str, census_file: str, client_file: str, data_dir: Path):
    """
    Process census and client data for a single area (for multiprocessing).
    
    Args:
        area_id: Area identifier
        census_file: Path to census file
        client_file: Path to client file
        data_dir: Data directory path
    """
    try:
        results = []
        
        # Process census data
        if census_file and Path(census_file).exists():
            # Try to read as Excel first, then CSV
            try:
                master_df = pd.read_excel(census_file)
            except Exception:
                master_df = pd.read_csv(census_file)

            master_df.rename(columns={'_id': 'customer_code', 'Lat': 'latitude', 'Lng': 'longitude'}, inplace=True)
            
            # Filter data for this area
            df = master_df[master_df.apply(lambda r: r.str.contains(area_id, case=False).any(), axis=1)]
            print(f"Area {area_id}: {df.shape[0]} census records")
            
            # Save to area-specific directory
            output_path = data_dir / area_id / 'customers' / 'census_customer.csv'
            output_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(output_path, index=False)
            print(f"Saved census data for area: {area_id}")
            results.append(("census", True, df.shape[0]))
        else:
            results.append(("census", False, 0))
        
        # Process client data
        if client_file and Path(client_file).exists():
            # Try to read as Excel first, then CSV
            try:
                master_df = pd.read_excel(client_file)
            except Exception:
                master_df = pd.read_csv(client_file)
                
            master_df.rename(columns={'_id': 'customer_code', 'Lat': 'latitude', 'Lng': 'longitude'}, inplace=True)
            
            # Filter data for this area
            df = master_df[master_df.apply(lambda r: r.str.contains(area_id, case=False).any(), axis=1)]
            print(f"Area {area_id}: {df.shape[0]} client records")
            
            # Save to area-specific directory
            output_path = data_dir / area_id / 'customers' / 'input_customer.csv'
            output_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(output_path, index=False)
            print(f"Saved client data for area: {area_id}")
            results.append(("client", True, df.shape[0]))
        else:
            results.append(("client", False, 0))
        
        return True, area_id, results
        
    except Exception as ex:
        print(f"Error processing census/client data for area {area_id}: {ex}")
        return False, area_id, []


def process_single_area_whitespace(area_data: dict):
    """
    Process whitespace tessellation for a single area (for multiprocessing).
    
    Args:
        area_data: Dictionary containing area information
    """
    try:
        area_id = area_data['area_id']
        boundary_file = area_data['boundary_file']
        census_file = area_data['census_file']
        whitespace_file = area_data['whitespace_file']

        print(f"Processing tessellation for area: {area_id}")

        # Check if whitespace already exists
        if whitespace_file.exists():
            print(f"Whitespace KML already exists for {area_id}, skipping...")
            return True, area_id

        # Load boundary polygon
        kml_reader = KMLReader(file=str(boundary_file))
        boundary_poly = Polygon(kml_reader.data[0].coordinates)

        # Load census data
        customers_df = pd.read_csv(census_file)
        customers_df = fuzzy_rename_columns(customers_df)

        # Check if we have enough data for clustering
        if len(customers_df) < 3:
            print(f"Not enough census data for {area_id}, copying boundary as whitespace...")
            shutil.copy2(boundary_file, whitespace_file)
            return True, area_id

        if "longitude" not in customers_df.columns or "latitude" not in customers_df.columns:
            print(f"Missing coordinate columns for {area_id}, copying boundary as whitespace...")
            shutil.copy2(boundary_file, whitespace_file)
            return True, area_id

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
        return True, area_id

    except Exception as ex:
        print(f"Error processing tessellation for area {area_id}: {ex}")
        # Fallback: copy boundary as whitespace
        try:
            shutil.copy2(boundary_file, whitespace_file)
            print(f"Created fallback whitespace for area: {area_id}")
            return True, area_id
        except Exception:
            print(f"Failed to create fallback whitespace for area: {area_id}")
            return False, area_id


def run_initialization(config_yaml: str):
    """
    Run the complete initialization process for RTM analysis.
    This function can be called from multiprocessing or for global initialization.

    Args:
        config_yaml: YAML configuration as string
    """
    # Parse configuration
    config = yaml.safe_load(config_yaml)

    # Replace placeholders in config paths
    company = config["analysis"]["company"]
    country = config["analysis"]["country"]
    config['paths'] = replace_placeholders(config['paths'], company, country)

    area_name = config["analysis"]["area"]

    print(f"Initializing RTM process for {company.upper()} - {country.upper()} - Area: {area_name}")
    print(f"Data directory: {config['paths']['data']}")
    print(f"Raw directory: {config['paths']['raw']}")

    try:
        # Get raw data directory
        raw_dir = Path(config["paths"]["raw"])
        raw_dir.mkdir(parents=True, exist_ok=True)

        # Look for area JSON file in raw directory
        area_json_files = list(raw_dir.glob("*area*.json"))
        if not area_json_files:
            print(f"No area JSON file found in raw directory for {area_name}")
            return

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

        # Step 1.5: Extract TIF data for area (optimized)
        print("\n=== Step 1.5: Extracting TIF data for area (optimized) ===")
        tif_success = process_tif_extraction(config)
        if not tif_success:
            print("Warning: TIF extraction failed, continuing with other steps...")

        # Step 3: Process census and client data
        print("\n=== Step 3: Processing census and client data ===")
        # Look for census and client files
        census_files = list(raw_dir.glob("*census*.xlsx")) + list(raw_dir.glob("*census*.csv"))
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
        if area_name == "all":
            print("All areas are ready for RTM analysis")
        else:
            print(f"Area {area_name} is ready for RTM analysis")

    except Exception as e:
        print(f"Error during initialization for {area_name}: {e}")
        raise


def run_global_initialization(config: dict):
    """
    Run initialization for all areas at once with multiprocessing support.

    Args:
        config: Configuration dictionary
    """
    company = config["analysis"]["company"]
    country = config["analysis"]["country"]

    print(f"Running global initialization for {company.upper()} - {country.upper()}")
    print(f"Data directory: {config['paths']['data']}")
    print(f"Raw directory: {config['paths']['raw']}")

    try:
        # Get raw data directory
        raw_dir = Path(config["paths"]["raw"])
        raw_dir.mkdir(parents=True, exist_ok=True)
        data_dir = Path(config["paths"]["data"])

        # Look for area JSON file in raw directory
        area_json_files = list(raw_dir.glob("*area*.json"))
        if not area_json_files:
            print("No area JSON file found in raw directory")
            return False

        area_json_file = area_json_files[0]  # Take the first one found
        print(f"Found area JSON file: {area_json_file}")

        # Step 1: Create KML files from JSON for all areas
        print("\n=== Step 1: Creating KML files from JSON for all areas ===")
        make_kml_from_json(str(area_json_file), config)

        # Get all area IDs after KML creation
        area_ids = [d.name for d in data_dir.iterdir() if d.is_dir()]
        print(f"Found {len(area_ids)} areas to process: {area_ids}")

        if not area_ids:
            print("No areas found after KML creation")
            return False

        # Step 1.5: Extract TIF data for all areas (optimized for large files)
        print("\n=== Step 1.5: Extracting TIF data for all areas (optimized) ===")
        tif_success = process_tif_extraction(config)
        if not tif_success:
            print("Warning: TIF extraction failed, continuing with other steps...")

        # Determine number of processes (use config value or default to 8, but not more than number of areas)
        max_processes_config = config.get("process", {}).get("max_processes", 8)
        max_processes = min(max_processes_config, len(area_ids))
        print(f"Using {max_processes} processes for parallel processing")

        # Step 2: Extract SEC data for all areas (parallel)
        print("\n=== Step 2: Extracting SEC data for all areas (parallel) ===")
        sec_files = list(raw_dir.glob("*sec*.kml")) + list(raw_dir.glob("*SEC*.kml"))
        if sec_files:
            sec_file = sec_files[0]
            print(f"Found SEC file: {sec_file}")
            
            # Load SEC data once
            sec = SEC(file=str(sec_file))
            
            # Find all boundary files
            boundary_files = [data_dir / area_id / "kmls" / "boundary.kml" for area_id in area_ids]
            boundary_files = [bf for bf in boundary_files if bf.exists()]
            
            if boundary_files:
                # Process SEC extraction in parallel
                print(f"Processing SEC extraction for {len(boundary_files)} areas...")
                with mp.Pool(processes=max_processes) as pool:
                    sec_tasks = [(bf, sec, data_dir) for bf in boundary_files]
                    sec_results = pool.starmap(process_single_area_sec, sec_tasks)
                
                # Report SEC results
                sec_successful = sum(1 for success, _ in sec_results if success)
                sec_failed = len(sec_results) - sec_successful
                print(f"SEC extraction completed: {sec_successful}/{len(sec_results)} areas successful")
                if sec_failed > 0:
                    failed_areas = [area for success, area in sec_results if not success]
                    print(f"Failed areas: {failed_areas}")
            else:
                print("No boundary files found for SEC extraction")
        else:
            print("No SEC file found in raw directory")

        # Step 3: Process census and client data for all areas (parallel)
        print("\n=== Step 3: Processing census and client data for all areas (parallel) ===")
        census_files = list(raw_dir.glob("*census*.xlsx")) + list(raw_dir.glob("*census*.csv"))
        client_files = list(raw_dir.glob("*client*.xlsx")) + list(raw_dir.glob("*client*.csv"))

        census_file = str(census_files[0]) if census_files else None
        client_file = str(client_files[0]) if client_files else None

        if census_file:
            print(f"Found census file: {census_file}")
        if client_file:
            print(f"Found client file: {client_file}")

        # Process census and client data in parallel
        print(f"Processing census and client data for {len(area_ids)} areas...")
        with mp.Pool(processes=max_processes) as pool:
            census_client_tasks = [(area_id, census_file, client_file, data_dir) for area_id in area_ids]
            census_client_results = pool.starmap(process_single_area_census_client, census_client_tasks)
        
        # Report census/client results
        census_client_successful = sum(1 for success, _, _ in census_client_results if success)
        census_client_failed = len(census_client_results) - census_client_successful
        print(f"Census/client processing completed: {census_client_successful}/{len(census_client_results)} areas successful")
        if census_client_failed > 0:
            failed_areas = [area for success, area, _ in census_client_results if not success]
            print(f"Failed areas: {failed_areas}")

        # Step 4: Generate whitespace tessellation for all areas (parallel)
        print("\n=== Step 4: Generating whitespace tessellation for all areas (parallel) ===")
        
        # Prepare area data for whitespace processing
        areas_data = []
        for area_id in area_ids:
            boundary_file = data_dir / area_id / "kmls" / "boundary.kml"
            census_file = data_dir / area_id / "customers" / "census_customer.csv"
            whitespace_file = data_dir / area_id / "kmls" / "whitespace.kml"
            
            if boundary_file.exists() and census_file.exists():
                areas_data.append({
                    'area_id': area_id,
                    'boundary_file': boundary_file,
                    'census_file': census_file,
                    'whitespace_file': whitespace_file
                })
        
        if areas_data:
            # Process whitespace tessellation in parallel
            print(f"Processing whitespace tessellation for {len(areas_data)} areas...")
            with mp.Pool(processes=max_processes) as pool:
                whitespace_results = pool.map(process_single_area_whitespace, areas_data)
            
            # Report whitespace results
            whitespace_successful = sum(1 for success, _ in whitespace_results if success)
            whitespace_failed = len(whitespace_results) - whitespace_successful
            print(f"Whitespace tessellation completed: {whitespace_successful}/{len(whitespace_results)} areas successful")
            if whitespace_failed > 0:
                failed_areas = [area for success, area in whitespace_results if not success]
                print(f"Failed areas: {failed_areas}")
        else:
            print("No areas found with required files for whitespace tessellation")

        print("\n=== Global initialization completed successfully! ===")
        return True

    except Exception as e:
        print(f"Error during global initialization: {e}")
        return False