"""Tests for ovc.loaders.boundaries."""

import geopandas as gpd
import pytest
from pyproj import Transformer
from shapely.geometry import LineString, Point, box

from ovc.loaders.boundaries import load_boundary_shapefile


def _write(tmp_path, geoms, crs=4326):
    path = tmp_path / "aoi.geojson"
    gpd.GeoDataFrame(geometry=geoms, crs=crs).to_file(path, driver="GeoJSON")
    return path


def test_non_polygon_features_ignored(tmp_path):
    # Cairo (lon, lat)
    path = _write(
        tmp_path,
        [box(31.20, 30.00, 31.22, 30.02), LineString([(31.2, 30.0), (31.3, 30.1)])],
    )
    res = load_boundary_shapefile(path)
    assert len(res.gdf_4326) == 1
    assert res.gdf_4326.geometry.iloc[0].geom_type == "Polygon"
    assert res.gdf_4326.crs.to_epsg() == 4326
    assert res.name == "aoi"


def test_line_only_boundary_rejected(tmp_path):
    path = _write(tmp_path, [LineString([(31.2, 30.0), (31.3, 30.1)]), Point(31.2, 30)])
    with pytest.raises(ValueError, match="no polygon"):
        load_boundary_shapefile(path)


def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_boundary_shapefile(tmp_path / "nope.geojson")


def test_projected_boundary_reprojected(tmp_path):
    # Cairo (31.2 E, 30.0 N) expressed in UTM 36N, then loaded back as (lon, lat)
    x, y = Transformer.from_crs(4326, 32636, always_xy=True).transform(31.2, 30.0)
    path = _write(tmp_path, [box(x - 500, y - 500, x + 500, y + 500)], crs=32636)
    b = load_boundary_shapefile(path).gdf_4326.total_bounds
    assert b[0] < 31.2 < b[2] and b[1] < 30.0 < b[3]
    assert b[2] - b[0] < 0.02
