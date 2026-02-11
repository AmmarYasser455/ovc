from __future__ import annotations
from dataclasses import dataclass
import geopandas as gpd
from pyproj import CRS


@dataclass(frozen=True)
class CRSResult:
    crs_wgs84: CRS
    crs_metric: CRS


def choose_utm_crs_from_gdf(gdf_4326: gpd.GeoDataFrame) -> CRS:
    if gdf_4326 is None or gdf_4326.empty:
        return CRS.from_epsg(3857)
    c = gdf_4326.union_all().centroid
    lon, lat = float(c.x), float(c.y)
    zone = int((lon + 180) // 6) + 1
    zone = max(1, min(zone, 60))  # Clamp to valid UTM zone range
    epsg = 32600 + zone if lat >= 0 else 32700 + zone
    return CRS.from_epsg(epsg)


def ensure_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Reproject a GeoDataFrame to WGS 84 (EPSG:4326).

    Raises
    ------
    ValueError
        If the GeoDataFrame has no CRS defined.  OVC requires
        georeferenced data to prevent silent coordinate corruption.

        Previously this function silently assumed ``EPSG:4326`` when
        ``crs`` was ``None``, which could produce incorrect QC results
        if the data was actually in a projected CRS.
    """
    if gdf.crs is None:
        raise ValueError(
            "Input data has no CRS defined. OVC requires georeferenced data. "
            "Set the CRS in your source file (e.g. via QGIS or ogr2ogr), "
            "or run 'geoqa profile <file>' to diagnose the issue."
        )
    return gdf.to_crs(4326)


def get_crs_pair(boundary_gdf: gpd.GeoDataFrame) -> CRSResult:
    boundary_4326 = ensure_wgs84(boundary_gdf)
    return CRSResult(
        crs_wgs84=CRS.from_epsg(4326), crs_metric=choose_utm_crs_from_gdf(boundary_4326)
    )
