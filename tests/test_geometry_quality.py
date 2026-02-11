"""Tests for geometry quality checks (new in v2.0.0)."""

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import Polygon, LineString, Point, MultiPolygon

from ovc.checks.geometry_quality import (
    find_duplicate_geometries,
    find_invalid_geometries,
    find_unreasonable_areas,
    compute_compactness,
    find_min_road_distance_violations,
)


# ── Duplicate geometry tests ──────────────────────────────────


def test_exact_duplicates_detected():
    poly = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    gdf = gpd.GeoDataFrame(
        {"bldg_id": [0, 1, 2]},
        geometry=[poly, poly, Polygon([(20, 20), (30, 20), (30, 30), (20, 30)])],
        crs=3857,
    )
    result = find_duplicate_geometries(gdf)
    # Buildings 0 and 1 are duplicates
    assert len(result) == 2
    assert set(result["bldg_id"]) == {0, 1}


def test_no_duplicates():
    gdf = gpd.GeoDataFrame(
        {"bldg_id": [0, 1]},
        geometry=[
            Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]),
            Polygon([(20, 20), (30, 20), (30, 30), (20, 30)]),
        ],
        crs=3857,
    )
    result = find_duplicate_geometries(gdf)
    assert len(result) == 0


def test_duplicates_empty_input():
    gdf = gpd.GeoDataFrame(geometry=[], crs=3857)
    gdf["bldg_id"] = []
    result = find_duplicate_geometries(gdf)
    assert len(result) == 0


# ── Invalid geometry tests ────────────────────────────────────


def test_self_intersecting_polygon():
    # Bowtie polygon (self-intersecting)
    bowtie = Polygon([(0, 0), (10, 10), (10, 0), (0, 10)])
    gdf = gpd.GeoDataFrame(
        {"bldg_id": [0]},
        geometry=[bowtie],
        crs=3857,
    )
    result = find_invalid_geometries(gdf)
    assert len(result) == 1
    assert "Self-intersection" in result.iloc[0]["validity_reason"]


def test_valid_polygon():
    gdf = gpd.GeoDataFrame(
        {"bldg_id": [0]},
        geometry=[Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])],
        crs=3857,
    )
    result = find_invalid_geometries(gdf)
    assert len(result) == 0


# ── Area reasonableness tests ────────────────────────────────


def test_too_small_building():
    # 1 sq meter (<4 default threshold)
    tiny = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    gdf = gpd.GeoDataFrame(
        {"bldg_id": [0]},
        geometry=[tiny],
        crs=3857,
    )
    result = find_unreasonable_areas(gdf, min_area_m2=4.0, max_area_m2=50000.0)
    assert len(result) == 1
    assert result.iloc[0]["error_class"] == "too_small"


def test_too_large_building():
    # 100k sq meters (>50k threshold)
    huge = Polygon([(0, 0), (1000, 0), (1000, 100), (0, 100)])
    gdf = gpd.GeoDataFrame(
        {"bldg_id": [0]},
        geometry=[huge],
        crs=3857,
    )
    result = find_unreasonable_areas(gdf, min_area_m2=4.0, max_area_m2=50000.0)
    assert len(result) == 1
    assert result.iloc[0]["error_class"] == "too_large"


def test_reasonable_area():
    # 100 sq meters — within range
    normal = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    gdf = gpd.GeoDataFrame(
        {"bldg_id": [0]},
        geometry=[normal],
        crs=3857,
    )
    result = find_unreasonable_areas(gdf)
    assert len(result) == 0


# ── Compactness tests ─────────────────────────────────────────


def test_compact_square():
    """A square should have a compactness around 0.785 (well above 0.2)."""
    sq = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    gdf = gpd.GeoDataFrame(
        {"bldg_id": [0]},
        geometry=[sq],
        crs=3857,
    )
    result = compute_compactness(gdf, min_compactness=0.2)
    assert len(result) == 0  # Square should NOT be flagged


def test_narrow_polygon_flagged():
    """A very thin polygon should be flagged as low compactness."""
    narrow = Polygon([(0, 0), (100, 0), (100, 0.5), (0, 0.5)])
    gdf = gpd.GeoDataFrame(
        {"bldg_id": [0]},
        geometry=[narrow],
        crs=3857,
    )
    result = compute_compactness(gdf, min_compactness=0.2)
    assert len(result) == 1


# ── Road distance violation tests ─────────────────────────────


def test_building_too_close_to_road():
    bldg = Polygon([(1, 0), (3, 0), (3, 2), (1, 2)])
    road = LineString([(0, 0), (0, 10)])
    buildings = gpd.GeoDataFrame(
        {"bldg_id": [0]},
        geometry=[bldg],
        crs=3857,
    )
    roads = gpd.GeoDataFrame(
        geometry=[road],
        crs=3857,
    )
    result = find_min_road_distance_violations(buildings, roads, min_distance_m=3.0)
    assert len(result) == 1  # Building is 1m from road, threshold is 3m


def test_building_far_from_road():
    bldg = Polygon([(50, 0), (60, 0), (60, 10), (50, 10)])
    road = LineString([(0, 0), (0, 10)])
    buildings = gpd.GeoDataFrame(
        {"bldg_id": [0]},
        geometry=[bldg],
        crs=3857,
    )
    roads = gpd.GeoDataFrame(
        geometry=[road],
        crs=3857,
    )
    result = find_min_road_distance_violations(buildings, roads, min_distance_m=3.0)
    assert len(result) == 0


def test_empty_buildings_distance():
    result = find_min_road_distance_violations(
        gpd.GeoDataFrame(geometry=[], crs=3857),
        gpd.GeoDataFrame(geometry=[LineString([(0, 0), (1, 1)])], crs=3857),
    )
    assert len(result) == 0


def test_empty_roads_distance():
    bldg = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    result = find_min_road_distance_violations(
        gpd.GeoDataFrame({"bldg_id": [0]}, geometry=[bldg], crs=3857),
        gpd.GeoDataFrame(geometry=[], crs=3857),
    )
    assert len(result) == 0
