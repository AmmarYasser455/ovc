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
    epsg = 32600 + zone if lat >= 0 else 32700 + zone
    return CRS.from_epsg(epsg)


def ensure_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        return gdf.set_crs(4326)
    return gdf.to_crs(4326)


def get_crs_pair(boundary_gdf: gpd.GeoDataFrame) -> CRSResult:
    boundary_4326 = ensure_wgs84(boundary_gdf)
    return CRSResult(
        crs_wgs84=CRS.from_epsg(4326), crs_metric=choose_utm_crs_from_gdf(boundary_4326)
    )
