"""Native desktop windows: the file dialogs and the start-up splash.

Both use Tk, which ships with Python on Windows and is bundled into
OVC.exe. A file dialog runs in a short-lived child process so Tk never
shares a thread with the HTTP server. When Tk or a display is missing
(a headless Linux server, the automated tests) every function reports
"not available" and the app falls back to its in-page file browser.
"""

from __future__ import annotations

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
    mode: str, title: str, initial_dir: str = "", initial_name: str = ""
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
        if req.get("mode") == "save":
            path = filedialog.asksaveasfilename(
                initialfile=req.get("initial_name") or "ovc_findings.gpkg",
                defaultextension=".gpkg",
                filetypes=SAVE_TYPES,
                confirmoverwrite=True,
                **options,
            )
        elif req.get("mode") == "test":  # packaging check: no dialog to click
            path = ""
        else:
            path = filedialog.askopenfilename(filetypes=OPEN_TYPES, **options)
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
