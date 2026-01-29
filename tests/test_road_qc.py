import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point

from ovc.road_qc.config import RoadQCConfig
from ovc.road_qc.checks.disconnected import find_disconnected_segments
from ovc.road_qc.checks.self_intersection import find_self_intersections
from ovc.road_qc.checks.dangles import find_dangles
from ovc.road_qc.metrics import compute_road_qc_metrics, merge_errors


CONFIG = RoadQCConfig()


def test_disconnected_single_road():
    """Single road is always disconnected (no network)."""
    gdf = gpd.GeoDataFrame(
        {"road_id": ["r1"]},
        geometry=[LineString([(0, 0), (10, 0)])],
        crs=3857,
    )
    result = find_disconnected_segments(gdf, CONFIG)
    assert len(result) == 1
    assert result.iloc[0]["error_type"] == "disconnected_segment"


def test_connected_roads():
    """Two roads sharing an endpoint are not disconnected."""
    gdf = gpd.GeoDataFrame(
        {"road_id": ["r1", "r2"]},
        geometry=[
            LineString([(0, 0), (10, 0)]),
            LineString([(10, 0), (20, 0)]),  # Connects at (10, 0)
        ],
        crs=3857,
    )
    result = find_disconnected_segments(gdf, CONFIG)
    assert len(result) == 0


def test_self_intersection_simple():
    """Simple line has no self-intersection."""
    gdf = gpd.GeoDataFrame(
        {"road_id": ["r1"]},
        geometry=[LineString([(0, 0), (10, 0), (10, 10)])],
        crs=3857,
    )
    result = find_self_intersections(gdf, CONFIG)
    assert len(result) == 0


def test_self_intersection_crossing():
    """Figure-8 line has self-intersection."""
    # Create a self-crossing line
    gdf = gpd.GeoDataFrame(
        {"road_id": ["r1"]},
        geometry=[LineString([(0, 0), (10, 10), (10, 0), (0, 10)])],
        crs=3857,
    )
    result = find_self_intersections(gdf, CONFIG)
    assert len(result) == 1
    assert result.iloc[0]["error_type"] == "self_intersection"


def test_dangles_dead_end():
    """Single road has two dangles (both endpoints)."""
    gdf = gpd.GeoDataFrame(
        {"road_id": ["r1"]},
        geometry=[LineString([(0, 0), (10, 0)])],
        crs=3857,
    )
    result = find_dangles(gdf, CONFIG)
    assert len(result) == 2  # Both endpoints are dangles


def test_dangles_connected():
    """Connected roads have fewer dangles."""
    gdf = gpd.GeoDataFrame(
        {"road_id": ["r1", "r2"]},
        geometry=[
            LineString([(0, 0), (10, 0)]),
            LineString([(10, 0), (20, 0)]),
        ],
        crs=3857,
    )
    result = find_dangles(gdf, CONFIG)
    # Only outer endpoints are dangles: (0,0) and (20,0)
    assert len(result) == 2


def test_metrics_computation():
    """Metrics correctly count and rank errors."""
    errors = gpd.GeoDataFrame(
        {
            "road_id": ["r1", "r2", "r3", "r4", "r5"],
            "error_type": ["dangle", "dangle", "dangle", "disconnected_segment", "self_intersection"],
        },
        geometry=[Point(0, 0)] * 5,
        crs=3857,
    )
    metrics = compute_road_qc_metrics(errors)

    assert metrics["total_errors"] == 5
    assert metrics["error_counts"]["dangle"] == 3
    assert metrics["error_counts"]["disconnected_segment"] == 1
    assert metrics["top_3_errors"][0] == ("dangle", 3)


def test_merge_errors():
    """Merge errors combines multiple GeoDataFrames."""
    gdf1 = gpd.GeoDataFrame(
        {"road_id": ["r1"], "error_type": ["dangle"]},
        geometry=[Point(0, 0)],
        crs=3857,
    )
    gdf2 = gpd.GeoDataFrame(
        {"road_id": ["r2"], "error_type": ["self_intersection"]},
        geometry=[Point(10, 10)],
        crs=3857,
    )
    result = merge_errors(gdf1, gdf2)
    assert len(result) == 2
