"""
Optimized PopulationTif class for handling large TIF files.
This class extracts only the relevant portions of TIF files based on boundary polygons,
avoiding memory issues with large global datasets.
"""

from pathlib import Path
from typing import List, Optional, Tuple, Union

import numpy as np
from osgeo import gdal
from shapely.geometry import Point, Polygon
from shapely.strtree import STRtree
from tqdm import tqdm

from ..base import PixelPolygon, Coordinates


class OptimizedPopulationTif:
    """
    Memory-efficient TIF processor that extracts only boundary-relevant portions.
    """
    
    def __init__(self, file: Union[str, Path], scale: float = 1.0, buffer_degrees: float = 0.01):
        """
        Initialize optimized TIF processor.
        
        Args:
            file: Path to the TIF file
            scale: Population scaling factor
            buffer_degrees: Buffer around boundary for extraction (in degrees)
        """
        self.tif_file = str(file)
        self.scale = scale
        self.buffer_degrees = buffer_degrees
        
        # Open TIF file in read-only mode
        self.src = gdal.Open(self.tif_file, gdal.GA_ReadOnly)
        if self.src is None:
            raise ValueError(f"Could not open TIF file: {self.tif_file}")
        
        # Get basic raster information
        self.height = self.src.RasterYSize
        self.width = self.src.RasterXSize
        self.geo_transform = self.src.GetGeoTransform()
        
        # Calculate bounds
        self.ulx, self.xres, self.xskew, self.uly, self.yskew, self.yres = self.geo_transform
        self.lrx = self.ulx + (self.width * self.xres)
        self.lry = self.uly + (self.height * self.yres)
        
        print(f"TIF Dimensions: Width: {self.width} || Height: {self.height}")
        print(f"TIF Bounds: ({self.ulx}, {self.lry}) to ({self.lrx}, {self.uly})")
        
        # Initialize empty containers - will be populated when boundaries are processed
        self._pixel_polygons = []
        self._str_tree = None
        self._extracted_bounds = None
        self._extracted_data = None
        
    def extract_for_boundary(self, boundary_polygon: Polygon, area_id: str, output_dir: Path) -> bool:
        """
        Extract TIF data for a specific boundary polygon and save as cropped TIF.
        
        Args:
            boundary_polygon: Shapely polygon representing the boundary
            area_id: Unique identifier for the area
            output_dir: Directory to save the cropped TIF file
            
        Returns:
            bool: True if extraction was successful
        """
        try:
            print(f"Extracting TIF data for area: {area_id}")
            
            # Add buffer to boundary
            buffered_boundary = boundary_polygon.buffer(self.buffer_degrees)
            
            # Get bounding box of the buffered boundary
            minx, miny, maxx, maxy = buffered_boundary.bounds
            
            # Convert geographic coordinates to pixel coordinates
            min_col, min_row = self._geo_to_pixel(minx, maxy)
            max_col, max_row = self._geo_to_pixel(maxx, miny)
            
            # Ensure bounds are within raster
            min_col = max(0, min_col)
            min_row = max(0, min_row)
            max_col = min(self.width, max_col)
            max_row = min(self.height, max_row)
            
            if min_col >= max_col or min_row >= max_row:
                print(f"No TIF data intersects with boundary for area: {area_id}")
                return False
            
            # Calculate extraction parameters
            width = max_col - min_col
            height = max_row - min_row
            
            print(f"Extracting region: cols {min_col}-{max_col}, rows {min_row}-{max_row}")
            print(f"Extraction size: {width}x{height} pixels")
            
            # Read only the required portion of the TIF (bounding window)
            extracted_data = self.src.ReadAsArray(
                xoff=min_col,
                yoff=min_row,
                xsize=width,
                ysize=height
            )
            # Handle multi-band rasters by taking the first band
            if extracted_data is None:
                print(f"GDAL returned no data for area: {area_id}")
                return False
            if extracted_data.ndim == 3:
                # GDAL returns (bands, rows, cols)
                extracted_data = extracted_data[0, :, :]
            
            # Create output directory
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Save cropped TIF file as population.tif (standard naming)
            cropped_tif_path = output_dir / "population.tif"
            self._save_cropped_tif(extracted_data, min_col, min_row, cropped_tif_path)
            
            # Note: We no longer post-process pixel polygons here. Downstream
            # workflows read the saved cropped TIF.
            
            print(f"Successfully extracted TIF data for area: {area_id}")
            return True
            
        except Exception as e:
            print(f"Error extracting TIF data for area {area_id}: {e}")
            return False

    def extract_for_boundary_path(self, boundary_path: Union[str, Path], area_id: str, output_dir: Path) -> bool:
        """
        Extract using GDAL cutline (precise mask clipping like QGIS cliprasterbymasklayer).

        Args:
            boundary_path: Path to boundary vector (e.g., KML)
            area_id: Area identifier
            output_dir: Target directory for population.tif
        """
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            cropped_tif_path = output_dir / "population.tif"

            warp_opts = gdal.WarpOptions(
                format="GTiff",
                cutlineDSName=str(boundary_path),
                cropToCutline=True,
                dstAlpha=True,
                dstNodata=-9999,
                multithread=True,
                creationOptions=["COMPRESS=LZW", "TILED=YES"]
            )
            warp_res = gdal.Warp(
                destNameOrDestDS=str(cropped_tif_path),
                srcDSOrSrcDSTab=self.src,
                options=warp_opts
            )

            if warp_res is None:
                print(f"GDAL Warp failed for area: {area_id}")
                return False

            # Flush and close the dataset created by Warp
            warp_res.FlushCache()
            warp_res = None

            print(f"Saved clipped TIF via cutline: {cropped_tif_path}")
            return True

        except Exception as e:
            print(f"Error during GDAL cutline warp for area {area_id}: {e}")
            return False
    
    def _geo_to_pixel(self, lon: float, lat: float) -> Tuple[int, int]:
        """Convert geographic coordinates to pixel coordinates."""
        col = int((lon - self.ulx) / self.xres)
        # In north-up rasters yres is typically negative; invert accordingly
        row = int((lat - self.uly) / self.yres)
        return col, row
    
    def _pixel_to_geo(self, col: int, row: int) -> Tuple[float, float]:
        """Convert pixel coordinates to geographic coordinates."""
        lon = self.ulx + (col * self.xres)
        lat = self.uly + (row * self.yres)
        return lon, lat
    
    def _save_cropped_tif(self, data: np.ndarray, min_col: int, min_row: int, output_path: Path):
        """Save cropped TIF data to file."""
        # Create new geotransform for cropped data
        new_ulx = self.ulx + (min_col * self.xres)
        new_uly = self.uly + (min_row * self.yres)
        new_geo_transform = (new_ulx, self.xres, self.xskew, new_uly, self.yskew, self.yres)
        
        # Create output dataset
        driver = gdal.GetDriverByName('GTiff')
        dst_ds = driver.Create(
            str(output_path),
            data.shape[1],  # width
            data.shape[0],  # height
            1,  # number of bands
            gdal.GDT_Float32
        )
        
        # Set geotransform and projection
        dst_ds.SetGeoTransform(new_geo_transform)
        dst_ds.SetProjection(self.src.GetProjection())
        
        # Write data
        dst_ds.GetRasterBand(1).WriteArray(data)
        dst_ds.FlushCache()
        dst_ds = None
        
        print(f"Saved cropped TIF: {output_path}")
    
    def _process_extracted_data(self, data: np.ndarray, min_col: int, min_row: int, boundary_polygon: Polygon):
        """Process extracted TIF data into pixel polygons."""
        height, width = data.shape
        pixel_polygons = []
        
        print("Processing extracted TIF pixels...")
        
        for r in tqdm(range(height), desc="Processing pixels"):
            for c in range(width):
                # Get population value
                population_val = data[r, c]
                
                # Apply scaling and filter zero values
                population_val = max(population_val, 0)
                if population_val == 0:
                    continue
                
                # Convert to absolute pixel coordinates
                abs_r = min_row + r
                abs_c = min_col + c
                
                # Get pixel coordinates
                x0y0, x0y1, x1y1, x1y0 = self._get_pixel_coords(abs_r, abs_c)
                pixel_coordinates = [x0y0, x0y1, x1y1, x1y0]
                
                # Create pixel polygon
                pixel_polygon = PixelPolygon(
                    pixel_coordinates,
                    x_population=self.scale * population_val,
                    x_position=(abs_r, abs_c)
                )
                
                # Only add if it intersects with the boundary
                if pixel_polygon.intersects(boundary_polygon):
                    pixel_polygons.append(pixel_polygon)
        
        # Update class attributes
        self._pixel_polygons = pixel_polygons
        self._str_tree = STRtree(pixel_polygons)
        
        print(f"Processed {len(pixel_polygons)} intersecting pixels")
    
    def _get_pixel_coords(self, r: int, c: int) -> Tuple[Tuple[float, float], ...]:
        """Get geographic coordinates for a pixel."""
        x0 = self.ulx + (c * self.xres)
        x1 = self.ulx + ((c + 1) * self.xres)
        y0 = self.uly + (r * self.yres)
        y1 = self.uly + ((r + 1) * self.yres)
        
        return (x0, y0), (x0, y1), (x1, y1), (x1, y0)
    
    def get_intersecting_pixels(self, poly: Polygon) -> List[PixelPolygon]:
        """Return pixels that intersect with the given polygon."""
        if self._str_tree is None:
            return []
        
        intersecting_pixels = self._str_tree.query(poly)
        return [pxl_poly for pxl_poly in intersecting_pixels if pxl_poly.intersects(poly)]
    
    def get_population(self, poly: Optional[Polygon] = None) -> float:
        """Calculate total population for the given polygon."""
        population = 0.0
        intersecting_pixels = self.get_intersecting_pixels(poly) if poly else self._pixel_polygons
        
        for pxl_poly in intersecting_pixels:
            intersecting_percentage = pxl_poly.intersection(poly).area / pxl_poly.area if poly else 1.0
            population += pxl_poly.x_population * intersecting_percentage
        
        return population
    
    def to_dict(self, poly: Optional[Polygon] = None) -> dict:
        """Convert pixel data to dictionary format."""
        intersecting_pixels = self.get_intersecting_pixels(poly) if poly else self._pixel_polygons
        
        pixel_record = {}
        for pxl_id, pxl_polygon in enumerate(intersecting_pixels):
            pixel_record[pxl_id] = {
                "position": pxl_polygon.x_position,
                "population": pxl_polygon.x_population,
                "coordinates": [Coordinates(*c) for c in pxl_polygon.exterior.coords],
            }
        
        return pixel_record
    
    def get_point_population(self, point: Union[Point, Tuple[float, float]]) -> float:
        """Get population value at a specific point."""
        point = point if isinstance(point, Point) else Point(point)
        
        if self._str_tree is None:
            return 0.0
        
        # Query for intersecting pixels
        intersecting_pixels = self._str_tree.query(point)
        
        # Check if point is within any pixel
        for pxl_poly in intersecting_pixels:
            if pxl_poly.contains(point):
                return pxl_poly.x_population
        
        # If not found, return 0
        return 0.0
    
    def close(self):
        """Close the TIF file."""
        if self.src:
            self.src = None
    
    def __del__(self):
        """Cleanup when object is destroyed."""
        self.close()


