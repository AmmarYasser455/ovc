from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point, LineString, MultiLineString

from ovc.road_qc.config import RoadQCConfig


def _extract_endpoints(geom) -> list[Point]:
    """Extract start and end points from LineString or MultiLineString."""
    endpoints = []

    if isinstance(geom, LineString):
        coords = list(geom.coords)
        if len(coords) >= 2:
            endpoints.append(Point(coords[0]))
            endpoints.append(Point(coords[-1]))
    elif isinstance(geom, MultiLineString):
        for line in geom.geoms:
            coords = list(line.coords)
            if len(coords) >= 2:
                endpoints.append(Point(coords[0]))
                endpoints.append(Point(coords[-1]))

    return endpoints


def find_disconnected_segments(
    roads_metric: gpd.GeoDataFrame,
    config: RoadQCConfig,
) -> gpd.GeoDataFrame:
    """Detect road segments not connected to the network.

    A segment is disconnected if neither of its endpoints is within
    ``disconnect_tolerance_m`` of any other segment's endpoints.
    Uses vectorized spatial-join for performance.

    Parameters
    ----------
    roads_metric : GeoDataFrame
        Road geometries in metric CRS.
    config : RoadQCConfig
        Configuration.

    Returns
    -------
    GeoDataFrame
        Disconnected segments with ``error_type`` column.
    """
    if roads_metric is None or roads_metric.empty:
        return gpd.GeoDataFrame(
            {"road_id": [], "error_type": [], "geometry": []},
            geometry="geometry",
            crs=getattr(roads_metric, "crs", None),
        )

    roads = roads_metric.copy()
    if "road_id" not in roads.columns:
        roads["road_id"] = roads.index.astype(str)

    tolerance = config.disconnect_tolerance_m

    # Extract all endpoints into a GeoDataFrame
    ep_records = []
    for idx, row in roads.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        for pt in _extract_endpoints(geom):
            ep_records.append({"road_id": row["road_id"], "geometry": pt})

    if not ep_records:
        return gpd.GeoDataFrame(
            {"road_id": [], "error_type": [], "geometry": []},
            geometry="geometry",
            crs=roads.crs,
        )

    ep_gdf = gpd.GeoDataFrame(ep_records, geometry="geometry", crs=roads.crs)

    # Buffer each endpoint by tolerance and spatial-join against all endpoints
    ep_gdf_buf = ep_gdf.copy()
    ep_gdf_buf["geometry"] = ep_gdf.geometry.buffer(tolerance)
    joined = gpd.sjoin(ep_gdf_buf, ep_gdf, how="inner", predicate="intersects")

    # Find which road_ids connect to a DIFFERENT road_id
    cross = joined[joined["road_id_left"] != joined["road_id_right"]]
    connected_ids = set(cross["road_id_left"].unique())

    all_ids = set(roads["road_id"].unique())
    disconnected_ids = all_ids - connected_ids

    if not disconnected_ids:
        return gpd.GeoDataFrame(
            {"road_id": [], "error_type": [], "geometry": []},
            geometry="geometry",
            crs=roads.crs,
        )

    result = roads[roads["road_id"].isin(disconnected_ids)][
        ["road_id", "geometry"]
    ].copy()
    result["error_type"] = "disconnected_segment"

    return result
