import geopandas as gpd
from shapely.geometry import box

from ovc.checks.boundary_overlap import find_buildings_touching_boundary

# UTM zone 36N (EPSG:32636) covers Cairo (~31.2E, 30.0N)
UTM = "EPSG:32636"
# Cairo downtown in UTM 36N: roughly (E 334000, N 3322000)
X0, Y0 = 334000.0, 3322000.0


def _buildings(with_osmid=True):
    gdf = gpd.GeoDataFrame(
        {"bldg_id": [1, 2]},
        geometry=[
            box(X0 + 98, Y0 + 40, X0 + 102, Y0 + 44),  # straddles east edge
            box(X0 + 40, Y0 + 40, X0 + 44, Y0 + 44),  # well inside
        ],
        crs=UTM,
    )
    if with_osmid:
        gdf["osmid"] = ["a", "b"]
    return gdf


def _boundary(crs=UTM):
    g = gpd.GeoDataFrame(geometry=[box(X0, Y0, X0 + 100, Y0 + 100)], crs=UTM)
    return g.to_crs(crs)


def test_flags_building_on_boundary():
    out = find_buildings_touching_boundary(_buildings(), _boundary())
    assert out["bldg_id"].tolist() == [1]
    assert out["error_type"].iloc[0] == "building_boundary_overlap"


def test_works_without_osmid_column():
    out = find_buildings_touching_boundary(_buildings(False), _boundary())
    assert out["bldg_id"].tolist() == [1]
    assert "osmid" not in out.columns


def test_boundary_in_other_crs_is_reprojected():
    out = find_buildings_touching_boundary(_buildings(), _boundary("EPSG:4326"))
    assert out["bldg_id"].tolist() == [1]


def test_missing_crs_is_rejected():
    import pytest

    no_crs_boundary = _boundary().set_crs(None, allow_override=True)
    with pytest.raises(ValueError, match="CRS"):
        find_buildings_touching_boundary(_buildings(), no_crs_boundary)
    no_crs_buildings = _buildings().set_crs(None, allow_override=True)
    with pytest.raises(ValueError, match="CRS"):
        find_buildings_touching_boundary(no_crs_buildings, _boundary())
