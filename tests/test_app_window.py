"""OVC's own window: it must stay up exactly as long as a window is open.

Regression for "OVC is not running any more" on Windows: OVC used to stop
when the browser process it started exited, but Chromium-based browsers
(Edge, Chrome) can hand the window to another of their processes and exit.
"""

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from ovc.app import launcher, native
from ovc.app.server import AppServer, AppState

NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def test_no_app_browser_means_no_window(monkeypatch, tmp_path):
    monkeypatch.setenv("OVC_NO_WINDOW", "1")
    assert native.window_available() is False
    monkeypatch.delenv("OVC_NO_WINDOW")
    monkeypatch.setenv("OVC_APP_BROWSER", str(tmp_path / "missing.exe"))
    assert native.window_available() is False
    assert native.open_window("http://127.0.0.1:1/") is None


def test_window_is_a_plain_app_window(monkeypatch):
    """Like Edge's own "install as app": --app and nothing that looks like a
    program driving a browser in secret (private profile, --disable-...)."""
    started = {}

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            started["cmd"] = cmd

    monkeypatch.setattr(native, "find_app_browser", lambda: "msedge.exe")
    monkeypatch.setattr(native.subprocess, "Popen", FakePopen)
    monkeypatch.delenv("OVC_APP_BROWSER_ARGS", raising=False)
    native.open_window("http://127.0.0.1:5/?t=x")
    cmd = started["cmd"]
    assert cmd[1] == "--app=http://127.0.0.1:5/?t=x&w=1"
    assert not any(a.startswith(("--user-data-dir", "--disable")) for a in cmd)


def test_a_run_that_was_ended_from_outside_is_reported(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    sessions = launcher._sessions_dir()
    sessions.mkdir(parents=True)
    (sessions / "999999.json").write_text(
        json.dumps({"pid": 999999, "version": "3.7.0", "started": "2026-11-22 00:12"})
    )
    mine = launcher._mark_session()
    found = launcher.previous_unclean_session()
    assert found == {"pid": 999999, "version": "3.7.0", "started": "2026-11-22 00:12"}
    assert mine.exists()  # a running OVC is never reported
    assert launcher.previous_unclean_session() is None  # reported once


def _client_stream(server):
    """Open /api/events like a page does; returns the response."""
    port = server.server_address[1]
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/events?t={server.state.token}"
    )
    return NO_PROXY.open(req, timeout=10)


def test_event_stream_counts_open_windows_and_says_quit():
    server = AppServer(0, AppState("tok"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        stream = _client_stream(server)
        assert stream.headers["Content-Type"] == "text/event-stream"
        time.sleep(0.3)
        assert server.state.clients == 1
        server.state.shutdown.set()
        body = stream.read().decode()
        assert "event: quit" in body
        time.sleep(0.3)
        assert server.state.clients == 0
    finally:
        server.shutdown()
        server.server_close()


def test_wait_returns_only_after_the_last_window_closes():
    state = AppState("tok")
    state.clients = 1
    done = {}
    worker = threading.Thread(
        target=lambda: done.setdefault(
            "why", launcher.wait_for_windows_closed(state, grace=1.0)
        )
    )
    worker.start()
    time.sleep(2.5)
    assert worker.is_alive()  # a window is open: keep running
    with state.lock:
        state.clients = 0
        state.clients_changed = time.time()
    worker.join(timeout=5)
    assert done["why"] == "closed"

    state = AppState("tok")
    threading.Timer(0.5, state.shutdown.set).start()
    assert launcher.wait_for_windows_closed(state, grace=1.0) == "quit"


def _chromium():
    exe = os.environ.get("OVC_CHROMIUM")
    if exe:
        return exe
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            return p.chromium.executable_path
    except Exception:
        return None


@pytest.fixture()
def display():
    """A virtual X display for a real browser window (Linux CI)."""
    if os.environ.get("DISPLAY"):
        yield os.environ["DISPLAY"]
        return
    xvfb = shutil.which("Xvfb")
    if not xvfb or sys.platform != "linux":
        pytest.skip("needs Xvfb")
    number = f":{90 + os.getpid() % 9}"
    proc = subprocess.Popen([xvfb, number, "-screen", "0", "1440x900x24"])
    time.sleep(1.5)
    yield number
    proc.kill()


def _alive(url):
    port = url.split(":")[2].split("/")[0]
    token = url.split("t=")[1]
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/ping", headers={"X-OVC-Token": token}
    )
    try:
        with NO_PROXY.open(req, timeout=3) as resp:
            return json.loads(resp.read()).get("app") == "ovc"
    except Exception:
        return False


def test_ovc_survives_the_browser_handing_its_window_over(tmp_path, display):
    """The real bug, with a real Chromium: a browser already running on the
    analyst's profile receives OVC's window, so the process OVC starts exits
    at once. OVC must keep serving the open window, then stop once it closes."""
    exe = _chromium()
    if not exe or not Path(exe).exists():
        pytest.skip("Chromium is not available")
    home = tmp_path / "home"
    home.mkdir()
    env = dict(
        os.environ,
        HOME=str(home),
        USERPROFILE=str(home),
        DISPLAY=display,
        OVC_NO_UPDATE_CHECK="1",
        OVC_APP_BROWSER=exe,
        OVC_APP_BROWSER_ARGS="--no-sandbox",
        PYTHONUNBUFFERED="1",
    )
    first = subprocess.Popen(
        [
            exe,
            "--no-sandbox",
            "--no-first-run",
            "about:blank",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(3)
        ovc = subprocess.Popen(
            [sys.executable, "-m", "ovc.app"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        url = ovc.stdout.readline().strip()
        assert url.startswith("http://127.0.0.1:"), url
        # Past the close grace period: only a live window keeps OVC running.
        time.sleep(launcher.WINDOW_CLOSE_GRACE + 8)
        assert ovc.poll() is None, "OVC stopped while its window was open"
        assert _alive(url)

        first.terminate()  # the analyst closes the window
        first.wait(timeout=20)
        ovc.wait(timeout=launcher.WINDOW_CLOSE_GRACE + 20)
        assert ovc.returncode == 0
        log = (home / ".ovc" / "logs" / "ovc-app.log").read_text()
        assert "Stopping: no OVC window open" in log
    finally:
        for proc in (first, locals().get("ovc")):
            if proc is not None and proc.poll() is None:
                proc.kill()
