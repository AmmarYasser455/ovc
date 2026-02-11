from __future__ import annotations

import geopandas as gpd
from ovc.core.logging import get_logger


def find_buildings_touching_boundary(
    buildings_metric: gpd.GeoDataFrame,
    boundary_metric: gpd.GeoDataFrame,
    boundary_buffer_m: float = 0.5,
) -> gpd.GeoDataFrame:
    """Find buildings that touch or overlap the study area boundary.

    This flags buildings that intersect a buffer around the boundary line,
    which may indicate incomplete features or edge effects.

    Parameters
    ----------
    buildings_metric : GeoDataFrame
        Buildings in metric CRS with ``bldg_id`` and ``osmid`` columns.
    boundary_metric : GeoDataFrame
        Boundary polygon(s) in metric CRS.
    boundary_buffer_m : float
        Buffer distance (meters) around the boundary line.

    Returns
    -------
    GeoDataFrame
        Buildings intersecting the boundary buffer, with ``error_type``
        and ``error_class`` columns.
    """
    logger = get_logger("ovc.checks.boundary")

    if buildings_metric is None or buildings_metric.empty:
        return gpd.GeoDataFrame(geometry=[], crs=getattr(buildings_metric, "crs", None))

    if boundary_metric is None or boundary_metric.empty:
        return gpd.GeoDataFrame(geometry=[], crs=buildings_metric.crs)

    boundary_union = boundary_metric.union_all()
    boundary_line = getattr(boundary_union, "boundary", boundary_union)

    buf = (
        gpd.GeoSeries([boundary_line], crs=boundary_metric.crs)
        .buffer(float(boundary_buffer_m))
        .iloc[0]
    )

    mask = buildings_metric.intersects(buf)
    out = buildings_metric.loc[mask, ["bldg_id", "osmid", "geometry"]].copy()

    out["error_type"] = "building_boundary_overlap"
    out["error_class"] = "boundary"

    logger.info(f"Boundary overlap: {len(out)} buildings touch boundary")
    return out
