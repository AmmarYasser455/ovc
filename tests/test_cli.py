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


def test_gui_falls_back_to_the_browser_without_an_app_browser(monkeypatch, tmp_path):
    import threading

    from ovc.app import native

    monkeypatch.setenv("OVC_NO_WINDOW", "1")
    assert native.window_available() is False
    monkeypatch.delenv("OVC_NO_WINDOW")
    monkeypatch.setenv("OVC_APP_BROWSER", str(tmp_path / "missing.exe"))
    assert native.find_app_browser() is None
    assert native.window_available() is False
    assert native.run_window("http://127.0.0.1:1/", threading.Event()) is False


def test_window_closes_when_the_app_stops(monkeypatch, tmp_path):
    """run_window starts the browser in app mode with its own profile and
    ends it when the app's stop event is set."""
    import sys
    import threading

    from ovc.app import native

    # a stand-in "browser": records its arguments and stays open
    log = tmp_path / "args.txt"
    fake = tmp_path / "browser.py"
    fake.write_text(
        "import sys, time, pathlib\n"
        f"pathlib.Path(r'{log}').write_text('\\n'.join(sys.argv[1:]))\n"
        "time.sleep(60)\n"
    )
    monkeypatch.setattr(native, "find_app_browser", lambda: sys.executable)
    monkeypatch.setenv("OVC_APP_BROWSER_ARGS", "")
    real_popen = native.subprocess.Popen
    monkeypatch.setattr(
        native.subprocess,
        "Popen",
        lambda cmd, **kw: real_popen([cmd[0], str(fake)] + cmd[1:], **kw),
    )
    stopped, ready = threading.Event(), threading.Event()
    threading.Timer(1.5, ready.set).start()
    threading.Timer(2.5, stopped.set).start()
    assert native.run_window("http://127.0.0.1:9/?t=abc", stopped, ready=ready) is True
    args = log.read_text().splitlines()
    assert args[0] == "--app=http://127.0.0.1:9/?t=abc&w=1"
    profile = next(a for a in args if a.startswith("--user-data-dir=")).split("=", 1)[1]
    assert "ovc-window-" in profile
    import os

    assert not os.path.exists(profile)  # the throw-away profile is removed
