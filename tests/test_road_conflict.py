import geopandas as gpd
from shapely.geometry import LineString, box

from ovc.checks.road_conflict import find_buildings_on_roads

# Metric coordinates in EPSG:32636 (UTM 36N, Cairo area); units are metres.
X0, Y0 = 311000.0, 3322000.0


def _buildings():
    return gpd.GeoDataFrame(
        {"bldg_id": [1]},
        geometry=[box(X0, Y0, X0 + 10, Y0 + 10)],
        crs=32636,
    )


def _roads(index):
    # First road is far away; second crosses the building.
    return gpd.GeoDataFrame(
        {"osmid": [100, 200]},
        geometry=[
            LineString([(X0 + 500, Y0), (X0 + 600, Y0)]),
            LineString([(X0 - 5, Y0 + 5), (X0 + 15, Y0 + 5)]),
        ],
        crs=32636,
        index=index,
    )


def test_conflict_with_default_index():
    out = find_buildings_on_roads(_buildings(), _roads([0, 1]), 1.0, 0.5)
    assert list(out["osmid"]) == [200]
    assert abs(out.iloc[0]["inter_area_m2"] - 20.0) < 1e-6


def test_conflict_with_non_default_index():
    # Index labels differ from row positions (e.g. after filtering).
    out = find_buildings_on_roads(_buildings(), _roads([7, 3]), 1.0, 0.5)
    assert list(out["osmid"]) == [200]
    assert abs(out.iloc[0]["inter_area_m2"] - 20.0) < 1e-6


def test_conflict_with_duplicate_index():
    out = find_buildings_on_roads(_buildings(), _roads([1, 1]), 1.0, 0.5)
    assert list(out["osmid"]) == [200]
    assert abs(out.iloc[0]["inter_area_m2"] - 20.0) < 1e-6
