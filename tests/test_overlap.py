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


def test_keep_polygonal_geometry_collection():
    from shapely.geometry import GeometryCollection, LineString, Point
    from ovc.checks.overlap import _keep_polygonal

    poly = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
    gc = GeometryCollection([LineString([(5, 5), (6, 6)]), poly, Point(9, 9)])
    assert _keep_polygonal(gc).equals(poly)
    assert _keep_polygonal(GeometryCollection([Point(0, 0)])) is None
    assert _keep_polygonal(GeometryCollection()) is None


def _overlaps(geoms):
    from shapely.geometry import box  # noqa: F401

    gdf = gpd.GeoDataFrame({"bldg_id": range(len(geoms))}, geometry=geoms, crs=32636)
    return find_building_overlaps(gdf, THRESHOLDS)


def test_overlap_area_counts_every_part_of_the_intersection():
    """A U-shaped building crossed by a bar overlaps it in two 3 m x 2 m parts.

    The whole 12 m² must be reported, not only the largest part.
    """
    from shapely.geometry import box

    u_shape = Polygon(
        [(0, 0), (10, 0), (10, 10), (7, 10), (7, 3), (3, 3), (3, 10), (0, 10)]
    )
    ov = _overlaps([u_shape, box(0, 8, 10, 12)])
    assert len(ov) == 1
    assert ov.iloc[0]["inter_area_m2"] == 12.0
    assert ov.iloc[0].geometry.geom_type == "MultiPolygon"


def test_building_inside_another_is_contained_not_duplicate():
    from shapely.geometry import box

    ov = _overlaps([box(0, 0, 20, 20), box(5, 5, 7, 7)])
    assert len(ov) == 1
    assert ov.iloc[0]["overlap_type"] == "contained"
    assert ov.iloc[0]["inter_area_m2"] == 4.0


def test_invalid_building_is_not_silently_dropped():
    """A self-intersecting polygon has zero signed area; it used to be dropped
    without a word, hiding its overlap with the square under it."""
    from shapely.geometry import box

    bowtie = Polygon([(0, 0), (10, 10), (10, 0), (0, 10)])
    ov = _overlaps([bowtie, box(0, 0, 10, 10)])
    assert len(ov) == 1
    assert ov.iloc[0]["inter_area_m2"] == 50.0


def test_shared_edge_and_shared_vertex_are_not_overlaps():
    from shapely.geometry import box

    assert len(_overlaps([box(0, 0, 4, 10), box(4, 0, 10, 10)])) == 0
    assert len(_overlaps([box(0, 0, 4, 4), box(4, 4, 8, 8)])) == 0


def test_each_pair_is_reported_once():
    from shapely.geometry import box

    ov = _overlaps([box(0, 0, 4, 4), box(2, 0, 6, 4), box(3, 0, 8, 4)])
    pairs = sorted(zip(ov["bldg_a"], ov["bldg_b"]))
    assert pairs == [(0, 1), (0, 2), (1, 2)]


def test_overlap_equal_to_the_threshold_is_reported():
    from shapely.geometry import box

    # 0.5 m x 1 m strip = exactly the 0.5 m² threshold
    ov = _overlaps([box(0, 0, 4, 1), box(3.5, 0, 8, 1)])
    assert len(ov) == 1
    assert ov.iloc[0]["inter_area_m2"] == 0.5
