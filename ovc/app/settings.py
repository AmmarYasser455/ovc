"""The app's settings, kept in ``~/.ovc/settings.json``.

The page cannot keep them itself: OVC listens on a different port each
time, and a browser keeps saved data per port, so anything stored in the
page would be forgotten at the next start.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

DEFAULTS = {
    "check_for_updates": True,
    "theme": "light",
    "basemap": "none",  # none | osm | carto-light | carto-dark | topo | custom
    "custom_basemap_url": "",
    "shortcuts": {},  # command -> key, overriding the defaults in the page
    "docks": {},
    "last_dir": "",
    "recent_projects": [],
}
_lock = threading.Lock()


def path() -> Path:
    return Path.home() / ".ovc" / "settings.json"


def load() -> dict:
    data = dict(DEFAULTS)
    try:
        stored = json.loads(path().read_text(encoding="utf-8"))
        if isinstance(stored, dict):
            data.update({k: v for k, v in stored.items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass
    return data


def update(changes: dict) -> dict:
    """Merge known keys into the settings file; unknown keys are ignored."""
    with _lock:
        data = load()
        for key, value in (changes or {}).items():
            if key in DEFAULTS and isinstance(value, type(DEFAULTS[key])):
                data[key] = value
        target = path()
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(target)
        return data


def remember_project(project_path: str) -> list:
    recent = [p for p in load()["recent_projects"] if p != project_path]
    recent.insert(0, project_path)
    return update({"recent_projects": recent[:10]})["recent_projects"]
