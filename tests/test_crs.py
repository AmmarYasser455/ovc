"""Tests for CRS validation in ovc.core.crs."""

import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon

from ovc.core.crs import choose_utm_crs_from_gdf, ensure_wgs84, get_crs_pair


class TestEnsureWgs84:
    """Tests for ensure_wgs84 — the central CRS gate."""

    def test_raises_on_no_crs(self):
        """ensure_wgs84 must raise ValueError when CRS is None."""
        gdf = gpd.GeoDataFrame(
            {"val": [1]},
            geometry=[Point(31.0, 30.0)],
        )
        assert gdf.crs is None
        with pytest.raises(ValueError, match="no CRS defined"):
            ensure_wgs84(gdf)

    def test_valid_projected_crs_reprojected(self):
        """Data in a projected CRS should be reprojected to EPSG:4326."""
        gdf = gpd.GeoDataFrame(
            {"val": [1]},
            geometry=[Point(500_000, 3_300_000)],
            crs="EPSG:32636",  # UTM zone 36N
        )
        result = ensure_wgs84(gdf)
        assert result.crs is not None
        assert result.crs.to_epsg() == 4326

    def test_already_wgs84(self):
        """Data already in EPSG:4326 should pass through unchanged."""
        gdf = gpd.GeoDataFrame(
            {"val": [1]},
            geometry=[Point(31.0, 30.0)],
            crs="EPSG:4326",
        )
        result = ensure_wgs84(gdf)
        assert result.crs.to_epsg() == 4326
        assert float(result.geometry.iloc[0].x) == pytest.approx(31.0, abs=1e-6)

    def test_web_mercator_reprojected(self):
        """EPSG:3857 (Web Mercator) should be reprojected to 4326."""
        gdf = gpd.GeoDataFrame(
            {"val": [1]},
            geometry=[Point(0, 0)],
            crs="EPSG:3857",
        )
        result = ensure_wgs84(gdf)
        assert result.crs.to_epsg() == 4326


class TestChooseUtmCrs:
    """Tests for choose_utm_crs_from_gdf."""

    def test_egypt_utm_zone(self):
        """Data near Cairo should get UTM zone 36N."""
        gdf = gpd.GeoDataFrame(
            geometry=[Point(31.2, 30.0)],
            crs="EPSG:4326",
        )
        utm = choose_utm_crs_from_gdf(gdf)
        assert utm.to_epsg() == 32636

    def test_empty_gdf_fallback(self):
        """Empty GDF should return Web Mercator fallback."""
        gdf = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        utm = choose_utm_crs_from_gdf(gdf)
        assert utm.to_epsg() == 3857

    def test_none_gdf_fallback(self):
        """None input should return Web Mercator fallback."""
        utm = choose_utm_crs_from_gdf(None)
        assert utm.to_epsg() == 3857


class TestGetCrsPair:
    """Tests for get_crs_pair."""

    def test_returns_wgs84_and_utm(self):
        gdf = gpd.GeoDataFrame(
            geometry=[Polygon([(31, 30), (31.1, 30), (31.1, 30.1), (31, 30.1)])],
            crs="EPSG:4326",
        )
        pair = get_crs_pair(gdf)
        assert pair.crs_wgs84.to_epsg() == 4326
        # UTM zone for lon=31 → zone 36
        assert pair.crs_metric.to_epsg() == 32636

    def test_raises_on_no_crs(self):
        """get_crs_pair should propagate the ValueError from ensure_wgs84."""
        gdf = gpd.GeoDataFrame(
            geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        )
        with pytest.raises(ValueError, match="no CRS defined"):
            get_crs_pair(gdf)
