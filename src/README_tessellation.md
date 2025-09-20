# Tessellation Module

This module provides tessellation functionality for generating whitespace KML files using Voronoi tessellation based on census data.

## Functions

### Clustering Functions
- `cluster_kmeans(df, config)`: Cluster data using K-means algorithm
- `cluster_hdbscan(df, config)`: Cluster data using HDBSCAN algorithm  
- `no_clusters(df, config)`: Use each point as its own cluster

### Tessellation Functions
- `voronoi_tesselation(centers_df, boundary)`: Generate Voronoi tessellation
- `post_adjustments(polys, boundary_poly, center_X, save_path)`: Post-process and save polygons

### Utility Functions
- `fuzzy_rename_columns(df)`: Standardize column names (lat/lng -> latitude/longitude)
- `get_random_points_on_shapely_polygon(polygon, num_points)`: Generate random boundary points
- `to_kml(geoms, save_path)`: Convert geometry list to KML format
- `print_my_traceback(tb_config)`: Custom traceback for debugging

## Usage

The tessellation module is automatically used by `init_process.py` in Step 4 of the RTM pipeline to generate whitespace KML files for each area based on census data and boundary files.

## Dependencies

- pandas
- numpy
- scipy
- scikit-learn
- shapely
- pathlib
