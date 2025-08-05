from tqdm import tqdm
from osgeo import gdal
from shapely.strtree import STRtree

from shapely.geometry import Point

from ..base import PixelPolygon, Coordinates


class PopulationTif:
    def __init__(self, file, scale=1.0) -> None:
        # Note: gdal take path in string form not in pahtlib.Path form, so we have to convert
        tif_file = str(file)  # converting Path to str

        # up or down scaling by scale constant provided in __init__
        self.scale = scale

        src = gdal.Open(tif_file, gdal.GA_ReadOnly)

        self.height = src.RasterYSize  # number of rows (because we are measuring how stretched y is)
        self.width = src.RasterXSize  # number of columns (because we are measuring how stretched x is)

        self.raster_data = src.ReadAsArray()

        # ulx (upper left x) | uly(upper left y)
        self.ulx, self.xres, self.xskew, self.uly, self.yskew, self.yres = src.GetGeoTransform()

        # lrx (lower right x) | lry (lower right y)
        self.lrx = self.ulx + (self.width * self.xres)
        self.lry = self.uly + (self.height * self.yres)

        print(f"Tif Dimensions:  Width: {self.width}  ||  Height: {self.height}")
        print("Caching & Converting Tif Pixels . . . . .")
        # cache all th pixels and being stored in the form of polygons list, in the self._pixel_polygons:list
        self._pixel_polygons = self.cache_pixels()

        # create str_tree (Spatial Indexing) for faster intersections # str_tree QUERIES ARE VERY VERY EFFICIENT
        self._str_tree = STRtree(self._pixel_polygons)

    def cache_pixels(self) -> list[PixelPolygon]:
        tif_pixel_polys = []

        for r in tqdm(range(self.height)):  # rows
            for c in range(self.width):  # cols

                # some values are negative in population data
                population_val = self.raster_data[r][c]

                # apply check to map negative values to zero
                population_val = max(population_val, 0)

                # break (continue) the loop if population zero, move to next iteration
                if population_val == 0:
                    continue

                # get the coordinates of a pixel (x0 means lower x, x1 means higher value x, same for y)
                x0y0, x0y1, x1y1, x1y0 = self.get_pixel_coords(r, c)
                pixel_coordinates = [x0y0, x0y1, x1y1, x1y0]

                # scaled population
                scaled_population = self.scale * population_val

                # creating polygon of pixel coordinates so we can check intersection later with other(mta, whitespace) polygons
                pixel_polygon = PixelPolygon(pixel_coordinates, x_population=scaled_population, x_position=(r, c))

                # adding to cache for latter use
                tif_pixel_polys.append(pixel_polygon)

        return tif_pixel_polys

    def get_pixel_coords(self, r, c):
        # because changing in column number means we are moving on x axis (left and right)
        x0 = self.ulx + (c * self.xres)
        x1 = self.ulx + ((c + 1) * self.xres)

        # because changing in row number means we are moving along y axis (up and down)
        y0 = self.uly + (r * self.yres)
        y1 = self.uly + ((r + 1) * self.yres)

        # longitude => x-axis
        # latitude => y-axis

        # x0y0, x0y1, x1y0, x1y1
        # so indirectly we are returning (longitude, latitude) because x represent longitude and y latitude.
        return (x0, y0), (x0, y1), (x1, y1), (x1, y0)

    def get_intersecting_pixels(self, poly) -> list[PixelPolygon]:
        """
        Return only the pixels which overlapped with the provided polygon.
        """

        # srt_tree query function will return all the intersecting polygons (from self._str_tree) in the tree with the poly provided
        intersecting_pixels = self._str_tree.query(poly)

        # double check the pixels intersection with the given polygon
        return [pxl_poly for pxl_poly in intersecting_pixels if pxl_poly.intersects(poly)]

    def get_population(self, poly=None):

        population = 0
        intersecting_pixels = self.get_intersecting_pixels(poly) if poly else self._pixel_polygons

        for pxl_poly in intersecting_pixels:
            # if a polygon is provided then intersecting area of pixel will be checked, other wise 1.0 -> 100% is of that pixel will be considered.
            intersecting_percentage = pxl_poly.intersection(poly).area / pxl_poly.area if poly else 1.0
            population += pxl_poly.x_population * intersecting_percentage

        return population

    def to_dict(self, poly=None):
        """
        this method returns a population density data of each pixel of given tif, if "poly" argument is provided it will
        only data of tif pixels overlapping with the given polygon
        """

        intersecting_pixels = self.get_intersecting_pixels(poly) if poly else self._pixel_polygons

        # this is the dict which will contain all the information.
        pixel_recrod = {}

        # "pxl_polygon" in this, is of type PixelPolygon
        for pxl_id, pxl_polygon in enumerate(intersecting_pixels):
            pixel_recrod[pxl_id] = {
                "position": pxl_polygon.x_position,
                "population": pxl_polygon.x_population,
                "coordinates": [Coordinates(*c) for c in pxl_polygon.exterior.coords],
            }

        return pixel_recrod

    def get_point_population(self, p):
        """
        Returns the population value of the grid/box where the point falls.
        If the point doesn't fall in any populated area, returns the population of the nearest grid.

        Args:
            point: A shapely Point object representing the location to check

        Returns:
            float: The population value at that point or from the nearest grid
        """
        p = p if isinstance(p, Point) else Point(p)
        # Query the STR-tree for potential intersecting pixels
        intersecting_pixels = self._str_tree.query(p)

        # Check if the p falls within any of the pixels
        for pxl_poly in intersecting_pixels:
            if pxl_poly.contains(p):
                return pxl_poly.x_population

        # If p doesn't fall in any pixel, find the nearest pixel
        nearest_pixel = self._str_tree.nearest(p)
        return nearest_pixel.x_population
