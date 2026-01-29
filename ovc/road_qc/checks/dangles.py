from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from collections import Counter

from ovc.road_qc.config import RoadQCConfig


def find_dangles(
    roads_metric: gpd.GeoDataFrame,
    config: RoadQCConfig,
) -> gpd.GeoDataFrame:
    """
    Detect dangling endpoints (dead ends) in the road network.

    A dangle is an endpoint that connects to only one road segment,
    indicating a potential incomplete digitization or actual dead end.

    Parameters:
        roads_metric: Road geometries in metric CRS
        config: Road QC configuration

    Returns:
        GeoDataFrame with dangle points, includes error_type column
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

    tolerance = config.dangle_tolerance_m

    # Extract all endpoints with their coordinates (rounded for matching)
    endpoints = []
    for _, row in roads.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        coords = list(geom.coords)
        if len(coords) < 2:
            continue

        start = Point(coords[0])
        end = Point(coords[-1])

        # Round to tolerance for grouping
        start_key = (round(start.x / tolerance) * tolerance,
                     round(start.y / tolerance) * tolerance)
        end_key = (round(end.x / tolerance) * tolerance,
                   round(end.y / tolerance) * tolerance)

        endpoints.append({
            "road_id": row["road_id"],
            "point": start,
            "key": start_key,
        })
        endpoints.append({
            "road_id": row["road_id"],
            "point": end,
            "key": end_key,
        })

    if not endpoints:
        return gpd.GeoDataFrame(
            {"road_id": [], "error_type": [], "geometry": []},
            geometry="geometry",
            crs=roads.crs,
        )

    # Count occurrences of each endpoint location
    key_counts = Counter(ep["key"] for ep in endpoints)

    # Endpoints that appear only once are dangles
    dangles = []
    seen_keys = set()

    for ep in endpoints:
        key = ep["key"]
        if key_counts[key] == 1 and key not in seen_keys:
            dangles.append({
                "road_id": ep["road_id"],
                "error_type": "dangle",
                "geometry": ep["point"],
            })
            seen_keys.add(key)

    if not dangles:
        return gpd.GeoDataFrame(
            {"road_id": [], "error_type": [], "geometry": []},
            geometry="geometry",
            crs=roads.crs,
        )

    return gpd.GeoDataFrame(dangles, geometry="geometry", crs=roads.crs)
