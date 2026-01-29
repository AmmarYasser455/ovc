import geopandas as gpd
from shapely.geometry import Polygon
from ovc.checks.overlap import find_building_overlaps, OverlapThresholds

THRESHOLDS = OverlapThresholds(
    duplicate_ratio_min=0.95,
    partial_ratio_min=0.2,
    min_intersection_area_m2=0.5,
)


def test_overlap_duplicate():
    gdf = gpd.GeoDataFrame(
        {"bldg_id": [0, 1]},
        geometry=[
            Polygon([(0, 0), (2, 0), (2, 2), (0, 2)]),
            Polygon([(0, 0), (2, 0), (2, 2), (0, 2)]),
        ],
        crs=3857,
    )
    ov = find_building_overlaps(gdf, THRESHOLDS)
    assert len(ov) == 1
    assert ov.iloc[0]["overlap_type"] == "duplicate"


def test_overlap_partial():
    gdf = gpd.GeoDataFrame(
        {"bldg_id": [0, 1]},
        geometry=[
            Polygon([(0, 0), (2, 0), (2, 2), (0, 2)]),
            Polygon([(1, 1), (3, 1), (3, 3), (1, 3)]),
        ],
        crs=3857,
    )
    ov = find_building_overlaps(gdf, THRESHOLDS)
    assert len(ov) == 1
    assert ov.iloc[0]["overlap_type"] == "partial"


def test_no_overlap():
    gdf = gpd.GeoDataFrame(
        {"bldg_id": [0, 1]},
        geometry=[
            Polygon([(0, 0), (2, 0), (2, 2), (0, 2)]),
            Polygon([(3, 3), (5, 3), (5, 5), (3, 5)]),
        ],
        crs=3857,
    )
    ov = find_building_overlaps(gdf, THRESHOLDS)
    assert len(ov) == 0
