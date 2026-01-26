from __future__ import annotations

import geopandas as gpd
import osmnx as ox
import pandas as pd
from shapely.geometry import box

from ovc.core.crs import ensure_wgs84
from ovc.core.geometry import drop_empty_and_fix


def _split_bounds(bounds, nx: int, ny: int):
    minx, miny, maxx, maxy = bounds
    dx = (maxx - minx) / nx
    dy = (maxy - miny) / ny
    cells = []
    for i in range(nx):
        for j in range(ny):
            cells.append(
                box(
                    minx + i * dx,
                    miny + j * dy,
                    minx + (i + 1) * dx,
                    miny + (j + 1) * dy,
                )
            )
    return cells


def load_buildings(boundary_4326: gpd.GeoDataFrame, tags: dict, parts: int = 9) -> gpd.GeoDataFrame:
    boundary_4326 = ensure_wgs84(boundary_4326)
    aoi = boundary_4326.unary_union

    nx, ny = 3, 3
    cells = _split_bounds(aoi.bounds, nx, ny)
    chunks = []

    for cell in cells:
        try:
            gdf = ox.features_from_polygon(cell, tags)
        except Exception:
            continue

        if gdf is None or gdf.empty:
            continue

        if gdf.crs is None:
            gdf = gdf.set_crs(4326)
        else:
            gdf = gdf.to_crs(4326)

        gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()
        gdf = drop_empty_and_fix(gdf)
        chunks.append(gdf)

    if not chunks:
        return gpd.GeoDataFrame(geometry=[], crs=4326)

    out = gpd.GeoDataFrame(pd.concat(chunks, ignore_index=True), crs=4326)
    out = out.reset_index(drop=False).rename(columns={"index": "osmid"})
    out["osmid"] = out["osmid"].astype(str)
    out = out[out.intersects(aoi)].copy()
    out = out.reset_index(drop=True)
    return out
