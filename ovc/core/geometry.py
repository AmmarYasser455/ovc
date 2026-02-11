from __future__ import annotations

import geopandas as gpd
from ovc.core.logging import get_logger


def drop_empty_and_fix(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Remove null/empty geometries and attempt to fix invalid ones.

    Parameters
    ----------
    gdf : GeoDataFrame
        Input data.

    Returns
    -------
    GeoDataFrame
        Cleaned data with valid geometries only.
    """
    if gdf is None or gdf.empty:
        return gpd.GeoDataFrame(geometry=[], crs=4326)
    gdf = gdf[gdf.geometry.notna()].copy()
    if gdf.empty:
        return gpd.GeoDataFrame(geometry=[], crs=gdf.crs)
    try:
        gdf["geometry"] = gdf.geometry.make_valid()
    except Exception:
        pass
    # Drop any remaining empty geometries after make_valid
    gdf = gdf[~gdf.geometry.is_empty].copy()
    return gdf


def clip_to_boundary(
    gdf: gpd.GeoDataFrame, boundary: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """Clip features to a boundary polygon using spatial pre-filter.

    Parameters
    ----------
    gdf : GeoDataFrame
        Features to clip.
    boundary : GeoDataFrame
        Boundary polygon(s).

    Returns
    -------
    GeoDataFrame
        Clipped features.
    """
    if gdf is None or gdf.empty:
        return gdf
    if boundary is None or boundary.empty:
        return gdf
    boundary_union = boundary.union_all()
    try:
        out = gdf[gdf.intersects(boundary_union)].copy()
        out["geometry"] = out.geometry.intersection(boundary_union)
        out = out[out.geometry.notna() & ~out.geometry.is_empty].copy()
        return out
    except Exception:
        return gdf
