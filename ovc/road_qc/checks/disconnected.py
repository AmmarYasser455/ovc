from __future__ import annotations

import geopandas as gpd
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
    """
    Detect road segments that are not connected to the network.

    A segment is disconnected if neither of its endpoints is within
    `disconnect_tolerance_m` of any other segment's endpoints.

    Parameters:
        roads_metric: Road geometries in metric CRS
        config: Road QC configuration

    Returns:
        GeoDataFrame with disconnected segments, includes error_type column
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

    # Extract all endpoints
    endpoints = []
    for idx, row in roads.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        pts = _extract_endpoints(geom)
        for pt in pts:
            endpoints.append({"road_id": row["road_id"], "point": pt})

    if not endpoints:
        return gpd.GeoDataFrame(
            {"road_id": [], "error_type": [], "geometry": []},
            geometry="geometry",
            crs=roads.crs,
        )

    ep_df = pd.DataFrame(endpoints)
    ep_gdf = gpd.GeoDataFrame(ep_df, geometry="point", crs=roads.crs)

    # Build spatial index and find disconnected segments
    tolerance = config.disconnect_tolerance_m
    disconnected_ids = set()

    # Use spatial index for efficient neighbor lookup
    sindex = ep_gdf.sindex

    for road_id in roads["road_id"].unique():
        road_endpoints = ep_gdf[ep_gdf["road_id"] == road_id]

        # Check if any endpoint connects to another road via spatial index
        connected = False
        for _, ep in road_endpoints.iterrows():
            pt = ep["point"]
            # Query spatial index with buffered bounds
            minx, miny, maxx, maxy = (
                pt.x - tolerance, pt.y - tolerance,
                pt.x + tolerance, pt.y + tolerance,
            )
            candidates = list(sindex.intersection((minx, miny, maxx, maxy)))
            for idx in candidates:
                candidate = ep_gdf.iloc[idx]
                if candidate["road_id"] == road_id:
                    continue
                if pt.distance(candidate["point"]) <= tolerance:
                    connected = True
                    break
            if connected:
                break

        if not connected:
            disconnected_ids.add(road_id)

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
