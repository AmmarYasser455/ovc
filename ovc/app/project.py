"""OVC project files (``.ovcproj``): the map as the analyst left it.

A project is JSON: the layers in drawing order with their symbology,
visibility and declared CRS, the map extent, the basemap and the last tool
used. Each layer path is stored absolute and relative to the project file,
so a project folder can be moved or shared and still open.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

FORMAT = 1
EXTENSION = ".ovcproj"


class ProjectError(Exception):
    """A project could not be saved or opened. The message is safe to show."""


def save(target, project: dict) -> str:
    from ovc import __version__

    target = Path(target)
    if target.suffix.lower() != EXTENSION:
        target = target.with_suffix(EXTENSION)
    if not target.parent.is_dir():
        raise ProjectError(f"Folder not found: {target.parent}")
    layers = []
    for layer in project.get("layers", []):
        entry = dict(layer)
        src = Path(entry.get("path", ""))
        try:
            entry["relpath"] = os.path.relpath(src, target.parent)
        except ValueError:  # another drive on Windows
            entry["relpath"] = None
        layers.append(entry)
    data = {
        "ovc_project": FORMAT,
        "saved_with": __version__,
        "saved": datetime.now().isoformat(timespec="seconds"),
        **{k: v for k, v in project.items() if k != "layers"},
        "layers": layers,
    }
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(target)
    return str(target)


def open_project(source) -> dict:
    source = Path(source)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ProjectError(f"Cannot open {source.name}: {exc.strerror or exc}") from exc
    except ValueError as exc:
        raise ProjectError(f"{source.name} is not an OVC project.") from exc
    if not isinstance(data, dict) or data.get("ovc_project") is None:
        raise ProjectError(f"{source.name} is not an OVC project.")
    if int(data["ovc_project"]) > FORMAT:
        raise ProjectError(
            f"{source.name} was saved by a newer OVC ({data.get('saved_with')}). Update OVC to open it."
        )
    missing = []
    for layer in data.get("layers", []):
        path = Path(layer.get("path", ""))
        if not path.exists() and layer.get("relpath"):
            moved = (source.parent / layer["relpath"]).resolve()
            if moved.exists():
                layer["path"] = str(moved)
                continue
        if not path.exists():
            missing.append(layer.get("path", ""))
    data["missing"] = missing
    data["path"] = str(source)
    return data
