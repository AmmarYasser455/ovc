"""The map app's local server, driven over HTTP the way the browser does."""

import json
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
from ovc.sample_data import sample_path

SAMPLE = str(sample_path())
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
    assert config["sample"] == SAMPLE


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