def extract_tif_for_areas(global_tif_path: Union[str, Path], 
                         area_cutlines: dict, 
                         output_base_dir: Path,
                         scale: float = 1.0,
                         buffer_degrees: float = 0.01) -> dict:
    """
    Extract TIF data for multiple areas efficiently.
    
    Args:
        global_tif_path: Path to the global TIF file
        area_boundaries: Dictionary mapping area_id to boundary polygon
        output_base_dir: Base directory for output files
        scale: Population scaling factor
        buffer_degrees: Buffer around boundaries for extraction
        
    Returns:
        dict: Mapping of area_id to success status
    """
    results = {}
    
    # Initialize the optimized TIF processor
    tif_processor = OptimizedPopulationTif(global_tif_path, scale, buffer_degrees)
    
    try:
        for area_id, boundary_path in area_cutlines.items():
            print(f"\nProcessing area: {area_id}")
            
            # Create area-specific output directory
            area_output_dir = output_base_dir / area_id / "tifs"
            
            # Prefer precise clipping via cutline
            success = tif_processor.extract_for_boundary_path(
                boundary_path,
                area_id,
                area_output_dir
            )
            
            results[area_id] = success
            
            if success:
                print(f"✅ Successfully processed area: {area_id}")
            else:
                print(f"❌ Failed to process area: {area_id}")
    
    finally:
        # Clean up
        tif_processor.close()
    
    return results
