from __future__ import annotations

import geopandas as gpd
import osmnx as ox

from ovc.core.crs import ensure_wgs84
from ovc.core.geometry import drop_empty_and_fix, clip_to_boundary


def load_roads(boundary_4326: gpd.GeoDataFrame, tags: dict) -> gpd.GeoDataFrame:
    """
    Load OSM roads intersecting the AOI polygon.

    - Uses polygon-based query (NOT bbox)
    - Clips results strictly to boundary
    - Returns LineString / MultiLineString only
    - FAIL-SAFE if no roads are found
    """

    if boundary_4326 is None or boundary_4326.empty:
        return gpd.GeoDataFrame(geometry=[], crs=4326)

    boundary_4326 = ensure_wgs84(boundary_4326)

    aoi_geom = boundary_4326.unary_union

    try:
        gdf = ox.features_from_polygon(aoi_geom, tags)
    except Exception:
        return gpd.GeoDataFrame(geometry=[], crs=4326)

    if gdf is None or gdf.empty:
        return gpd.GeoDataFrame(geometry=[], crs=4326)

    if gdf.crs is None:
        gdf = gdf.set_crs(4326)
    else:
        gdf = gdf.to_crs(4326)

    gdf = gdf[gdf.geometry.type.isin(["LineString", "MultiLineString"])].copy()

    if gdf.empty:
        return gpd.GeoDataFrame(geometry=[], crs=4326)

    gdf = drop_empty_and_fix(gdf)

    if gdf.empty:
        return gpd.GeoDataFrame(geometry=[], crs=4326)

    gdf = clip_to_boundary(gdf, boundary_4326)

    if gdf.empty:
        return gpd.GeoDataFrame(geometry=[], crs=4326)

    gdf = gdf.reset_index(drop=False).rename(columns={"index": "osmid"})
    if "osmid" not in gdf.columns:
        gdf["osmid"] = gdf.index.astype(str)
    else:
        gdf["osmid"] = gdf["osmid"].astype(str)

    gdf["feature_type"] = "road"

    return gdf
