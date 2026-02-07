from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, LineString, MultiLineString
from collections import Counter

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


def find_dangles(
    roads_metric: gpd.GeoDataFrame,
    config: RoadQCConfig,
    boundary_metric: gpd.GeoDataFrame | None = None,
) -> gpd.GeoDataFrame:
    """
    Detect dangling endpoints (dead ends) in the road network.

    A dangle is an endpoint that connects to only one road segment,
    indicating a potential incomplete digitization or actual dead end.

    Endpoints near the boundary are excluded (they may connect to roads
    outside the study area).

    Parameters:
        roads_metric: Road geometries in metric CRS
        config: Road QC configuration
        boundary_metric: Optional boundary to filter out edge endpoints

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
    if tolerance <= 0:
        tolerance = 1.0  # Guard against zero division

    # Get boundary buffer for filtering edge endpoints
    boundary_buffer = None
    if boundary_metric is not None and not boundary_metric.empty:
        # Buffer the boundary line by tolerance
        boundary_union = (
            boundary_metric.union_all()
            if hasattr(boundary_metric, "union_all")
            else boundary_metric.unary_union
        )
        boundary_buffer = boundary_union.boundary.buffer(tolerance * 3)

    # Extract all endpoints with their coordinates (rounded for matching)
    endpoints = []
    for _, row in roads.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        pts = _extract_endpoints(geom)
        for pt in pts:
            # Skip endpoints near the boundary (they likely connect to external roads)
            if boundary_buffer is not None and boundary_buffer.contains(pt):
                continue

            # Round to tolerance for grouping
            key = (
                round(pt.x / tolerance) * tolerance,
                round(pt.y / tolerance) * tolerance,
            )
            endpoints.append(
                {
                    "road_id": row["road_id"],
                    "point": pt,
                    "key": key,
                }
            )

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
            dangles.append(
                {
                    "road_id": ep["road_id"],
                    "error_type": "dangle",
                    "geometry": ep["point"],
                }
            )
            seen_keys.add(key)

    if not dangles:
        return gpd.GeoDataFrame(
            {"road_id": [], "error_type": [], "geometry": []},
            geometry="geometry",
            crs=roads.crs,
        )

    return gpd.GeoDataFrame(dangles, geometry="geometry", crs=roads.crs)
