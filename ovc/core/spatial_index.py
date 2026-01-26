from __future__ import annotations
import geopandas as gpd

def ensure_sindex(gdf: gpd.GeoDataFrame):
    return gdf.sindex
