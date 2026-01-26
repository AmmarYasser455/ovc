from __future__ import annotations
import geopandas as gpd

def drop_empty_and_fix(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf is None or gdf.empty:
        return gpd.GeoDataFrame(geometry=[], crs=4326)
    gdf = gdf[gdf.geometry.notna()].copy()
    if gdf.empty:
        return gpd.GeoDataFrame(geometry=[], crs=gdf.crs)
    try:
        gdf["geometry"] = gdf.geometry.make_valid()
    except Exception:
        pass
    return gdf

def clip_to_boundary(gdf: gpd.GeoDataFrame, boundary: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf is None or gdf.empty:
        return gdf
    if boundary is None or boundary.empty:
        return gdf
    boundary_union = boundary.unary_union
    try:
        out = gdf[gdf.intersects(boundary_union)].copy()
        out["geometry"] = out.geometry.intersection(boundary_union)
        out = out[out.geometry.notna()].copy()
        return out
    except Exception:
        return gdf
