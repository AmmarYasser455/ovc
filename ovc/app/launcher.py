"""Start the OVC map app and open it in the default browser.

Entry points: the ``ovc-gui`` command installed with the package (a windowed
program on Windows, so no console opens), ``python -m ovc.app`` and the
``OVC.exe`` built by ``packaging/windows``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import secrets
import sys
import tempfile
import threading
import time
import traceback
import urllib.request
import webbrowser
from pathlib import Path


def _state_dir() -> Path:
    d = Path.home() / ".ovc"
    try:
        d.mkdir(exist_ok=True)
    except OSError:
        d = Path(tempfile.gettempdir())
    return d


def _instance_file() -> Path:
    return _state_dir() / "app-instance.json"


def _running_instance() -> str | None:
    """URL of an OVC app that is already running, if any."""
    try:
        info = json.loads(_instance_file().read_text(encoding="utf-8"))
        req = urllib.request.Request(
            f"http://127.0.0.1:{int(info['port'])}/api/ping",
            headers={"X-OVC-Token": info["token"]},
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=1.5) as resp:
            if json.loads(resp.read()).get("app") == "ovc":
                return f"http://127.0.0.1:{int(info['port'])}/?t={info['token']}"
    except Exception:
        pass
    return None


def _show_error(text: str) -> None:
    """Tell the analyst why OVC did not start, even without a console."""
    log = _state_dir() / "ovc-app.log"
    try:
        log.write_text(text, encoding="utf-8")
    except OSError:
        pass
    if sys.stderr is not None:
        print(text, file=sys.stderr)
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                None,
                f"OVC could not start.\n\n{text[-900:]}\n\nDetails: {log}",
                "OVC",
                0x10,
            )
        except Exception:
            pass


log = logging.getLogger("ovc.app.launcher")
WINDOW_START_TIMEOUT = 45.0  # seconds for the page to load in a new window
WINDOW_CLOSE_GRACE = 15.0  # seconds with no open window before OVC stops


def _sessions_dir() -> Path:
    return _state_dir() / "sessions"


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, int(pid))  # query limited info
        if not handle:
            return False
        code = ctypes.c_ulong()
        kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        kernel32.CloseHandle(handle)
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    return True


def previous_unclean_session() -> dict | None:
    """The last OVC run that ended without stopping normally, if any.

    Each run leaves a marker file while it runs and removes it when it
    stops. A marker whose process is gone means OVC was ended from outside
    (crash, Task Manager, antivirus) and the analyst should hear about it.
    """
    found = None
    for marker in _sessions_dir().glob("*.json"):
        try:
            info = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            info = {}
        if info.get("pid") and _pid_alive(info["pid"]):
            continue  # another OVC that is still running
        try:
            marker.unlink()
        except OSError:
            pass
        if not found or info.get("started", "") > found.get("started", ""):
            found = info
    return found


def _mark_session() -> Path | None:
    from datetime import datetime

    from ovc import __version__

    try:
        _sessions_dir().mkdir(parents=True, exist_ok=True)
        marker = _sessions_dir() / f"{os.getpid()}.json"
        marker.write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "version": __version__,
                    "started": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
            ),
            encoding="utf-8",
        )
        return marker
    except OSError:
        return None


def wait_for_windows_closed(state, grace: float = WINDOW_CLOSE_GRACE) -> str:
    """Block while at least one OVC window is open; return why it stopped.

    A window counts as open while its page holds ``/api/events``. The grace
    period covers a page reload and the moment a window is being opened.
    """
    while not state.shutdown.wait(1.0):
        with state.lock:
            clients = state.clients
            quiet_for = time.time() - state.clients_changed
        if clients == 0 and quiet_for > grace:
            log.info("Stopping: no OVC window open for %.0f s", quiet_for)
            return "closed"
    log.info("Stopping: Quit or update")
    return "quit"


def self_test(report_path: str | None = None) -> int:
    """Run the bundled sample through read, check, export and re-read.

    Used by the packaging checks to prove an installed or frozen copy has
    its data files and geospatial libraries. Returns 0 on success.
    """
    import geopandas as gpd

    from ovc.api import check_file
    from ovc.app.server import STATIC
    from ovc.sample_data import sample_path
    from ovc.io import export_findings, list_layers

    report: dict = {"ok": False}
    try:
        for name in (
            "index.html",
            "app.js",
            "toolbox.js",
            "app.css",
            "ovc.ico",
            "splash-logo.png",
            "vendor/leaflet/leaflet.js",
        ):
            target = STATIC
            for part in name.split("/"):
                target = target / part
            assert target.is_file(), f"missing app file: {name}"
        sample = sample_path()
        report["layers"] = [i.name for i in list_layers(sample)]
        result = check_file(
            sample,
            "parcels",
            check_gaps=True,
            coverage_path=sample,
            coverage_layer="block",
            id_field="parcel_ref",
        )
        report["status"] = result.status
        report["counts"] = result.counts_by_type()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "findings.gpkg"
            export_findings(result, out, protect=[sample])
            back = gpd.read_file(out, layer="ovc_findings")
            report["export_crs"] = back.crs.to_epsg()
            report["export_areas"] = sorted(round(a, 6) for a in back["area_m2"])
            # A shapefile, read and drawn the way the map does it.
            from ovc.app.server import AppState

            shp = Path(tmp) / "parcels.shp"
            gpd.read_file(sample, layer="parcels").to_file(shp)
            shp_info = list_layers(shp)[0]
            preview = AppState("self-test").features_geojson(str(shp), shp_info.name)
            report["shapefile"] = {
                "geometry": shp_info.geometry_type,
                "crs": shp_info.crs,
                "drawn": preview.meta["shown"],
            }
        report["ok"] = (
            report["counts"] == {"overlap": 1, "gap": 1}
            and report["export_crs"] == 32636
            and report["export_areas"] == [10.0, 30.0]
            and report["shapefile"]["drawn"] == 8
            and report["shapefile"]["crs"].startswith("EPSG:32636")
        )
    except Exception:
        report["error"] = traceback.format_exc()
    text = json.dumps(report, indent=2)
    if report_path:
        Path(report_path).write_text(text, encoding="utf-8")
    if sys.stdout is not None:
        print(text)
    return 0 if report["ok"] else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="ovc-gui", description="Open the OVC map app."
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Start the app without opening a window or a browser",
    )
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Open OVC in the default browser instead of its own window",
    )
    parser.add_argument(
        "--port", type=int, default=0, help="Port (default: any free port)"
    )
    parser.add_argument(
        "--idle-timeout",
        type=float,
        default=900.0,
        help="Seconds without an open OVC page before the app stops (default 900)",
    )
    parser.add_argument(
        "--self-test",
        nargs="?",
        const="",
        metavar="REPORT.json",
        help="Check the installation with the bundled sample and exit",
    )
    parser.add_argument("--pick", metavar="REQUEST.json", help=argparse.SUPPRESS)
    parser.add_argument("--splash-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--window-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--install-info", metavar="REPORT.json", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    from ovc.app import diagnostics, native

    if not (args.pick or args.install_info or args.self_test is not None):
        diagnostics.setup_logging()

    # OVC opens in its own window when it can; otherwise in the browser.
    windowed = args.window_test or (
        not args.no_browser and not args.browser and native.window_available()
    )

    if args.install_info:  # packaging check: how this copy was installed
        from ovc import __version__
        from ovc.app import updates

        Path(args.install_info).write_text(
            json.dumps({"version": __version__, "kind": updates.install_kind()}),
            encoding="utf-8",
        )
        return 0
    if args.pick:  # child process showing one native file dialog
        from ovc.app.native import run_picker

        return run_picker(args.pick)
    if args.splash_test:  # packaging check: the splash window opens and closes
        from ovc.app.native import show_splash

        return 0 if show_splash(lambda: True, min_seconds=1.0) else 1
    if args.self_test is not None:
        return self_test(args.self_test or None)

    try:
        if not args.port and not windowed:
            existing = _running_instance()
            if existing:
                if not args.no_browser:
                    webbrowser.open(existing)
                if sys.stdout is not None:
                    print(existing, flush=True)
                return 0

        # Loading the geospatial libraries takes a few seconds: do it in the
        # background and show the splash window meanwhile.
        boot: dict = {}

        def start():
            try:
                from ovc.app.server import AppServer, AppState

                state = AppState(
                    secrets.token_urlsafe(24), idle_timeout=args.idle_timeout
                )
                boot["server"] = AppServer(args.port, state)
            except Exception:
                boot["error"] = traceback.format_exc()

        worker = threading.Thread(target=start, name="ovc-boot", daemon=True)
        worker.start()
        if (
            not args.no_browser
            and not args.window_test
            and not os.environ.get("OVC_NO_SPLASH")
        ):
            from ovc.app.native import show_splash

            show_splash(lambda: not worker.is_alive())
        worker.join()
        if "error" in boot:
            log.error("Start-up failed:\n%s", boot["error"])
            _show_error(boot["error"])
            return 1
        from ovc.app.server import serve

        server = boot["server"]
        state = server.state
        state.in_window = windowed
        state.previous_session = previous_unclean_session()
        if state.previous_session:
            log.warning(
                "The previous OVC run did not stop normally: %s", state.previous_session
            )
        session_marker = _mark_session()
        log.info(
            "OVC %s started (%s), %s",
            diagnostics.environment()["version"],
            diagnostics.environment()["install"],
            "own window" if windowed else "browser tab",
        )
    except Exception:
        _show_error(traceback.format_exc())
        return 1

    instance = _instance_file()
    try:
        instance.write_text(
            json.dumps(
                {
                    "port": server.server_address[1],
                    "token": state.token,
                    "pid": os.getpid(),
                }
            ),
            encoding="utf-8",
        )
    except OSError:
        instance = None
    if sys.stdout is not None:
        print(server.url, flush=True)
    result = 0
    try:
        if windowed:
            # The window's lifetime is the app's: no idle shutdown.
            state.idle_timeout = float("inf")
            serving = threading.Thread(
                target=serve, args=(server,), name="ovc-serve", daemon=True
            )
            serving.start()
            process = native.open_window(server.url)
            log.info("Window: %s", "opened" if process else "no app browser found")
            shown = process is not None and state.window_ready.wait(
                WINDOW_START_TIMEOUT
            )
            if args.window_test:
                result = 0 if shown else 1
                log.info(
                    "Window test: %s", "page loaded" if shown else "page never loaded"
                )
            elif not shown:
                # No usable window: fall back to a browser tab.
                log.warning("The app window did not load; opening a browser tab")
                state.idle_timeout = args.idle_timeout
                state.last_seen = time.time()
                webbrowser.open(server.url)
                serving.join()  # until Quit or the idle timeout
            else:
                wait_for_windows_closed(state)
            state.shutdown.set()  # open pages close their windows
            serving.join(timeout=5)
            native.close_window(process)
        else:
            if not args.no_browser:
                webbrowser.open(server.url)
            serve(server)
    finally:
        for marker in (instance, session_marker):
            if marker is not None:
                try:
                    marker.unlink()
                except OSError:
                    pass
        log.info("OVC stopped normally")
    return result


if __name__ == "__main__":
    sys.exit(main())
