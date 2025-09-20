"""
Tessellation module for generating whitespace KML files using Voronoi tessellation.
This module provides clustering and tessellation functionality for RTM analysis.
"""

import random
import sys
import traceback
from pathlib import Path

import pandas as pd
import numpy as np
from scipy.spatial import Voronoi
import shapely.validation
from sklearn.cluster import HDBSCAN, KMeans
import shapely
from shapely.geometry import Polygon, Point, LineString, MultiPolygon, MultiLineString
import shapely.ops


def fuzzy_rename_columns(df):
    """Rename columns to standardize longitude/latitude naming."""
    # lower and strip the column names
    df.columns = df.columns.map(lambda x: x.lower().strip())

    if not ("longitude" in df.columns or "latitude" in df.columns):
        # change the following columns
        possible_renaming: dict = {"lat": "latitude", "lng": "longitude", "long": "longitude"}
        df.rename(columns=possible_renaming, inplace=True)
    return df


def get_random_points_on_shapely_polygon(polygon, num_points):
    """
    Generates random points on the boundary (edges) of a Shapely Polygon.

    Args:
        polygon (shapely.geometry.Polygon): The input Shapely Polygon object.
        num_points (int): The number of random points to generate.

    Returns:
        list of tuples: A list of (x, y) coordinates of the generated random points.
                        Returns an empty list if num_points is 0 or polygon is invalid.
    """
    if not isinstance(polygon, Polygon):
        raise TypeError("Input 'polygon' must be a shapely.geometry.Polygon object.")
    if num_points <= 0:
        return []

    # Get the boundary of the polygon as a LineString (or MultiLineString if there are holes)
    boundary_line = polygon.exterior  # For the outer boundary

    if boundary_line.length == 0:
        # Handles cases like a point-like polygon or line-like polygon
        if polygon.is_empty:
            return []
        # If it's a point, and length is 0, return that point if num_points > 0
        if polygon.area == 0 and isinstance(polygon.exterior, LineString) and len(polygon.exterior.coords) > 0:
            return [polygon.exterior.coords[0]] * num_points  # Return the single point multiple times

    points_on_polygon_boundary = []

    for _ in range(num_points):
        # Generate a random distance along the boundary's length
        random_distance = random.uniform(0, boundary_line.length)

        # Use .interpolate() to get the Point object at that distance
        point_on_boundary = boundary_line.interpolate(random_distance, normalized=False)

        # Extract the (x, y) coordinates from the Point object
        points_on_polygon_boundary.append((point_on_boundary.x, point_on_boundary.y))

    return points_on_polygon_boundary


def cluster_hdbscan(df: pd.DataFrame, config: dict = {}) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cluster data using HDBSCAN algorithm."""
    X = df[["longitude", "latitude"]].values

    hdb = HDBSCAN(min_cluster_size=3, metric="minkowski", metric_params={"p": 2}, n_jobs=-1)
    hdb.fit(X)

    df["cluster"] = hdb.labels_

    unique_labels = set(df.cluster.values)
    unique_labels.discard(-1)

    print("Total Number of Clusters After Discarding -1 Clusters ", len(unique_labels))

    # Calculate the "center" (centroid) for each cluster
    cluster_centers = {}
    for label in unique_labels:
        cluster_points = df.query("cluster == @label")
        if len(cluster_points) > 0:
            center = tuple(np.mean(cluster_points[["longitude", "latitude"]], axis=0))
            cluster_centers[label] = center

    centers_df = pd.DataFrame(cluster_centers.values(), columns=["longitude", "latitude"])
    return df, centers_df


def cluster_kmeans(df: pd.DataFrame, config: dict = {}) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cluster data using K-means algorithm."""
    X = df[["longitude", "latitude"]].values
    n_clusters = len(df) // 10

    kmeans = KMeans(n_clusters=n_clusters)
    kmeans.fit(X)

    df["cluster"] = kmeans.labels_
    centers_df = pd.DataFrame(kmeans.cluster_centers_, columns=["longitude", "latitude"])

    return df, centers_df


def no_clusters(df: pd.DataFrame, config: dict = {}):
    """No clustering - use each point as its own cluster."""
    df = df.dropna(subset=["longitude", "latitude"]).drop_duplicates(subset=["longitude", "latitude"])
    df["cluster"] = range(len(df))

    centers_df = df[["longitude", "latitude"]].copy()

    return df, centers_df


def voronoi_tesselation(centers_df: pd.DataFrame, boundary: Polygon):
    """Generate Voronoi tessellation based on cluster centers and boundary."""
    # Getting boundary points using envelope function with buffer
    bound = boundary.buffer(2.0).envelope.boundary
    num_boundarypoints = max(7500, int(len(centers_df) * 2))
    boundarypoints = [bound.interpolate(d) for d in np.linspace(0, bound.length, num_boundarypoints)]
    boundarycoords = np.array([[p.x, p.y] for p in boundarypoints])

    center_X = centers_df[["longitude", "latitude"]].values
    boundary_X = boundarycoords

    vor_X = np.concatenate([boundary_X, center_X])
    vor = Voronoi(vor_X)
    lines = [LineString(vor.vertices[line]) for line in vor.ridge_vertices if -1 not in line]
    polys = list(shapely.ops.polygonize(lines))
    return polys, center_X


