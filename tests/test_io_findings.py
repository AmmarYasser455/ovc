"""Reading layers with identity, the file-level API and exporting findings."""

import hashlib
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import box

from ovc import check_file
from ovc.sample_data import sample_path
from ovc.io import ExportError, LayerReadError, export_findings, list_layers, read_layer

SAMPLE = sample_path()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_list_layers_describes_the_sample():
    infos = {i.name: i for i in list_layers(SAMPLE)}
    assert set(infos) == {"buildings", "parcels", "block"}
    assert infos["buildings"].feature_count == 9
    assert infos["parcels"].feature_count == 8
    assert infos["block"].feature_count == 1
    assert infos["parcels"].crs.startswith("EPSG:32636")
    assert infos["parcels"].is_polygon and infos["parcels"].has_crs
    assert "parcel_ref" in infos["parcels"].fields


def test_read_layer_keeps_file_fids():
    gdf = read_layer(SAMPLE, "parcels")
    assert gdf.index.name == "fid"
    assert list(gdf.index) == list(range(1, 9))  # GeoPackage FIDs start at 1
    assert gdf.loc[2, "parcel_ref"] == "P2"


def test_unreadable_inputs_raise_layer_read_error(tmp_path):
    with pytest.raises(LayerReadError, match="File not found"):
        list_layers(tmp_path / "missing.gpkg")
    broken = tmp_path / "broken.gpkg"
    broken.write_bytes(b"this is not a geopackage")
    with pytest.raises(LayerReadError, match="Cannot read"):
        list_layers(broken)
    with pytest.raises(LayerReadError, match="Cannot read layer 'nope'"):
        read_layer(SAMPLE, "nope")


def test_unreadable_file_is_a_failed_run_not_zero_issues(tmp_path):
    broken = tmp_path / "broken.geojson"
    broken.write_text('{"type": "FeatureCollection", "features": [')
    r = check_file(broken)
    assert r.status == "failed"
    assert not r.ok
    assert "Cannot read" in r.message


def test_sample_buildings_expected_findings():
    r = check_file(SAMPLE, "buildings", id_field="bldg_ref")
    assert r.status == "issues"
    f = r.findings.set_index("issue_type")
    assert r.counts_by_type() == {"overlap": 1, "duplicate": 1, "containment": 1}
    assert (f.loc["overlap", "id_a"], f.loc["overlap", "id_b"]) == ("B1", "B2")
    assert f.loc["overlap", "area_m2"] == 16.0
    assert (f.loc["duplicate", "id_a"], f.loc["duplicate", "id_b"]) == ("B3", "B4")
    assert f.loc["duplicate", "area_m2"] == 100.0
    assert (f.loc["containment", "id_a"], f.loc["containment", "id_b"]) == ("B5", "B6")
    assert f.loc["containment", "area_m2"] == 9.0
    # B7's courtyard and the wall shared by B7 and B8 are not findings


def parcels_result():
    return check_file(
        SAMPLE,
        "parcels",
        check_gaps=True,
        coverage_path=SAMPLE,
        coverage_layer="block",
        id_field="parcel_ref",
    )


def test_export_and_reopen_geopackage(tmp_path):
    before = sha(SAMPLE)
    result = parcels_result()
    out = tmp_path / "findings.gpkg"
    done = export_findings(result, out, protect=[SAMPLE], source="sample | parcels")
    assert done["count"] == 2

    back = gpd.read_file(out, layer="ovc_findings").set_index("issue_type")
    assert back.crs.to_epsg() == 32636
    assert set(back.geometry.geom_type) == {"MultiPolygon"}
    # attributes
    assert (back.loc["overlap", "fid_a"], back.loc["overlap", "fid_b"]) == (2, 3)
    assert (back.loc["overlap", "id_a"], back.loc["overlap", "id_b"]) == ("P2", "P3")
    assert back.loc["overlap", "area_m2"] == 30.0
    assert back.loc["gap", "area_m2"] == 10.0
    assert back.loc["gap", "related_fids"] == "5, 7, 8"
    # geometry: the stored shapes have the stated areas and positions
    assert back.loc["overlap"].geometry.area == pytest.approx(30.0)
    assert back.loc["gap"].geometry.equals(box(330_040, 3_320_030, 330_041, 3_320_040))

    summary = gpd.read_file(out, layer="ovc_run_summary").set_index("item")["value"]
    assert summary["status"] == "issues"
    assert summary["area_unit"] == "square metres"
    assert summary["source"] == "sample | parcels"
    assert sha(SAMPLE) == before  # the source is untouched


def test_export_filter_and_geojson_in_wgs84(tmp_path):
    result = parcels_result()
    out = tmp_path / "gaps.geojson"
    done = export_findings(result, out, issue_types=["gap"])
    assert done["count"] == 1
    back = gpd.read_file(out)
    assert back.crs.to_epsg() == 4326
    assert list(back["issue_type"]) == ["gap"]
    assert back["area_m2"].iloc[0] == 10.0
    assert back.to_crs(32636).geometry.area.iloc[0] == pytest.approx(10.0, abs=1e-3)


def test_export_never_writes_to_inputs_or_silently_replaces(tmp_path):
    result = parcels_result()
    copy = tmp_path / "copy.gpkg"
    copy.write_bytes(SAMPLE.read_bytes())
    with pytest.raises(ExportError, match="input files"):
        export_findings(result, copy, overwrite=True, protect=[copy])
    assert sha(copy) == sha(SAMPLE)

    out = tmp_path / "f.gpkg"
    export_findings(result, out)
    with pytest.raises(ExportError, match="already exists"):
        export_findings(result, out)
    export_findings(result, out, overwrite=True)
    with pytest.raises(ExportError, match=".gpkg or .geojson"):
        export_findings(result, tmp_path / "f.shp")
    with pytest.raises(ExportError, match="no completed run"):
        export_findings(check_file(tmp_path / "missing.gpkg"), tmp_path / "x.gpkg")


def test_clean_run_exports_an_empty_layer_with_crs(tmp_path):
    gdf = gpd.GeoDataFrame(geometry=[box(0, 0, 1, 1), box(1, 0, 2, 1)], crs=32636)
    src = tmp_path / "clean.gpkg"
    gdf.to_file(src, driver="GPKG")
    result = check_file(src)
    assert result.status == "clean"
    out = tmp_path / "none.gpkg"
    export_findings(result, out)
    back = gpd.read_file(out, layer="ovc_findings")
    assert len(back) == 0
    assert back.crs.to_epsg() == 32636
