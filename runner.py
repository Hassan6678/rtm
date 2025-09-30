import multiprocessing as mp
import subprocess
import sys
from pathlib import Path
import yaml

from mymodules.utils import replace_placeholders
from src.init_process import run_initialization, run_global_initialization


def run_rtm_analysis_wrapper(area_name: str, config: dict, logs_dir: Path):
    """
    Wrapper function for multiprocessing - runs RTM analysis only (no initialization).
    """
    # Update config for this specific area
    area_config = config.copy()
    area_config["analysis"]["area"] = area_name
    config_yaml = yaml.dump(area_config, default_flow_style=False)

    return run_rtm_analysis(config_yaml, area_name, logs_dir)


def run_rtm_analysis(config_yaml: str, area_name: str, logs_dir: Path):
    """
    Run RTM analysis for a specific area.
    
    Args:
        config_yaml: YAML configuration as string
        area_name: Name of the area to process
        logs_dir: Directory to save logs
    """
    print(f"\nStarting RTM analysis for {area_name.capitalize()}")
    
    with open(logs_dir / f"{area_name}_analysis_logs.txt", "w") as log_file:
        sub_process = subprocess.run(
            ["python", "rtm_analysis.py", config_yaml], 
            stdout=log_file, 
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
    
    print(f"Finished RTM analysis for {area_name.capitalize()}\n")
    return sub_process.returncode


def process_area(area_name: str, config: dict, logs_dir: Path):
    """
    Process a single area through initialization and analysis.
    
    Args:
        area_name: Name of the area to process
        config: Configuration dictionary
        logs_dir: Directory to save logs
    """
    try:
        # Update config for this specific area
        area_config = config.copy()
        area_config["analysis"]["area"] = area_name
        config_yaml = yaml.dump(area_config, default_flow_style=False)
        
        print(f"Processing area: {area_name}")
        
        # Step 1: Run initialization process
        print(f"Running initialization for {area_name}...")
        with open(logs_dir / f"{area_name}_init_logs.txt", "w") as log_file:
            # Capture initialization output
            import io
            from contextlib import redirect_stdout, redirect_stderr
            
            init_output = io.StringIO()
            with redirect_stdout(init_output), redirect_stderr(init_output):
                try:
                    run_initialization(config_yaml)
                    init_success = True
                except Exception as e:
                    print(f"Initialization failed for {area_name}: {e}", file=init_output)
                    init_success = False
            
            log_file.write(init_output.getvalue())
        
        if not init_success:
            print(f"Initialization failed for {area_name}, skipping analysis")
            return 1
        
        # Step 2: Run RTM analysis
        print(f"Running RTM analysis for {area_name}...")
        analysis_result = run_rtm_analysis(config_yaml, area_name, logs_dir)
        
        return analysis_result
        
    except Exception as e:
        print(f"Error processing area {area_name}: {e}")
        return 1


def main():
    """
    Main function to run RTM analysis with multiprocessing support.
    """
    # Load configuration
    with open("config.yaml", "r") as yf:
        config = yaml.safe_load(yf)
    
    # Replace placeholders in config paths
    company = config["analysis"]["company"]
    country = config["analysis"]["country"]
    config['paths'] = replace_placeholders(config['paths'], company, country)
    
    area_name = config["analysis"]["area"]
    
    # Create logs directory
    logs_dir = Path(config["paths"]["logs"]).resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Starting RTM process for {company.upper()} - {country.upper()}")
    print(f"Data directory: {config['paths']['data']}")
    print(f"Logs directory: {logs_dir}")
    
    if area_name == "all":
        # Process all areas - First run global initialization to create all boundary KMLs, SEC, customer data, and whitespace
        print("Running global initialization to create boundary KML files, process customer data, and generate whitespace...")

        try:
            init_success = run_global_initialization(config)

            if not init_success:
                print("Global initialization failed, cannot proceed")
                return

        except Exception as e:
            print(f"Error during global initialization: {e}")
            return

        print("Global initialization completed. Discovering areas...")

        # Now find all areas with boundary KML files that were just created
        data_directory = Path(config["paths"]['data'])
        exclude_cities = config["analysis"]["exclude"]

        areas = []
        for boundary_file in data_directory.glob("**/boundary.kml"):
            area_name = boundary_file.parent.parent.name
            if area_name not in exclude_cities:
                areas.append(area_name)

        print(f"Found {len(areas)} areas to process: {areas}")

        if not areas:
            print("No areas found to process after initialization")
            return

        # Use multiprocessing to process areas (analysis only, since init is done)
        max_processes = min(8, len(areas))
        print(f"Using {max_processes} processes for parallel analysis")

        with mp.Pool(processes=max_processes) as pool:
            # Create tasks for each area (analysis only)
            tasks = [(area, config, logs_dir) for area in areas]

            # Process areas in parallel
            results = pool.starmap(run_rtm_analysis_wrapper, tasks)

        # Report results
        successful = sum(1 for result in results if result == 0)
        failed = len(results) - successful

        print("\n=== Processing Complete ===")
        print(f"Successfully processed: {successful} areas")
        print(f"Failed: {failed} areas")
        
    else:
        # Process single area
        print(f"Processing single area: {area_name}")
        result = process_area(area_name, config, logs_dir)
        
        if result == 0:
            print(f"Successfully processed area: {area_name}")
        else:
            print(f"Failed to process area: {area_name}")


if __name__ == "__main__":
    main()
