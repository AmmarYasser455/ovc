"""Build the app's icon sprite from Lucide (https://lucide.dev, ISC licence).

    npm pack lucide-static@0.460.0 && tar xzf lucide-static-0.460.0.tgz
    python packaging/brand/make_icon_sprite.py package

Writes the <symbol> elements into ovc/app/static/index.html between the
``icons:start`` and ``icons:end`` markers (so icons work offline and appear
with the first paint) and copies Lucide's licence next to the vendored files.
"""

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "ovc" / "app" / "static" / "index.html"

# OVC icon id -> Lucide icon name
ICONS = {
    "add": "file-plus",
    "layers": "layers",
    "pan": "hand",
    "select": "mouse-pointer-2",
    "zoomin": "zoom-in",
    "zoomout": "zoom-out",
    "extent": "maximize",
    "zoomlayer": "scan",
    "zoomsel": "scan-search",
    "clear": "eraser",
    "trash": "trash-2",
    "undo": "undo-2",
    "export": "download",
    "run": "play",
    "close": "x",
    "info": "info",
    "caret": "chevron-right",
    "back": "arrow-left",
    "map": "map",
    "toolbox": "briefcase",
    "hammer": "hammer",
    "up": "arrow-up",
    "down": "arrow-down",
    "pane-left": "panel-left",
    "pane-right": "panel-right",
    "list": "list",
    "table": "table-2",
    "sun": "sun",
    "moon": "moon",
    "globe": "globe",
    "bug": "bug",
    "log": "file-text",
    "update": "refresh-cw",
    "search": "search",
    "folder": "folder-open",
    "palette": "palette",
    "properties": "settings-2",
    "upload": "upload",
    "help": "circle-help",
    "external": "external-link",
    "ruler": "ruler",
    "area": "land-plot",
    "select-rect": "square-dashed-mouse-pointer",
    "edit": "pencil",
    "save": "save",
    "discard": "circle-x",
    "redo": "redo-2",
    "polygon": "pentagon",
    "rectangle": "rectangle-horizontal",
    "circle": "circle",
    "line": "spline",
    "point": "map-pin",
    "move": "move",
    "rotate": "rotate-cw",
    "reshape": "pen-tool",
    "merge": "merge",
    "split": "scissors",
    "catalog": "folder-tree",
    "file": "file",
    "history": "history",
    "exit": "log-out",
    "export-layer": "file-output",
    "settings": "settings",
    "keyboard": "keyboard",
    "chevron-down": "chevron-down",
}


def main(package: Path) -> None:
    symbols = []
    for ovc_id, name in ICONS.items():
        svg = (package / "icons" / f"{name}.svg").read_text(encoding="utf-8")
        inner = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.S).group(1)
        inner = re.sub(r"\s*\n\s*", "", inner).strip()
        symbols.append(
            f'  <symbol id="i-{ovc_id}" viewBox="0 0 24 24">{inner}</symbol>'
        )
    page = PAGE.read_text(encoding="utf-8")
    block = (
        "<!-- icons:start (Lucide, ISC licence; see vendor/lucide/LICENSE) -->\n"
        + "\n".join(symbols)
        + "\n  <!-- icons:end -->"
    )
    page, n = re.subn(r"<!-- icons:start.*?<!-- icons:end -->", block, page, flags=re.S)
    if n != 1:
        sys.exit("icons:start / icons:end markers not found in index.html")
    PAGE.write_text(page, encoding="utf-8")
    vendor = ROOT / "ovc" / "app" / "static" / "vendor" / "lucide"
    vendor.mkdir(parents=True, exist_ok=True)
    shutil.copy(package / "LICENSE", vendor / "LICENSE")
    print(f"Wrote {len(symbols)} icons into {PAGE.name}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
