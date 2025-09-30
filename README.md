# RTM Data Preprocessing Pipeline

A comprehensive data preprocessing pipeline for Route-to-Market (RTM) analysis that transforms raw geographic and customer data into structured KML files and analysis-ready datasets.

## Overview

This project processes area boundary data, customer information, and census data to create a multi-tenant geospatial analysis framework. The pipeline generates KML files for boundaries, SEC (Socio-Economic Classification) polygons, and whitespace tessellation, enabling spatial analysis for retail territory optimization.

## Core Process Flow

### 1. Data Inputs
- **Area JSON file**: Contains polygon coordinates with MongoDB IDs and area metadata
- **Outlet/Client data**: Customer location data mapped to area MongoDB IDs
- **Census data**: Population data also mapped to area MongoDB IDs
- **SEC KML file**: Socio-economic classification polygons

### 2. Directory Structure Generated
```
projects/{company}/{country}/data/{area_id}/
├── customers/
│   ├── census_customer.csv      # Filtered census data for the area
│   └── input_customer.csv       # Filtered outlet/client data for the area
├── kmls/
│   ├── boundary.kml            # Area boundary polygons
│   ├── sec.kml                 # SEC classification polygons
│   └── whitespace.kml          # Tessellated whitespace polygons
└── tifs/
    └── population.tif          # Population density TIFF files
```

### 3. Processing Steps

#### Global Initialization (Batch Processing)
When processing multiple areas, initialization runs once for efficiency:

**Step 1: Boundary KML Generation**
- Converts area JSON data to individual boundary.kml files for all areas
- Creates area-specific directory structure (`projects/{company}/{country}/data/{area_id}/`)
- Validates polygon geometry and fixes invalid polygons

**Step 2: SEC Data Extraction**
- Intersects SEC polygons with all area boundaries at once
- Categorizes SEC data into A, B, C, D, E classes
- Generates sec.kml files with color-coded polygons for all areas
- **Manual Intervention Required**: If no SEC polygons intersect a boundary, manually create sec.kml in Google Earth

**Step 3: Customer Data Processing**
- Filters census and client data by area MongoDB IDs for all areas
- Maps customer locations to specific areas
- Generates area-specific CSV files in `customers/` subdirectories

**Step 4: Whitespace Tessellation**
- Uses Voronoi tessellation based on census data points for all areas
- Generates whitespace polygons within boundaries
- Falls back to boundary copy if insufficient census data

#### Parallel Analysis
After global initialization, RTM analysis runs concurrently for each area using the processed data.

## TIFF Population Data Handling

### Extraction Constraints
- **Minimum Area**: TIFF extraction fails if boundary area < 1 km²
- **Complete Coverage**: Boundary must entirely encompass the TIFF box

### Solutions for Failed Extractions
1. **Parent Boundary Fallback**: Use parent population.tif (parents are always > 1 km²)
2. **Manual Boundary Adjustment**: Modify boundary in Google Earth until area > 1 km², then extract

## Usage

### Configuration
Update `config.yaml` with:
```yaml
analysis:
  company: your_company
  country: your_country
  area: "all"  # or specific area MongoDB ID
```

### Running the Pipeline

#### Process All Areas (Recommended)
When `area: "all"` in config.yaml:
1. **Global Initialization**: Creates all boundary KMLs, processes customer data, generates whitespace tessellation
2. **Parallel Analysis**: Runs RTM analysis for each area concurrently
```bash
python runner.py
```

#### Process Specific Area
Set `area` in config.yaml to the specific MongoDB ID:
```bash
python runner.py
```

### Manual Initialization (Advanced)
For custom workflows, you can run initialization separately:
```python
from src.init_process import run_global_initialization
run_global_initialization(config_dict)
```

## Key Components

### `runner.py`
- Main orchestration script with efficient multiprocessing support
- Runs global initialization once for all areas (KML creation, data processing, tessellation)
- Handles parallel RTM analysis for individual areas
- Manages logging and error handling

### `src/init_process.py`
- Data preprocessing and KML generation
- SEC extraction and tessellation
- Customer data filtering

### `rtm_analysis.py`
- Spatial analysis using processed data
- Population density calculations
- Whitespace analysis with SEC integration

### `src/tessellation.py`
- Voronoi tessellation algorithms
- K-means clustering for whitespace generation
- Polygon validation and processing

## Dependencies

- pandas
- numpy
- shapely
- simplekml
- pyyaml
- scipy
- scikit-learn
- gdal

## Multi-Tenant Architecture

The pipeline supports multiple companies and countries through:
- Placeholder-based path configuration
- Area-specific data isolation
- Configurable exclusion lists
- Parallel processing across areas

## Manual Interventions Required

1. **SEC KML Creation**: When no SEC polygons intersect boundaries
2. **Boundary Adjustment**: For areas < 1 km² requiring TIFF extraction
3. **Data Validation**: Manual review of generated KML files in Google Earth

## Output Artifacts

- **boundary.kml**: Geographic boundaries for each area
- **sec.kml**: Socio-economic classification polygons
- **whitespace.kml**: Tessellated polygons for analysis
- **population_density.json**: Population data per pixel
- **whitespace_data.json**: Analysis-ready whitespace information
- **sec_polygons.json**: SEC polygon metadata
