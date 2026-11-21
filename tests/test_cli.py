"""The ``ovc`` command: ``ovc check`` and the original pipeline options."""

from pathlib import Path

import geopandas as gpd
import pytest

from ovc.sample_data import sample_path
from ovc.cli import check_command, main

SAMPLE = str(sample_path())
DATA = Path(__file__).parent / "data"


def test_check_reports_issues_and_writes_findings(tmp_path, capsys):
    out = tmp_path / "findings.gpkg"
    code = check_command(
        [
            SAMPLE,
            "--layer",
            "parcels",
            "--gaps",
            "--coverage",
            SAMPLE,
            "--coverage-layer",
            "block",
            "--id-field",
            "parcel_ref",
            "--out",
            str(out),
        ]
    )
    assert code == 1
    text = capsys.readouterr().out
    assert "Status: ISSUES" in text and "gap: 1" in text and "overlap: 1" in text
    back = gpd.read_file(out, layer="ovc_findings")
    assert sorted(back["area_m2"]) == [10.0, 30.0]


def test_check_exit_codes(tmp_path, capsys):
    clean = tmp_path / "clean.gpkg"
    gpd.read_file(SAMPLE, layer="block").to_file(clean, driver="GPKG")
    assert check_command([str(clean)]) == 0
    assert check_command([SAMPLE, "--layer", "parcels", "--gaps"]) == 2  # no coverage
    assert "area that should be fully covered" in capsys.readouterr().out
    assert check_command([str(tmp_path / "missing.gpkg")]) == 3


def test_main_dispatches_check(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["check", SAMPLE, "--layer", "buildings"])
    assert exit_info.value.code == 1
    assert "duplicate: 1" in capsys.readouterr().out


def test_original_pipeline_options_still_work(tmp_path):
    main(
        ["--buildings", str(DATA / "sample_buildings.geojson"), "--out", str(tmp_path)]
    )
    assert (tmp_path / "building_qc" / "building_qc.gpkg").exists()


def test_public_python_api_is_unchanged():
    import ovc
    from ovc.checks import OverlapThresholds, find_building_overlaps  # noqa: F401
    from ovc.export.pipeline import run_pipeline

    assert ovc.run_pipeline is run_pipeline
    assert callable(ovc.find_duplicate_geometries)
    assert callable(ovc.check_file) and callable(ovc.check_polygons)
    with pytest.raises(AttributeError):
        ovc.nope


def test_version_has_a_single_source():
    from importlib.metadata import version

    import ovc

    assert version("ovc") == ovc.__version__


def test_every_issue_type_declares_check_label_and_colour():
    from ovc.engine import ISSUE_TYPES

    for name, (check, label, colour) in ISSUE_TYPES.items():
        assert check in {"overlap", "gap", "input"}, name
        assert label and colour.startswith("#") and len(colour) == 7, name


def test_gui_falls_back_to_the_browser_without_a_window_toolkit(monkeypatch):
    from ovc.app import native

    monkeypatch.setenv("OVC_NO_WINDOW", "1")
    assert native.window_available() is False
    monkeypatch.delenv("OVC_NO_WINDOW")
    monkeypatch.setitem(__import__("sys").modules, "webview", None)  # not installed
    assert native.window_available() is False
    import threading

    assert native.run_window("http://127.0.0.1:1/", threading.Event()) is False
