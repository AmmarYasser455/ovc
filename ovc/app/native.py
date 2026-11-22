"""Native desktop windows: the app window, file dialogs and start-up splash.

The app window is the installed browser (Microsoft Edge on Windows) in app
mode, showing the same page without tabs or an address bar. Nothing is
bundled for it. The dialogs and the splash use Tk, which ships with Python on Windows and is bundled into
OVC.exe. A file dialog runs in a short-lived child process so Tk never
shares a thread with the HTTP server. When Tk or a display is missing
(a headless Linux server, the automated tests) every function reports
"not available" and the app falls back to its in-page file browser.
"""

from __future__ import annotations

import gc
import json
import os
import subprocess
import sys
import tempfile
import time
from importlib import resources
from pathlib import Path

from ovc.app.branding import APP_NAME, APP_TITLE, FOUNDER, ORGANIZATION

INK, CREAM, ACCENT, MUTED = "#121417", "#f3eee4", "#f2552c", "#9aa0a6"
OPEN_TYPES = [
    ("Vector layers", "*.gpkg *.shp *.geojson *.json *.fgb *.gml *.kml"),
    ("GeoPackage", "*.gpkg"),
    ("Shapefile", "*.shp"),
    ("GeoJSON", "*.geojson *.json"),
    ("All files", "*.*"),
]
SAVE_TYPES = [("GeoPackage", "*.gpkg"), ("GeoJSON", "*.geojson")]
PROJECT_TYPES = [("OVC project", "*.ovcproj")]
LAYER_SAVE_TYPES = [
    ("GeoPackage", "*.gpkg"),
    ("Shapefile", "*.shp"),
    ("GeoJSON", "*.geojson"),
    ("FlatGeobuf", "*.fgb"),
]
TYPES = {
    # kind -> (open types, save types, default extension)
    "data": (OPEN_TYPES, SAVE_TYPES, ".gpkg"),
    "findings": (OPEN_TYPES, SAVE_TYPES, ".gpkg"),
    "layer": (OPEN_TYPES, LAYER_SAVE_TYPES, ".gpkg"),
    "project": (PROJECT_TYPES, PROJECT_TYPES, ".ovcproj"),
}
_UNAVAILABLE = 3  # exit code of the child when Tk cannot open a window


def _asset(name: str) -> str:
    return str(resources.files("ovc.app") / "static" / name)


def dialogs_enabled() -> bool:
    """True when native file dialogs should be tried."""
    if os.environ.get("OVC_NO_NATIVE_DIALOG"):
        return False
    if os.name != "nt" and not (
        os.environ.get("DISPLAY")
        or os.environ.get("WAYLAND_DISPLAY")
        or sys.platform == "darwin"
    ):
        return False
    try:
        import tkinter  # noqa: F401
    except Exception:
        return False
    return True


def _child_command(request_file: str) -> list[str]:
    if getattr(sys, "frozen", False):  # OVC.exe
        return [sys.executable, "--pick", request_file]
    return [sys.executable, "-m", "ovc.app", "--pick", request_file]


def pick_path(
    mode: str,
    title: str,
    initial_dir: str = "",
    initial_name: str = "",
    kind: str = "data",
) -> dict:
    """Ask the analyst for a file with the operating system's own dialog.

    Returns ``{"native": True, "path": str | None}`` (None when cancelled) or
    ``{"native": False}`` when no native dialog can be shown.
    """
    if not dialogs_enabled():
        return {"native": False}
    with tempfile.TemporaryDirectory() as tmp:
        request = Path(tmp) / "request.json"
        request.write_text(
            json.dumps(
                {
                    "mode": mode,
                    "title": title,
                    "initial_dir": initial_dir,
                    "initial_name": initial_name,
                    "kind": kind if kind in TYPES else "data",
                    "result": str(Path(tmp) / "result.json"),
                }
            ),
            encoding="utf-8",
        )
        try:
            done = subprocess.run(_child_command(str(request)), timeout=3600)
            if done.returncode != 0:
                return {"native": False}
            result = json.loads((Path(tmp) / "result.json").read_text(encoding="utf-8"))
        except Exception:
            return {"native": False}
    return {"native": True, "path": result.get("path") or None}


def _hidden_root():
    """An invisible, always-on-top Tk window to own a dialog."""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        root.iconbitmap(_asset("ovc.ico"))
    except Exception:
        pass
    root.attributes("-topmost", True)
    root.update()
    return root


def run_picker(request_file: str) -> int:
    """Child process: show one dialog and write the chosen path."""
    try:
        req = json.loads(Path(request_file).read_text(encoding="utf-8"))
        from tkinter import filedialog

        root = _hidden_root()
    except Exception:
        return _UNAVAILABLE
    try:
        options = {"parent": root, "title": req.get("title") or APP_NAME}
        if req.get("initial_dir") and Path(req["initial_dir"]).is_dir():
            options["initialdir"] = req["initial_dir"]
        open_types, save_types, default_ext = TYPES.get(req.get("kind"), TYPES["data"])
        if req.get("mode") == "save":
            path = filedialog.asksaveasfilename(
                initialfile=req.get("initial_name") or "ovc_findings.gpkg",
                defaultextension=default_ext,
                filetypes=save_types,
                confirmoverwrite=True,
                **options,
            )
        elif req.get("mode") == "test":  # packaging check: no dialog to click
            path = ""
        else:
            path = filedialog.askopenfilename(filetypes=open_types, **options)
        Path(req["result"]).write_text(
            json.dumps({"path": path or ""}), encoding="utf-8"
        )
        return 0
    finally:
        root.destroy()


