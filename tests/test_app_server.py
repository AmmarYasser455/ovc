"""The map app's local server, driven over HTTP the way the browser does."""

import json
import os
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Polygon, box

from ovc.app.server import AppServer, AppState
from sample import SAMPLE as _SAMPLE

SAMPLE = str(_SAMPLE)
NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class Client:
    def __init__(self, server):
        self.base = f"http://127.0.0.1:{server.server_address[1]}"
        self.token = server.state.token

    def call(self, url, body=None, token=None, headers=None, **params):
        if params:
            url += "?" + urlencode(params)
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + url, data=data)
        req.add_header("X-OVC-Token", self.token if token is None else token)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with NO_PROXY.open(req, timeout=30) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as err:
            raw = err.read()
            try:
                return err.code, json.loads(raw)
            except ValueError:
                return err.code, {"raw": raw.decode()}

    def scan(self, **body):
        status, _ = self.call("/api/scan", body)
        assert status == 200
        for _ in range(400):
            _, job = self.call("/api/job")
            if job["state"] == "done":
                return job
            time.sleep(0.05)
        raise AssertionError("scan did not finish")


@pytest.fixture()
def client():
    server = AppServer(0, AppState("test-token"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield Client(server)
    server.shutdown()
    server.server_close()


def test_api_needs_the_launch_token_and_a_local_host(client):
    assert client.call("/api/config", token="wrong")[0] == 403
    assert client.call("/api/config", headers={"Host": "evil.example"})[0] == 403
    status, config = client.call("/api/config")
    assert status == 200
    assert "sample" not in config  # OVC ships no sample data in the app


def test_static_app_files_are_served(client):
    for path in ("/", "/static/app.js", "/static/vendor/leaflet/leaflet.js"):
        with NO_PROXY.open(client.base + path, timeout=10) as resp:
            assert resp.status == 200
            assert len(resp.read()) > 500
    assert client.call("/static/../server.py")[0] == 404


def test_browse_lists_folders_and_vector_files(client, tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "notes.txt").write_text("x")
    (tmp_path / "a.gpkg").write_bytes(b"")
    status, data = client.call("/api/browse", dir=str(tmp_path))
    assert status == 200
    assert [(e["name"], e["type"]) for e in data["entries"]] == [
        ("sub", "dir"),
        ("a.gpkg", "file"),
    ]
    assert data["parent"] == str(tmp_path.parent)
    assert client.call("/api/browse", dir=str(tmp_path / "nope"))[0] == 400


def test_layers_and_preview(client):
    _, data = client.call("/api/layers", path=SAMPLE)
    assert [layer["name"] for layer in data["layers"]] == [
        "buildings",
        "parcels",
        "block",
    ]
    _, preview = client.call("/api/preview", path=SAMPLE, layer="parcels")
    assert preview["shown"] == preview["total"] == 8
    west, south, east, north = preview["bounds"]
    assert 31.0 < west < east < 32.0 and 29.9 < south < north < 30.1  # WGS 84
    _, two = client.call("/api/features", path=SAMPLE, layer="parcels", fids="2,3")
    assert sorted(f["properties"]["fid"] for f in two["features"]) == [2, 3]


def test_scan_findings_and_export_roundtrip(client, tmp_path):
    job = client.scan(
        path=SAMPLE,
        layer="parcels",
        id_field="parcel_ref",
        check_overlaps=True,
        check_gaps=True,
        coverage={"path": SAMPLE, "layer": "block"},
    )
    summary = job["summary"]
    assert summary["status"] == "issues"
    assert summary["counts_by_type"] == {"overlap": 1, "gap": 1}
    assert job["export_default"].endswith("ovc_sample_parcels_ovc_findings.gpkg")

    _, findings = client.call("/api/findings")
    by_type = {f["properties"]["issue_type"]: f for f in findings["features"]}
    assert by_type["gap"]["properties"]["area_m2"] == 10.0
    assert by_type["overlap"]["properties"]["id_a"] == "P2"
    west, south, east, north = by_type["gap"]["bbox"]
    assert 31.0 < west <= east < 32.0  # zoom target is in WGS 84

    out = tmp_path / "out.gpkg"
    status, done = client.call(
        "/api/export", {"path": str(out), "issue_types": ["gap"]}
    )
    assert status == 200 and done["count"] == 1
    back = gpd.read_file(out, layer="ovc_findings")
    assert back.crs.to_epsg() == 32636
    assert list(back["area_m2"]) == [10.0]

    status, err = client.call("/api/export", {"path": str(out)})
    assert status == 400 and err["code"] == "exists"
    status, err = client.call("/api/export", {"path": SAMPLE, "overwrite": True})
    assert status == 400 and "never writes to its inputs" in err["error"]


def test_unreadable_file_reports_failure_not_zero_issues(client, tmp_path):
    broken = tmp_path / "broken.gpkg"
    broken.write_bytes(b"not a geopackage")
    status, err = client.call("/api/layers", path=str(broken))
    assert status == 400 and "Cannot read" in err["error"]
    job = client.scan(path=str(broken), check_overlaps=True)
    assert job["summary"]["status"] == "failed"
    assert "Cannot read" in job["summary"]["message"]
    status, _ = client.call("/api/export", {"path": str(tmp_path / "x.gpkg")})
    assert status == 400


def test_invalid_feature_gives_a_partial_run(client, tmp_path):
    src = tmp_path / "invalid.gpkg"
    bowtie = Polygon([(0, 0), (10, 10), (10, 0), (0, 10)])
    gpd.GeoDataFrame(geometry=[bowtie, box(0, 0, 10, 10)], crs=32636).to_file(
        src, driver="GPKG"
    )
    summary = client.scan(path=str(src), check_overlaps=True)["summary"]
    assert summary["status"] == "partial"
    assert summary["skipped_count"] == 1
    assert summary["checks"]["overlap"]["status"] == "incomplete"


def test_layer_without_crs_needs_a_declared_crs(client, tmp_path):
    # a shapefile without a .prj has no CRS
    shp = tmp_path / "nocrs.shp"
    gpd.GeoDataFrame(geometry=[box(0, 0, 4, 10), box(3, 0, 10, 10)]).to_file(shp)
    _, data = client.call("/api/layers", path=str(shp))
    assert data["layers"][0]["has_crs"] is False
    status, err = client.call("/api/preview", path=str(shp))
    assert status == 400 and err["code"] == "no_crs"
    assert client.scan(path=str(shp))["summary"]["status"] == "failed"
    job = client.scan(path=str(shp), assume_crs="EPSG:32636")
    assert job["summary"]["counts_by_type"] == {"overlap": 1}
    assert not Path(tmp_path / "nocrs.prj").exists()  # source left as it was


def test_identify_returns_the_feature_under_a_click(client):
    # centre of parcel P1 (0-20 m, 0-15 m of the block) in WGS 84
    import geopandas as gpd
    from shapely.geometry import Point

    lon, lat = (
        gpd.GeoSeries([Point(330_010, 3_320_007)], crs=32636)
        .to_crs(4326)
        .iloc[0]
        .coords[0]
    )
    status, hit = client.call(
        "/api/identify", path=SAMPLE, layer="parcels", lon=lon, lat=lat
    )
    assert status == 200
    assert hit["fid"] == 1 and hit["attributes"] == {"parcel_ref": "P1"}
    assert hit["feature"]["geometry"]["type"] == "Polygon"
    # an outline-only layer is hit on its edge, not in its interior
    _, inside = client.call(
        "/api/identify",
        path=SAMPLE,
        layer="block",
        lon=lon,
        lat=lat,
        tol=0.00001,
        edge="1",
    )
    assert inside["feature"] is None
    _, nothing = client.call(
        "/api/identify", path=SAMPLE, layer="parcels", lon=0, lat=0
    )
    assert nothing["feature"] is None


def test_export_leaves_out_dismissed_findings_and_keeps_notes(client, tmp_path):
    client.scan(
        path=SAMPLE,
        layer="parcels",
        check_gaps=True,
        coverage={"path": SAMPLE, "layer": "block"},
    )
    _, findings = client.call("/api/findings")
    gap_id = next(
        f["properties"]["finding_id"]
        for f in findings["features"]
        if f["properties"]["issue_type"] == "gap"
    )
    out = tmp_path / "kept.gpkg"
    status, done = client.call(
        "/api/export",
        {
            "path": str(out),
            "finding_ids": [gap_id],
            "notes": {str(gap_id): "survey again"},
        },
    )
    assert status == 200 and done["count"] == 1
    back = gpd.read_file(out, layer="ovc_findings")
    assert list(back["issue_type"]) == ["gap"]
    assert list(back["review_note"]) == ["survey again"]


def test_native_dialog_is_off_without_a_desktop(client, monkeypatch):
    monkeypatch.setenv("OVC_NO_NATIVE_DIALOG", "1")
    status, res = client.call("/api/pick", {"mode": "open", "title": "Add layer"})
    assert status == 200 and res == {"native": False}
    _, config = client.call("/api/config")
    assert config["native_dialog"] is False
    assert config["app"]["organization"] == "OpenTerra"
    assert config["app"]["founder"] == "Ammar Yasser"


def test_bug_report_and_log_endpoints(client, monkeypatch, tmp_path):
    monkeypatch.setenv("OVC_NO_OPEN_URL", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    status, info = client.call("/api/diagnostics")
    assert status == 200
    assert info["report_url"] == "https://github.com/AmmarYasser455/ovc/issues/new"
    assert {"version", "os", "install", "log", "log_path"} <= set(info)

    ok = "https://github.com/AmmarYasser455/ovc/issues/new?title=x"
    assert client.call("/api/open-url", {"url": ok}) == (200, {"opened": True})
    # anything that is not OVC's own GitHub page is refused
    status, err = client.call("/api/open-url", {"url": "https://example.com/"})
    assert status == 400 and "GitHub" in err["error"]

    status, res = client.call("/api/open-log", {})
    assert status == 200 and res["path"].endswith("ovc-app.log")


def test_unexpected_error_is_logged_and_reported_not_dropped(client, monkeypatch):
    from ovc.app import server as server_module

    def boom(*args, **kwargs):
        raise RuntimeError("unexpected while drawing")

    monkeypatch.setattr(server_module.AppState, "features_geojson", boom)
    status, err = client.call("/api/preview", path=SAMPLE, layer="parcels")
    assert status == 500
    assert "unexpected while drawing" in err["error"]


def test_dropped_files_are_copied_and_readable(client, tmp_path):
    import urllib.request as ur

    src = tmp_path / "parcels.geojson"
    gpd.read_file(SAMPLE, layer="parcels").to_file(src, driver="GeoJSON")
    req = ur.Request(
        client.base + "/api/upload?drop=abc123&name=parcels.geojson",
        data=src.read_bytes(),
        headers={
            "X-OVC-Token": client.token,
            "Content-Type": "application/octet-stream",
        },
    )
    with NO_PROXY.open(req, timeout=30) as resp:
        saved = json.loads(resp.read())["path"]
    assert "ovc-dropped" in saved and saved.endswith("parcels.geojson")
    _, data = client.call("/api/layers", path=saved)
    assert data["layers"][0]["feature_count"] == 8
    # a name with a path in it cannot write outside the drop folder
    req = ur.Request(
        client.base + "/api/upload?drop=abc123&name=..%2F..%2Fevil.txt",
        data=b"x",
        headers={"X-OVC-Token": client.token},
    )
    with NO_PROXY.open(req, timeout=30) as resp:
        assert json.loads(resp.read())["path"].endswith("abc123" + os.sep + "evil.txt")


def test_large_layers_are_drawn_simplified_but_checked_exactly(
    client, tmp_path, monkeypatch
):
    from ovc.app import server as server_module

    monkeypatch.setattr(server_module, "DISPLAY_VERTEX_BUDGET", 20)
    _, preview = client.call("/api/preview", path=SAMPLE, layer="parcels")
    assert preview["simplified"] is True and preview["shown"] == 8
    _, exact = client.call("/api/features", path=SAMPLE, layer="parcels", fids="1")
    assert exact["simplified"] is False  # the features behind a finding: exact


# ---- 4.0: settings, projects, measuring, selection, editing ------------


def _copy_sample(tmp_path):
    import shutil

    work = tmp_path / "work.gpkg"
    shutil.copy(SAMPLE, work)
    return str(work)


def test_settings_round_trip(client):
    _, before = client.call("/api/settings")
    assert before["basemap"] == "none"
    status, after = client.call(
        "/api/settings",
        {
            "basemap": "carto-light",
            "shortcuts": {"pan": "Ctrl+Shift+P"},
            "nonsense": 1,
            "theme": 5,
        },
    )
    assert status == 200
    assert after["basemap"] == "carto-light"
    assert after["shortcuts"] == {"pan": "Ctrl+Shift+P"}
    assert "nonsense" not in after and after["theme"] == "light"  # wrong type ignored
    assert client.call("/api/settings")[1]["basemap"] == "carto-light"


def test_project_save_refuses_to_overwrite_then_opens(client, tmp_path):
    project = {
        "basemap": "osm",
        "view": {"center": [30, 31], "zoom": 17},
        "layers": [
            {"path": SAMPLE, "layer": "parcels", "color": "#123456", "visible": True}
        ],
    }
    status, saved = client.call(
        "/api/project/save", {"path": str(tmp_path / "site"), "project": project}
    )
    assert status == 200 and saved["path"].endswith("site.ovcproj")
    assert saved["recent"][0] == saved["path"]
    again = client.call(
        "/api/project/save", {"path": saved["path"], "project": project}
    )
    assert again[0] == 400 and again[1]["code"] == "exists"
    assert (
        client.call(
            "/api/project/save",
            {"path": saved["path"], "project": project, "overwrite": True},
        )[0]
        == 200
    )

    _, opened = client.call("/api/project/open", {"path": saved["path"]})
    assert opened["layers"][0]["color"] == "#123456" and opened["missing"] == []
    assert opened["basemap"] == "osm"
    _, listing = client.call("/api/browse", dir=str(tmp_path), kind="project")
    assert [e["name"] for e in listing["entries"]] == ["site.ovcproj"]
    bad = tmp_path / "bad.ovcproj"
    bad.write_text("{}")
    assert client.call("/api/project/open", {"path": str(bad)})[0] == 400


def test_measure_is_geodesic(client):
    # 0.001 degrees of longitude at the equator is 111.32 m on WGS 84.
    _, line = client.call("/api/measure", {"coords": [[0, 0], [0.001, 0]]})
    assert line["length_m"] == pytest.approx(111.32, abs=0.01)
    _, area = client.call(
        "/api/measure",
        {"coords": [[0, 0], [0.001, 0], [0.001, 0.001], [0, 0.001]], "kind": "area"},
    )
    assert area["area_m2"] == pytest.approx(111.32 * 110.57, rel=1e-3)


def test_select_by_box_and_fids(client):
    _, preview = client.call("/api/preview", path=SAMPLE, layer="parcels")
    west, south, east, north = preview["bounds"]
    _, everything = client.call(
        "/api/select",
        {"path": SAMPLE, "layer": "parcels", "bbox": [west, south, east, north]},
    )
    assert len(everything["fids"]) == 8 and len(everything["rows"]) == 8
    _, two = client.call(
        "/api/select", {"path": SAMPLE, "layer": "parcels", "fids": [2, 3]}
    )
    assert two["fids"] == [2, 3]
    assert {r["parcel_ref"] for r in two["rows"]} == {"P2", "P3"}


def test_edit_session_over_http(client, tmp_path, _private_home):
    work = _copy_sample(tmp_path)
    target = {"path": work, "layer": "parcels"}
    _, status = client.call("/api/edit/start", target)
    assert (
        status["editing"]
        and status["count"] == 8
        and status["geometry_type"] == "Polygon"
    )
    _, two = client.call("/api/select", {**target, "fids": [2, 3]})
    merged = client.call(
        "/api/edit/op", {**target, "op": {"op": "merge", "fids": [2, 3]}}
    )[1]
    assert merged["count"] == 7 and merged["removed"] == [3]
    # the map and the checks read the working copy
    assert client.call("/api/preview", path=work, layer="parcels")[1]["total"] == 7
    shifted = {
        "type": "Polygon",
        "coordinates": [
            [[x + 0.00001, y] for x, y in ring]
            for ring in two["features"][0]["geometry"]["coordinates"]
        ],
    }
    moved = client.call(
        "/api/edit/op",
        {
            **target,
            "op": {"op": "update", "features": [{"fid": 2, "geometry": shifted}]},
        },
    )[1]
    assert moved["changed"][0]["fid"] == 2 and moved["can_undo"]
    assert (
        client.call(
            "/api/edit/op",
            {
                **target,
                "op": {
                    "op": "split",
                    "fids": [2],
                    "line": {"type": "LineString", "coordinates": [[0, 0], [0.1, 0.1]]},
                },
            },
        )[0]
        == 400
    )  # misses it

    _, saved = client.call("/api/edit/save", target)
    assert Path(saved["backup"]).exists()
    assert len(gpd.read_file(work, layer="parcels")) == 7
    assert len(gpd.read_file(work, layer="block")) == 1  # other layers kept
    assert len(gpd.read_file(saved["backup"], layer="parcels")) == 8

    out = tmp_path / "parcels.shp"
    assert client.call("/api/layer/export", {**target, "out": str(out)})[0] == 200
    assert len(gpd.read_file(out)) == 7
    exists = client.call("/api/layer/export", {**target, "out": str(out)})
    assert exists[0] == 400 and exists[1]["code"] == "exists"
    assert (
        client.call("/api/layer/export", {**target, "out": work})[0] == 400
    )  # use Save Edits
