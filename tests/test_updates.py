"""Update check and in-app install, against a fake release feed."""

import hashlib
import json
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from ovc import __version__
from ovc.app import updates


@pytest.fixture()
def feed(tmp_path, monkeypatch):
    """A local web server holding a release JSON, an installer and its checksum."""
    root = tmp_path / "www"
    root.mkdir()
    installer = b"MZ fake OVC installer " * 1000
    (root / "OVC-Setup.exe").write_bytes(installer)
    digest = hashlib.sha256(installer).hexdigest()
    (root / "OVC-Setup.exe.sha256").write_text(f"{digest}  OVC-Setup.exe")
    handler = partial(SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *a: None
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    def publish(tag, assets=True):
        release = {
            "tag_name": tag,
            "name": f"OVC {tag}",
            "html_url": f"{base}/release",
            "body": "What's new",
            "assets": (
                [
                    {
                        "name": "OVC-Setup.exe",
                        "browser_download_url": f"{base}/OVC-Setup.exe",
                    },
                    {
                        "name": "OVC-Setup.exe.sha256",
                        "browser_download_url": f"{base}/OVC-Setup.exe.sha256",
                    },
                ]
                if assets
                else []
            ),
        }
        (root / "latest.json").write_text(json.dumps(release))

    monkeypatch.setenv("OVC_UPDATE_FEED", f"{base}/latest.json")
    monkeypatch.delenv("OVC_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    publish("v99.0.0")
    yield {"publish": publish, "root": root, "base": base, "digest": digest}
    server.shutdown()
    server.server_close()


def test_parse_version():
    assert updates.parse_version("v3.6.0") == (3, 6, 0)
    assert updates.parse_version("3.10") == (3, 10, 0)
    assert updates.parse_version("v3.6.0-beta") is None
    assert updates.parse_version("v3.10.0") > updates.parse_version("v3.9.9")


def test_newer_release_is_reported(feed):
    info = updates.check()
    assert info["available"] is True
    assert info["latest"] == "99.0.0" and info["current"] == __version__
    assert info["kind"] == "python"  # running from source, not the installer
    assert info["can_install"] is False  # only an installed OVC updates itself
    assert info["download_url"].endswith("/OVC-Setup.exe")


def test_same_or_older_release_is_not_an_update(feed):
    feed["publish"]("v" + __version__)
    assert updates.check()["available"] is False
    feed["publish"]("v1.0.0")
    assert updates.check()["available"] is False


def test_unreachable_or_bad_feed_is_reported_not_raised(feed, monkeypatch):
    (feed["root"] / "latest.json").write_text("{not json")
    info = updates.check()
    assert info["available"] is False and "Could not reach" in info["error"]
    feed["publish"]("nightly")
    assert "unexpected tag" in updates.check()["error"]


def test_checks_can_be_turned_off(feed, monkeypatch):
    updates.set_checks_enabled(False)
    info = updates.check()
    assert info["enabled"] is False and info["latest"] is None  # nothing fetched
    assert updates.check(force=True)["available"] is True  # "Check now" still works
    updates.set_checks_enabled(True)
    monkeypatch.setenv("OVC_NO_UPDATE_CHECK", "1")
    assert updates.check()["latest"] is None


def test_only_github_https_is_trusted_without_a_test_feed(monkeypatch):
    monkeypatch.delenv("OVC_UPDATE_FEED", raising=False)
    with pytest.raises(updates.UpdateError):
        updates._check_url("http://github.com/x")
    with pytest.raises(updates.UpdateError):
        updates._check_url("https://example.com/OVC-Setup.exe")
    assert updates._check_url(updates.DOWNLOAD_URL) == updates.DOWNLOAD_URL


def test_installed_copy_can_install(feed, monkeypatch, tmp_path):
    app_dir = tmp_path / "Programs" / "OVC"
    app_dir.mkdir(parents=True)
    (app_dir / "OVC.exe").write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(app_dir / "OVC.exe"))
    monkeypatch.setattr(sys, "platform", "win32")
    assert updates.install_kind() == "portable"  # the zip: no uninstaller
    (app_dir / "unins000.exe").write_bytes(b"")
    assert updates.install_kind() == "installer"
    assert updates.check()["can_install"] is True
    feed["publish"]("v99.0.0", assets=False)  # a release without the installer
    assert updates.check()["can_install"] is False


def test_download_is_checked_against_the_published_checksum(feed):
    base = feed["base"]
    seen = []
    path = updates.download_installer(
        f"{base}/OVC-Setup.exe", f"{base}/OVC-Setup.exe.sha256", seen.append
    )
    assert hashlib.sha256(path.read_bytes()).hexdigest() == feed["digest"]
    assert seen and seen[-1] == 1.0

    (feed["root"] / "OVC-Setup.exe").write_bytes(b"tampered")
    with pytest.raises(updates.UpdateError, match="does not match"):
        updates.download_installer(
            f"{base}/OVC-Setup.exe", f"{base}/OVC-Setup.exe.sha256"
        )
    (feed["root"] / "OVC-Setup.exe.sha256").write_text("not a hash")
    with pytest.raises(updates.UpdateError, match="not a SHA-256"):
        updates.download_installer(
            f"{base}/OVC-Setup.exe", f"{base}/OVC-Setup.exe.sha256"
        )


def test_server_installs_the_update_and_closes(feed, monkeypatch):
    """The app downloads, verifies, starts the installer and shuts down."""
    from test_app_server import Client

    from ovc.app.server import AppServer, AppState

    launched = []
    monkeypatch.setattr(updates, "install_kind", lambda: "installer")
    monkeypatch.setattr(updates, "launch_installer", lambda p: launched.append(Path(p)))
    server = AppServer(0, AppState("tok"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        client = Client(server)
        status, info = client.call("/api/update")
        assert status == 200 and info["available"] and info["can_install"]
        status, _ = client.call("/api/update/install", {})
        assert status == 200
        for _ in range(100):
            _, job = client.call("/api/update/status")
            if job["state"] not in ("downloading", "launching"):
                break
            threading.Event().wait(0.05)
        assert job["state"] == "launched"
        assert len(launched) == 1
        assert hashlib.sha256(launched[0].read_bytes()).hexdigest() == feed["digest"]
        assert server.state.shutdown.wait(
            5
        )  # OVC closes so the installer can replace it
    finally:
        server.shutdown()
        server.server_close()


def test_server_refuses_to_install_into_a_non_installed_copy(feed):
    from test_app_server import Client

    from ovc.app.server import AppServer, AppState

    server = AppServer(0, AppState("tok"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        client = Client(server)
        status, err = client.call("/api/update/install", {})
        assert status == 400 and "cannot install updates" in err["error"]
        status, res = client.call("/api/update/settings", {"enabled": False})
        assert status == 200 and res == {"enabled": False}
    finally:
        server.shutdown()
        server.server_close()