def post_adjustments(polys: list, boundary_poly: Polygon, center_X, save_path):
    """Post-process tessellation polygons and save to KML."""
    # Polygons inside the boundary
    f_polys = []
    for p in polys:
        r_poly = boundary_poly.intersection(p)
        if not r_poly.is_empty:
            f_polys.append(r_poly)

    # 1st Pass
    total_multi_polygons = 0
    final_polygons = []
    have_to_adjust = []

    while f_polys:
        p = f_polys.pop()

        if isinstance(p, Polygon):
            final_polygons.append(p)
        elif isinstance(p, MultiPolygon):
            total_multi_polygons += 1
            acluster_point = None
            polygon_with_center = None
            center_found = False

            for sub_poly in p.geoms:
                if not center_found:
                    for c in center_X:
                        c_point = Point(*c)
                        if sub_poly.intersects(c_point):
                            acluster_point = c_point
                            polygon_with_center = sub_poly
                            center_found = True

                    if not center_found:
                        have_to_adjust.append(sub_poly)
                    else:
                        final_polygons.append(sub_poly)
                else:
                    have_to_adjust.append(sub_poly)
    
    print("Total MultiPolygons Found: ", total_multi_polygons)
    print(f"BEFORE: Total Full Polygon: {len(final_polygons)} || Have To Adjust Polygons: {len(have_to_adjust)}")

    # 2nd & Final Pass
    while have_to_adjust:
        to_adjust_poly = have_to_adjust.pop()

        for indx, fp in enumerate(final_polygons):
            if type(fp.intersection(to_adjust_poly)) in [LineString]:
                new_fp = fp.union(to_adjust_poly)
                final_polygons[indx] = new_fp
                break

        for indx, hp in enumerate(have_to_adjust):
            if type(hp.intersection(to_adjust_poly)) in [LineString]:
                new_hp = hp.union(to_adjust_poly)
                have_to_adjust[indx] = new_hp
                break

    print(f"AFTER: Total Full Polygon: {len(final_polygons)} || Have To Adjust Polygons: {len(have_to_adjust)}")

    # check if any multipolygon
    if [tp for tp in final_polygons if isinstance(tp, MultiPolygon)]:
        print("Why multipolygon is occuring at this level ?")

    # Write to KML
    to_kml(final_polygons, save_path=save_path)


def to_kml(geoms: list, save_path):
    """Convert geometry list to KML format and save to file."""
    get_final_kml = lambda d, name: f"""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2" xmlns:kml="http://www.opengis.net/kml/2.2" xmlns:atom="http://www.w3.org/2005/Atom">
    <Document>
        <name>{name}</name>
        {d}
    </Document>
    </kml>"""

    def get_extended_data(d: dict):
        extended_data_points = []
        for k, v in d.items():
            extended_data_points.append(f"""
                        <Data name="{k}">
                        <value>{v}</value>""")
        
        extended_data_string = "".join(extended_data_points)
        return f"""
                    <ExtendedData>{extended_data_string}
                    </ExtendedData>"""

    get_point_representation = (
        lambda p, n="": f"""
                <Placemark>
                    <name>{n}</name>
                    <description></description>
                    <Point>
                        <coordinates>{p}</coordinates>
                    </Point>
                </Placemark>
    """
    )

    get_polygon_representation = (
        lambda c, n="": f"""
                <Placemark>
                    <name>{n}</name>
                    <description></description>
                    <Polygon>
                        <outerBoundaryIs>
                            <LinearRing>
                                <coordinates>{c}</coordinates>
                            </LinearRing>
                        </outerBoundaryIs>   
                    </Polygon>
                </Placemark>
    """
    )

    get_folder_representation = lambda name, geoms: f"""
        <Folder>
            <name>{name}</name>
            <description></description>
            {geoms}
        </Folder>
    """

    pp_reprs = []
    for indx, pp in enumerate(geoms):
        coords_str = ""
        for lng, lat in pp.exterior.coords:
            coords_str += f"{lng},{lat},0.0 "

        coords_str = coords_str.strip()
        pp_repr = get_polygon_representation(c=coords_str, n=indx)
        pp_reprs.append(pp_repr)

    final_polygons = "".join(pp_reprs).strip()
    folder_repr = get_folder_representation(name="whitespace_tessellation", geoms=final_polygons)
    kml_repr = get_final_kml(name="whitespace", d=folder_repr)

    with open(save_path, mode="w+") as f:
        f.write(kml_repr)


def print_my_traceback(tb_config={}):
    """Print custom traceback for debugging."""
    messages = []
    messages.append(f"Exception directory: {tb_config.get('dir_name', 'N/A')}")
    exc_type, exc_value, tb = sys.exc_info()
    if tb is None:
        messages.append("No exception currently being handled.")
        return
    
    # Iterate through the traceback frames
    my_frames_only = []
    for frame_info in traceback.extract_tb(tb):
        # Check if the file path starts with your project root
        if "src/" in frame_info.filename and not "site-packages" in frame_info.filename and not "python" in frame_info.filename.lower():
            my_frames_only.append(frame_info)
            
    if not my_frames_only:
        messages.append("No frames from your project found in the traceback.")
        return

    # Now, format and print only your relevant frames
    for frame in my_frames_only:
        messages.append(f"  File \"{frame.filename}\", line {frame.lineno}, in {frame.name}")
        messages.append(f"    {frame.line.strip()}")
    
    # Always print the exception type and value at the end
    messages.append(f"{exc_type.__name__}: {exc_value}")

    final_print = '\n'.join(messages)
    print(final_print, flush=True)
