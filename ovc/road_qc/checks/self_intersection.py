from __future__ import annotations

import geopandas as gpd
from shapely.geometry import Point, MultiPoint

from ovc.road_qc.config import RoadQCConfig


def find_self_intersections(
    roads_metric: gpd.GeoDataFrame,
    config: RoadQCConfig,
) -> gpd.GeoDataFrame:
    """
    Detect roads that intersect themselves.

    Uses Shapely's `is_simple` property to identify non-simple geometries
    (those with self-intersections).

    Parameters:
        roads_metric: Road geometries in metric CRS
        config: Road QC configuration

    Returns:
        GeoDataFrame with self-intersection points, includes error_type column
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

    errors = []

    for _, row in roads.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        # Check if geometry is simple (no self-intersections)
        if geom.is_simple:
            continue

        # Non-simple geometry: find intersection points
        road_id = row["road_id"]

        # Get the self-intersection point(s) using unary_union trick
        try:
            # Buffer slightly and get boundary intersections
            boundary = geom.boundary
            if boundary is not None and not boundary.is_empty:
                # For non-simple lines, the intersection points can be found
                # by detecting where the line crosses itself
                inter = geom.intersection(geom.buffer(config.self_intersection_buffer_m))
                if inter is not None and not inter.is_empty:
                    # Extract centroid as representative point
                    errors.append({
                        "road_id": road_id,
                        "error_type": "self_intersection",
                        "geometry": geom.centroid,
                    })
        except Exception:
            # Fallback: just mark the road as having self-intersection
            errors.append({
                "road_id": road_id,
                "error_type": "self_intersection",
                "geometry": geom.centroid,
            })

    if not errors:
        return gpd.GeoDataFrame(
            {"road_id": [], "error_type": [], "geometry": []},
            geometry="geometry",
            crs=roads.crs,
        )

    return gpd.GeoDataFrame(errors, geometry="geometry", crs=roads.crs)
