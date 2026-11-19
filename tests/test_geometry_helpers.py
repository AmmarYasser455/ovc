"""Tests for ovc.core.geometry helpers."""

import geopandas as gpd
from shapely.geometry import LineString, box

from ovc.core.geometry import clip_to_boundary, drop_empty_and_fix


def test_drop_empty_keeps_input_crs():
    gdf = gpd.GeoDataFrame(geometry=[], crs="EPSG:32636")
    assert drop_empty_and_fix(gdf).crs == gdf.crs


def test_drop_empty_all_null_keeps_crs():
    gdf = gpd.GeoDataFrame(geometry=[None], crs="EPSG:32636")
    assert drop_empty_and_fix(gdf).crs == gdf.crs


def test_clip_reprojects_boundary_to_data_crs():
    # Cairo area, roads in WGS84 (lon, lat); boundary given in UTM 36N.
    roads = gpd.GeoDataFrame(
        geometry=[LineString([(31.0, 30.05), (31.2, 30.05)])], crs="EPSG:4326"
    )
    boundary_4326 = gpd.GeoDataFrame(geometry=[box(31.05, 30.0, 31.1, 30.1)], crs=4326)
    boundary_utm = boundary_4326.to_crs("EPSG:32636")
    out = clip_to_boundary(roads, boundary_utm)
    assert len(out) == 1
    minx, _, maxx, _ = out.geometry.iloc[0].bounds
    assert abs(minx - 31.05) < 1e-6 and abs(maxx - 31.1) < 1e-6
