from __future__ import annotations

import geopandas as gpd


def find_buildings_touching_boundary(
    buildings_metric: gpd.GeoDataFrame,
    boundary_metric: gpd.GeoDataFrame,
    boundary_buffer_m: float = 0.5,
) -> gpd.GeoDataFrame:
    if buildings_metric is None or buildings_metric.empty:
        return gpd.GeoDataFrame(geometry=[], crs=getattr(buildings_metric, "crs", None))

    if boundary_metric is None or boundary_metric.empty:
        return gpd.GeoDataFrame(geometry=[], crs=buildings_metric.crs)

    boundary_union = boundary_metric.unary_union
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
    return out
