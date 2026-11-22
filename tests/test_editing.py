"""Editing a layer: working copy, undo, merge, split, save with backup, export."""

import shutil

import geopandas as gpd
import pytest
from shapely.geometry import box, mapping

from ovc.app import project, settings
from ovc.app.server import AppState
from sample import SAMPLE

X0, Y0 = 330_000, 3_320_000


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    return tmp_path / "home"


@pytest.fixture()
def gpkg(tmp_path):
    copy = tmp_path / "data.gpkg"
    shutil.copy(SAMPLE, copy)
    return str(copy)


def to_map(geom):
    """A shape in EPSG:32636 as the map sends it (WGS 84 GeoJSON)."""
    return mapping(gpd.GeoSeries([geom], crs=32636).to_crs(4326).iloc[0])


def rect(a, b, c, d):
    return box(X0 + a, Y0 + b, X0 + c, Y0 + d)


def test_move_add_delete_and_undo(home, gpkg):
    state = AppState("t")
    assert state.edit_start(gpkg, "parcels")["count"] == 8
    # move P1 (FID 1) 100 m east
    moved = state.edit_op(
        gpkg,
        "parcels",
        {"op": "update", "fid": 1, "geometry": to_map(rect(100, 0, 120, 15))},
    )
    assert moved["dirty"] and moved["can_undo"] and moved["changed"][0]["fid"] == 1
    # the map, Select and the tools now read the edited copy
    layer = state.read(gpkg, "parcels")
    assert layer.loc[1].geometry.bounds[0] == pytest.approx(X0 + 100, abs=1e-3)
    added = state.edit_op(
        gpkg,
        "parcels",
        {
            "op": "add",
            "geometry": to_map(rect(200, 0, 210, 10)),
            "attributes": {"parcel_ref": "NEW"},
        },
    )
    new_fid = added["changed"][0]["fid"]
    assert new_fid == 9 and state.read(gpkg, "parcels").loc[9, "parcel_ref"] == "NEW"
    state.edit_op(gpkg, "parcels", {"op": "delete", "fids": [2]})
    assert 2 not in state.read(gpkg, "parcels").index
    state.edit_op(gpkg, "parcels", {"op": "undo"})
    assert 2 in state.read(gpkg, "parcels").index
    state.edit_op(gpkg, "parcels", {"op": "redo"})
    assert 2 not in state.read(gpkg, "parcels").index


def test_merge_and_split_are_exact(home, gpkg):
    state = AppState("t")
    state.edit_start(gpkg, "parcels")
    merged = state.edit_op(gpkg, "parcels", {"op": "merge", "fids": [1, 2]})
    assert merged["removed"] == [2]
    layer = state.read(gpkg, "parcels")
    assert layer.loc[1].geometry.area == pytest.approx(600.0)  # 20x15 + 20x15
    assert layer.loc[1, "parcel_ref"] == "P1"  # attributes of the first
    # split it again along x = 20
    cut = {
        "type": "LineString",
        "coordinates": [
            list(c)
            for c in gpd.GeoSeries.from_wkt(
                [f"LINESTRING ({X0+20} {Y0-5}, {X0+20} {Y0+20})"], crs=32636
            )
            .to_crs(4326)
            .iloc[0]
            .coords
        ],
    }
    split = state.edit_op(gpkg, "parcels", {"op": "split", "fids": [1], "line": cut})
    areas = sorted(
        round(state.read(gpkg, "parcels").loc[f["fid"]].geometry.area, 3)
        for f in split["changed"]
    )
    assert areas == [300.0, 300.0]
    with pytest.raises(Exception, match="all the way across"):
        miss = {"type": "LineString", "coordinates": [[0, 0], [0.0001, 0.0001]]}
        state.edit_op(gpkg, "parcels", {"op": "split", "fids": [3], "line": miss})


