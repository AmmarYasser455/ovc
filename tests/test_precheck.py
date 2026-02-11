"""Tests for the GeoQA pre-check integration."""

from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point, Polygon

from ovc.precheck.runner import (
    PrecheckResult,
    PrecheckSummary,
    precheck_buildings,
    precheck_roads,
    precheck_boundary,
    precheck_all,
    _run_geoqa_profile,
)


@pytest.fixture
def buildings_shp(tmp_path):
    """Create a temporary buildings shapefile."""
    polys = [
        Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
        Polygon([(2, 0), (3, 0), (3, 1), (2, 1)]),
        Polygon([(4, 0), (5, 0), (5, 1), (4, 1)]),
    ]
    gdf = gpd.GeoDataFrame(
        {"name": ["a", "b", "c"], "area_m2": [100, 200, 150]},
        geometry=polys,
        crs="EPSG:4326",
    )
    path = tmp_path / "buildings.shp"
    gdf.to_file(path)
    return path


@pytest.fixture
def roads_shp(tmp_path):
    """Create a temporary roads shapefile."""
    lines = [
        LineString([(0, 0), (5, 0)]),
        LineString([(0, 1), (5, 1)]),
    ]
    gdf = gpd.GeoDataFrame(
        {"name": ["road1", "road2"]},
        geometry=lines,
        crs="EPSG:4326",
    )
    path = tmp_path / "roads.shp"
    gdf.to_file(path)
    return path


@pytest.fixture
def boundary_shp(tmp_path):
    """Create a temporary boundary shapefile."""
    poly = Polygon([(-1, -1), (6, -1), (6, 6), (-1, 6)])
    gdf = gpd.GeoDataFrame(geometry=[poly], crs="EPSG:4326")
    path = tmp_path / "boundary.shp"
    gdf.to_file(path)
    return path


@pytest.fixture
def bad_buildings_shp(tmp_path):
    """Create buildings with issues: invalid geometry, no CRS."""
    polys = [
        Polygon([(0, 0), (2, 0), (0, 2), (2, 2)]),  # bowtie (invalid)
        Polygon([(3, 0), (4, 0), (4, 1), (3, 1)]),
    ]
    gdf = gpd.GeoDataFrame(
        {"name": ["bad", "ok"]},
        geometry=polys,
    )
    # Intentionally no CRS
    path = tmp_path / "bad_buildings.shp"
    gdf.to_file(path)
    return path


class TestPrecheckResult:
    def test_defaults(self):
        r = PrecheckResult(dataset_name="test")
        assert r.quality_score == 0.0
        assert r.is_ready is False  # no CRS, 0 features → would be blocker
        assert not r.has_blockers  # but empty blockers list by default

    def test_has_blockers(self):
        r = PrecheckResult(dataset_name="test")
        r.blockers.append("No CRS")
        assert r.has_blockers is True
        assert r.is_ready is False


class TestPrecheckBuildings:
    def test_valid_buildings(self, buildings_shp, tmp_path):
        result = precheck_buildings(buildings_shp, out_dir=tmp_path)
        assert isinstance(result, PrecheckResult)
        assert result.dataset_name == "buildings"
        assert result.feature_count == 3
        assert result.quality_score > 0
        assert result.is_ready is True
        assert result.geometry_type == "Polygon"
        assert result.crs is not None
        assert result.report_path is not None
        assert result.report_path.exists()

    def test_bad_buildings_blocked(self, bad_buildings_shp, tmp_path):
        result = precheck_buildings(bad_buildings_shp, out_dir=tmp_path)
        assert result.has_blockers  # no CRS = blocker
        assert result.is_ready is False
        assert any("CRS" in b for b in result.blockers)


class TestPrecheckRoads:
    def test_valid_roads(self, roads_shp, tmp_path):
        result = precheck_roads(roads_shp, out_dir=tmp_path)
        assert result.is_ready is True
        assert result.geometry_type == "LineString"
        assert result.feature_count == 2

    def test_wrong_geometry_type(self, buildings_shp, tmp_path):
        """Passing polygon data as roads should add a blocker."""
        result = precheck_roads(buildings_shp, out_dir=tmp_path)
        assert result.has_blockers
        assert any("LineString" in b for b in result.blockers)


class TestPrecheckBoundary:
    def test_valid_boundary(self, boundary_shp, tmp_path):
        result = precheck_boundary(boundary_shp, out_dir=tmp_path)
        assert result.is_ready is True
        assert result.feature_count == 1

    def test_multi_feature_warning(self, buildings_shp, tmp_path):
        """Boundary with many features should warn."""
        result = precheck_boundary(buildings_shp, out_dir=tmp_path)
        # 3 features in buildings = should not trigger (threshold is >10)
        assert result.is_ready is True


class TestPrecheckAll:
    def test_all_valid(self, buildings_shp, roads_shp, boundary_shp, tmp_path):
        summary = precheck_all(
            buildings_path=buildings_shp,
            roads_path=roads_shp,
            boundary_path=boundary_shp,
            out_dir=tmp_path,
        )
        assert isinstance(summary, PrecheckSummary)
        assert summary.overall_ready is True
        assert summary.buildings is not None
        assert summary.roads is not None
        assert summary.boundary is not None
        assert len(summary.all_results) == 3

    def test_partial_datasets(self, buildings_shp, tmp_path):
        summary = precheck_all(
            buildings_path=buildings_shp,
            out_dir=tmp_path,
        )
        assert summary.overall_ready is True
        assert summary.buildings is not None
        assert summary.roads is None
        assert summary.boundary is None

    def test_with_bad_data(self, bad_buildings_shp, roads_shp, tmp_path):
        summary = precheck_all(
            buildings_path=bad_buildings_shp,
            roads_path=roads_shp,
            out_dir=tmp_path,
        )
        assert summary.overall_ready is False
        assert summary.buildings.has_blockers

    def test_nonexistent_file(self, tmp_path):
        result = precheck_buildings(
            tmp_path / "nonexistent.shp",
            out_dir=tmp_path,
        )
        assert result.has_blockers
        assert any("Failed to load" in b for b in result.blockers)
