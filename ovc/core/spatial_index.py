from __future__ import annotations
import geopandas as gpd


def ensure_sindex(gdf: gpd.GeoDataFrame):
    """Build or return the spatial index (STRtree) for a GeoDataFrame.

    GeoPandas lazily builds the spatial index on first access.
    Calling this explicitly ensures it is ready before query loops.
    """
    return gdf.sindex
