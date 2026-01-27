from __future__ import annotations

import geopandas as gpd


def build_summary_metrics(
    buildings_4326: gpd.GeoDataFrame,
    overlaps_metric: gpd.GeoDataFrame,
    road_conflicts_buildings_metric: gpd.GeoDataFrame,
    boundary_overlap_buildings_metric: gpd.GeoDataFrame,
    outside_boundary_buildings_metric: gpd.GeoDataFrame,
) -> dict:
    total_buildings = 0 if buildings_4326 is None else int(len(buildings_4326))

    overlap_count = 0 if overlaps_metric is None else int(len(overlaps_metric))
    overlap_total_area = (
        0.0
        if overlaps_metric is None or overlaps_metric.empty
        else float(overlaps_metric["inter_area_m2"].sum())
    )
    overlap_avg_area = (
        0.0
        if overlaps_metric is None or overlaps_metric.empty
        else float(overlaps_metric["inter_area_m2"].mean())
    )

    dup = 0
    part = 0
    sliv = 0
    if overlaps_metric is not None and not overlaps_metric.empty:
        vc = overlaps_metric["overlap_type"].value_counts()
        dup = int(vc.get("duplicate", 0))
        part = int(vc.get("partial", 0))
        sliv = int(vc.get("sliver", 0))

    count_building_on_road = (
        0
        if road_conflicts_buildings_metric is None
        else int(len(road_conflicts_buildings_metric))
    )
    count_building_overlap = overlap_count
    count_building_boundary_overlap = (
        0
        if boundary_overlap_buildings_metric is None
        else int(len(boundary_overlap_buildings_metric))
    )
    count_outside_boundary = (
        0
        if outside_boundary_buildings_metric is None
        else int(len(outside_boundary_buildings_metric))
    )

    error_buildings_ids = set()
    if (
        road_conflicts_buildings_metric is not None
        and not road_conflicts_buildings_metric.empty
        and "bldg_id" in road_conflicts_buildings_metric.columns
    ):
        error_buildings_ids |= set(
            road_conflicts_buildings_metric["bldg_id"].astype(int).tolist()
        )
    if (
        boundary_overlap_buildings_metric is not None
        and not boundary_overlap_buildings_metric.empty
        and "bldg_id" in boundary_overlap_buildings_metric.columns
    ):
        error_buildings_ids |= set(
            boundary_overlap_buildings_metric["bldg_id"].astype(int).tolist()
        )
    if (
        outside_boundary_buildings_metric is not None
        and not outside_boundary_buildings_metric.empty
        and "bldg_id" in outside_boundary_buildings_metric.columns
    ):
        error_buildings_ids |= set(
            outside_boundary_buildings_metric["bldg_id"].astype(int).tolist()
        )
    if overlaps_metric is not None and not overlaps_metric.empty:
        error_buildings_ids |= set(overlaps_metric["bldg_a"].astype(int).tolist())
        error_buildings_ids |= set(overlaps_metric["bldg_b"].astype(int).tolist())

    error_buildings_count = int(len(error_buildings_ids))
    error_buildings_ratio = (
        float(error_buildings_count / total_buildings) if total_buildings > 0 else 0.0
    )

    total_errors = int(
        count_building_on_road
        + count_building_overlap
        + count_building_boundary_overlap
        + count_outside_boundary
    )

    return {
        "total_buildings": total_buildings,
        "total_errors": total_errors,
        "error_buildings_count": error_buildings_count,
        "error_buildings_ratio": error_buildings_ratio,
        "overlap_count": overlap_count,
        "overlap_total_area_m2": overlap_total_area,
        "overlap_avg_area_m2": overlap_avg_area,
        "overlap_duplicate_count": dup,
        "overlap_partial_count": part,
        "overlap_sliver_count": sliv,
        "count_building_on_road": count_building_on_road,
        "count_building_overlap": count_building_overlap,
        "count_building_boundary_overlap": count_building_boundary_overlap,
        "count_outside_boundary": count_outside_boundary,
    }
