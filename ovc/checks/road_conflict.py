from __future__ import annotations

import geopandas as gpd
from ovc.core.logging import get_logger


def find_buildings_on_roads(
    buildings_metric: gpd.GeoDataFrame,
    roads_metric: gpd.GeoDataFrame,
    road_buffer_m: float,
    min_intersection_area_m2: float,
) -> gpd.GeoDataFrame:
    """Detect buildings that overlap with buffered road geometries.

    Uses spatial-join pre-filtering against the buffered roads to avoid
    the expensive full ``gpd.overlay`` on every building-road pair.

    Parameters
    ----------
    buildings_metric : GeoDataFrame
        Buildings in metric CRS with ``bldg_id`` column.
    roads_metric : GeoDataFrame
        Roads in metric CRS with ``osmid`` column.
    road_buffer_m : float
        Buffer distance (meters) applied to roads.
    min_intersection_area_m2 : float
        Minimum overlap area to flag.

    Returns
    -------
    GeoDataFrame
        Intersection geometries with ``bldg_id``, ``osmid``,
        ``inter_area_m2``, and ``error_type`` columns.
    """
    logger = get_logger("ovc.checks.road_conflict")

    if buildings_metric is None or roads_metric is None:
        return gpd.GeoDataFrame(
            geometry=[],
            crs=buildings_metric.crs if buildings_metric is not None else 3857,
        )
    if buildings_metric.empty or roads_metric.empty:
        return gpd.GeoDataFrame(geometry=[], crs=buildings_metric.crs)

    logger.info(
        f"Road conflict: {len(buildings_metric)} buildings, "
        f"{len(roads_metric)} roads, buffer={road_buffer_m}m"
    )

    rb = roads_metric[["osmid", "geometry"]].copy()
    rb["geometry"] = rb.geometry.buffer(float(road_buffer_m))

    # Spatial join to narrow down candidates (fast STRtree lookup)
    candidates = gpd.sjoin(
        buildings_metric[["bldg_id", "geometry"]],
        rb,
        how="inner",
        predicate="intersects",
    )

    if candidates.empty:
        return gpd.GeoDataFrame(geometry=[], crs=buildings_metric.crs)

    # Only compute exact intersection for candidate pairs
    rows = []
    bldg_geoms = buildings_metric.set_index("bldg_id")["geometry"]
    road_buf_geoms = rb.set_index(rb.index)["geometry"]

    for _, row in candidates.iterrows():
        bldg_id = row["bldg_id"]
        road_idx = row["index_right"]
        bg = bldg_geoms.loc[bldg_id] if bldg_id in bldg_geoms.index else None
        rg = road_buf_geoms.iloc[road_idx] if road_idx < len(road_buf_geoms) else None

        if bg is None or rg is None:
            continue

        inter = bg.intersection(rg)
        if inter is None or inter.is_empty:
            continue

        area = inter.area
        if area >= float(min_intersection_area_m2):
            rows.append(
                {
                    "bldg_id": bldg_id,
                    "osmid": row["osmid"],
                    "inter_area_m2": float(area),
                    "error_type": "building_on_road",
                    "geometry": inter,
                }
            )

    if not rows:
        return gpd.GeoDataFrame(geometry=[], crs=buildings_metric.crs)

    import pandas as pd

    result = gpd.GeoDataFrame(
        pd.DataFrame(rows), geometry="geometry", crs=buildings_metric.crs
    )
    logger.info(f"Found {len(result)} building-road conflicts")
    return result


def build_road_conflict_buildings_layer(
    buildings_metric: gpd.GeoDataFrame, conflicts: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """Return full building geometries for buildings involved in road conflicts."""
    if conflicts is None or conflicts.empty:
        return gpd.GeoDataFrame(geometry=[], crs=buildings_metric.crs)
    ids = set(conflicts["bldg_id"].astype(int).tolist())
    sub = buildings_metric[buildings_metric["bldg_id"].astype(int).isin(ids)].copy()
    sub["error_type"] = "building_on_road"
    sub["overlap_class"] = "n/a"
    return sub