def test_save_writes_back_with_a_backup_and_keeps_other_layers(home, gpkg):
    state = AppState("t")
    state.edit_start(gpkg, "parcels")
    state.edit_op(gpkg, "parcels", {"op": "delete", "fids": [8]})
    result = state.edit_save(gpkg, "parcels")
    assert len(gpd.read_file(gpkg, layer="parcels")) == 7
    assert len(gpd.read_file(gpkg, layer="buildings")) == 9  # untouched
    assert len(gpd.read_file(result["backup"], layer="parcels")) == 8
    assert str(home) in result["backup"]
    # the session is over: the file is read again
    assert len(state.read(gpkg, "parcels")) == 7


def test_save_shapefile_and_export(home, tmp_path):
    shp = tmp_path / "parcels.shp"
    gpd.read_file(SAMPLE, layer="parcels").to_file(shp)
    state = AppState("t")
    state.edit_start(str(shp), "parcels")
    state.edit_op(str(shp), "parcels", {"op": "delete", "fids": [0]})
    out = tmp_path / "edited.geojson"
    state.export_layer(str(shp), "parcels", str(out))
    assert len(gpd.read_file(out)) == 7
    saved = state.edit_save(str(shp), "parcels")
    back = gpd.read_file(shp)
    assert len(back) == 7 and back.crs.to_epsg() == 32636
    assert len(gpd.read_file(saved["backup"])) == 8


def test_discard_drops_the_edits(home, gpkg):
    state = AppState("t")
    state.edit_start(gpkg, "parcels")
    state.edit_op(gpkg, "parcels", {"op": "delete", "fids": [1, 2]})
    state.edit_discard(gpkg, "parcels")
    assert len(state.read(gpkg, "parcels")) == 8
    assert len(gpd.read_file(gpkg, layer="parcels")) == 8


def test_select_by_box(gpkg):
    state = AppState("t")
    wgs = gpd.GeoSeries([rect(1, 1, 19, 14)], crs=32636).to_crs(4326).total_bounds
    picked = state.select(gpkg, "parcels", None, list(wgs))
    assert picked["fids"] == [1]
    assert picked["rows"][0]["parcel_ref"] == "P1"
    wgs = gpd.GeoSeries([rect(1, 1, 59, 14)], crs=32636).to_crs(4326).total_bounds
    assert state.select(gpkg, "parcels", None, list(wgs))["fids"] == [1, 2, 3]


def test_project_round_trip_and_moved_folder(home, tmp_path, gpkg):
    folder = tmp_path / "work"
    folder.mkdir()
    data = folder / "data.gpkg"
    shutil.copy(gpkg, data)
    saved = project.save(
        folder / "block12",
        {
            "layers": [{"path": str(data), "layer": "parcels", "color": "#123456"}],
            "basemap": "osm",
        },
    )
    assert saved.endswith("block12.ovcproj")
    moved = tmp_path / "moved"
    shutil.move(str(folder), moved)
    opened = project.open_project(moved / "block12.ovcproj")
    assert opened["layers"][0]["path"] == str((moved / "data.gpkg").resolve())
    assert opened["missing"] == [] and opened["basemap"] == "osm"
    with pytest.raises(project.ProjectError, match="not an OVC project"):
        (tmp_path / "x.ovcproj").write_text("{}")
        project.open_project(tmp_path / "x.ovcproj")


def test_settings_are_kept_and_unknown_keys_ignored(home):
    assert settings.load()["theme"] == "light"
    settings.update(
        {
            "theme": "dark",
            "basemap": "osm",
            "nonsense": 1,
            "shortcuts": {"measure": "M"},
        }
    )
    data = settings.load()
    assert (
        data["theme"] == "dark"
        and data["shortcuts"] == {"measure": "M"}
        and "nonsense" not in data
    )
    settings.update({"theme": 5})  # wrong type: ignored
    assert settings.load()["theme"] == "dark"
    for i in range(12):
        settings.remember_project(f"p{i}.ovcproj")
    assert settings.load()["recent_projects"][0] == "p11.ovcproj"
    assert len(settings.load()["recent_projects"]) == 10
