from __future__ import annotations

import geopandas as gpd
import osmnx as ox
import pandas as pd
from shapely.geometry import box

from ovc.core.crs import ensure_wgs84
from ovc.core.geometry import drop_empty_and_fix
from ovc.core.logging import get_logger

# Configure osmnx
ox.settings.use_cache = True
ox.settings.log_console = False
ox.settings.timeout = 30


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


def load_buildings(
    boundary_4326: gpd.GeoDataFrame, tags: dict, parts: int = 16
) -> gpd.GeoDataFrame:
    boundary_4326 = ensure_wgs84(boundary_4326)
    aoi = boundary_4326.union_all()

    # Dynamic grid sizing: aim for ~2.0 km² chunks
    # Reproject to metric for area calculation
    aoi_metric = gpd.GeoSeries([aoi], crs=4326).to_crs(boundary_4326.estimate_utm_crs())
    area_km2 = aoi_metric.area.iloc[0] / 1e6
    
    # Calculate required chunks (min 16 still applies as a baseline if small)
    target_chunk_km2 = 2.0
    required_chunks = max(parts, int(area_km2 / target_chunk_km2))
    
    side = max(1, int(required_chunks**0.5))
    nx, ny = side, side
    
    cells = _split_bounds(aoi.bounds, nx, ny)
    logger = get_logger("ovc.loaders.buildings")
    logger.info(f"Targeting {required_chunks} chunks ({side}x{side}) for {area_km2:.1f} km² area")
    chunks = []

    for i, cell in enumerate(cells):
        logger.info(f"Downloading buildings chunk {i+1}/{len(cells)}...")
        try:
            gdf = ox.features_from_polygon(cell, tags)
        except Exception as e:
            msg = str(e)
            if "No data found for query" in msg:
                 # This is common in empty areas (desert, sea), don't warn
                 logger.debug(f"Chunk {i+1}: No buildings found (expected for empty areas)")
            else:
                 logger.warning(f"Failed to download chunk {i+1}: {e}")
            continue

        if gdf is None or gdf.empty:
            continue

        if gdf.crs is None:
            gdf = gdf.set_crs(4326)
        else:
            gdf = gdf.to_crs(4326)

        gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()
        gdf = drop_empty_and_fix(gdf)

        # Preserve real OSM IDs from osmnx MultiIndex before concat
        gdf = gdf.reset_index(drop=False)
        if "osmid" not in gdf.columns:
            if "element_type" in gdf.columns and "osmid" in gdf.columns:
                pass  # already present
            elif gdf.index.name == "osmid":
                gdf = gdf.reset_index()
            else:
                gdf["osmid"] = gdf.index.astype(str)
        gdf["osmid"] = gdf["osmid"].astype(str)

        chunks.append(gdf)

    if not chunks:
        return gpd.GeoDataFrame(geometry=[], crs=4326)

    out = gpd.GeoDataFrame(pd.concat(chunks, ignore_index=True), crs=4326)

    # Deduplicate buildings fetched from overlapping grid cells
    if "osmid" in out.columns:
        out = out.drop_duplicates(subset="osmid", keep="first")

    out = out[out.intersects(aoi)].copy()
    out = out.reset_index(drop=True)
    return out