def show_splash(is_ready, min_seconds: float = 1.6, max_seconds: float = 60.0) -> bool:
    """Show the start-up window until ``is_ready()`` is true.

    Returns False without showing anything when Tk is not available.
    """
    try:
        return _splash_window(is_ready, min_seconds, max_seconds)
    finally:
        # Free the window's Tk objects now, on this thread. Tk widgets hold
        # reference cycles, so otherwise the garbage collector frees them
        # later on whichever thread it runs, usually one reading a layer;
        # Tcl then stops the process ("async handler deleted by the wrong
        # thread", Windows fatal exception 0x80000003).
        gc.collect()


def _splash_window(is_ready, min_seconds: float, max_seconds: float) -> bool:
    try:
        import tkinter as tk

        root = tk.Tk()
    except Exception:
        return False
    try:
        from ovc import __version__

        width, height = 440, 250
        root.overrideredirect(True)
        root.configure(bg=INK)
        x = (root.winfo_screenwidth() - width) // 2
        y = (root.winfo_screenheight() - height) // 2
        root.geometry(f"{width}x{height}+{x}+{y}")
        root.attributes("-topmost", True)
        try:
            root.iconbitmap(_asset("ovc.ico"))
        except Exception:
            pass
        try:
            logo = tk.PhotoImage(file=_asset("splash-logo.png"))
            tk.Label(root, image=logo, bg=INK, bd=0).pack(pady=(34, 6))
            root._logo = logo  # keep a reference
        except Exception:
            tk.Label(
                root, text=APP_NAME, fg=CREAM, bg=INK, font=("Segoe UI", 34, "bold")
            ).pack(pady=(34, 6))
        tk.Label(root, text=APP_TITLE, fg=CREAM, bg=INK, font=("Segoe UI", 13)).pack()
        tk.Label(
            root, text=f"Version {__version__}", fg=MUTED, bg=INK, font=("Segoe UI", 9)
        ).pack(pady=(2, 14))
        tk.Label(
            root, text=ORGANIZATION, fg=ACCENT, bg=INK, font=("Segoe UI", 11, "bold")
        ).pack()
        tk.Label(
            root, text=f"Founded by {FOUNDER}", fg=CREAM, bg=INK, font=("Segoe UI", 9)
        ).pack()
        status = tk.Label(root, text="Loading…", fg=MUTED, bg=INK, font=("Segoe UI", 9))
        status.pack(side="bottom", pady=10)

        started = time.time()

        def poll():
            elapsed = time.time() - started
            if (is_ready() and elapsed >= min_seconds) or elapsed >= max_seconds:
                root.destroy()
            else:
                root.after(80, poll)

        root.after(80, poll)
        root.mainloop()
        return True
    except Exception:
        try:
            root.destroy()
        except Exception:
            pass
        return False


def find_app_browser() -> str | None:
    """A Chromium-based browser that can show a page as a plain app window.

    Microsoft Edge is part of Windows 10 and 11; Chrome is used when Edge is
    not found. ``OVC_APP_BROWSER`` overrides the search.
    """
    override = os.environ.get("OVC_APP_BROWSER")
    if override:
        return override if Path(override).is_file() else None
    candidates = []
    if os.name == "nt":
        roots = [
            os.environ.get("PROGRAMFILES(X86)"),
            os.environ.get("PROGRAMFILES"),
            os.environ.get("LOCALAPPDATA"),
        ]
        for root in [r for r in roots if r]:
            candidates.append(
                Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            )
        for root in [r for r in roots if r]:
            candidates.append(
                Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe"
            )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def window_available() -> bool:
    """True when OVC can open in its own desktop window."""
    if os.environ.get("OVC_NO_WINDOW"):
        return False
    return find_app_browser() is not None


def open_window(url: str):
    """Open OVC in its own window: the installed browser in app mode.

    This is exactly what Edge does for a site "installed as an app": the
    analyst's normal browser profile, ``--app`` and nothing else. No private
    profile folder and no ``--disable-...`` switches, which made Edge show
    first-run prompts and look like a program driving a browser in secret.

    Returns the started process, or None when no window can be opened. The
    process is not the window's lifetime: Edge usually hands the window to
    its already-running browser and exits. The launcher watches the page's
    event stream instead (see ``/api/events``).
    """
    exe = find_app_browser()
    if exe is None:
        return None
    command = [
        exe,
        "--app=" + url + ("&" if "?" in url else "?") + "w=1",
        "--window-size=1440,900",
    ] + os.environ.get("OVC_APP_BROWSER_ARGS", "").split()
    try:
        return subprocess.Popen(command)
    except Exception:
        return None


def close_window(process) -> None:
    """Stop the browser process OVC started, if it is still running."""
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except Exception:
        process.kill()
