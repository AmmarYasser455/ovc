"""Tests for ovc.loaders.roads clipping behaviour."""

import geopandas as gpd
import pytest
from shapely.geometry import LineString, MultiPolygon, box

from ovc.loaders.roads import load_roads


def _write(tmp_path, lines):
    path = tmp_path / "roads.geojson"
    gdf = gpd.GeoDataFrame(
        {"name": list("abc")[: len(lines)]}, geometry=lines, crs=4326
    )
    gdf.to_file(path, driver="GeoJSON")
    return path


def test_point_only_clip_result_is_dropped(tmp_path):
    # Cairo area, (lon, lat); boundary is 31.20-31.22 E, 30.00-30.02 N
    boundary = gpd.GeoDataFrame(geometry=[box(31.20, 30.00, 31.22, 30.02)], crs=4326)
    inside = LineString([(31.19, 30.01), (31.21, 30.01)])
    touching = LineString([(31.22, 30.02), (31.23, 30.03)])  # shares a corner only
    out = load_roads(_write(tmp_path, [inside, touching]), boundary)
    assert len(out) == 1
    assert out.geometry.iloc[0].geom_type == "LineString"
    assert out.crs.to_epsg() == 4326


def test_mixed_collection_keeps_line_segment(tmp_path):
    # Two-part boundary; the road runs through part A and touches part B at a point.
    a = box(31.20, 30.00, 31.21, 30.01)
    b = box(31.22, 30.00, 31.23, 30.01)
    boundary = gpd.GeoDataFrame(geometry=[MultiPolygon([a, b])], crs=4326)
    road = LineString([(31.205, 30.005), (31.215, 30.005), (31.22, 30.01)])
    out = load_roads(_write(tmp_path, [road]), boundary)
    assert len(out) == 1
    geom = out.geometry.iloc[0]
    assert geom.geom_type in ("LineString", "MultiLineString")
    assert geom.length > 0
    assert abs(geom.bounds[0] - 31.205) < 1e-9


@pytest.mark.parametrize(
    "bad_path",
    [None, "", 123, {"a": 1}, float("nan"), ["roads.geojson"]],
)
def test_invalid_path_rejected(bad_path):
    with pytest.raises(TypeError):
        load_roads(bad_path)


@pytest.mark.parametrize(
    "bad_boundary",
    ["boundary.geojson", {"type": "Polygon"}, 5, float("nan"), [box(0, 0, 1, 1)]],
)
def test_invalid_boundary_rejected(tmp_path, bad_boundary):
    road = LineString([(31.19, 30.01), (31.21, 30.01)])
    with pytest.raises(TypeError):
        load_roads(_write(tmp_path, [road]), bad_boundary)


def test_empty_and_none_boundary_means_no_clip(tmp_path):
    road = LineString([(31.19, 30.01), (31.21, 30.01)])
    path = _write(tmp_path, [road])
    empty = gpd.GeoDataFrame(geometry=[], crs=4326)
    assert len(load_roads(path, None)) == 1
    assert len(load_roads(path, empty)) == 1


def test_geoseries_boundary_accepted(tmp_path):
    road = LineString([(31.19, 30.01), (31.21, 30.01)])
    boundary = gpd.GeoSeries([box(31.20, 30.00, 31.22, 30.02)], crs=4326)
    out = load_roads(_write(tmp_path, [road]), boundary)
    assert len(out) == 1
    assert abs(out.geometry.iloc[0].bounds[0] - 31.20) < 1e-9


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_roads(tmp_path / "nope.geojson")
