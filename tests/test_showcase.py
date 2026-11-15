"""The committed showcase must match what showcase/make_showcase.py produces."""

import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHOWCASE = ROOT / "showcase"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "ovc_showcase", SHOWCASE / "make_showcase.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _same(a, b, tol=1e-6):
    if isinstance(a, float) or isinstance(b, float):
        return isinstance(a, (int, float)) and math.isclose(a, b, abs_tol=tol)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k], tol) for k in a)
    return a == b


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("showcase")
    summary = _load_module().main(out_dir=out)
    return out, summary


def test_geojson_matches_committed(built):
    out, _ = built
    fresh = json.loads((out / "map.geojson").read_text(encoding="utf-8"))
    committed = json.loads((SHOWCASE / "map.geojson").read_text(encoding="utf-8"))
    assert _same(fresh, committed)


def test_result_is_lon_lat_in_cairo(built):
    out, summary = built
    data = json.loads((out / "map.geojson").read_text(encoding="utf-8"))
    lon, lat = data["features"][0]["geometry"]["coordinates"][0][0]
    # Downtown Cairo is near 31.24 E, 30.05 N; a swapped axis would fail here.
    assert 31.2 < lon < 31.3 and 30.0 < lat < 30.1
    flagged = [
        f
        for f in data["features"]
        if f["properties"]["layer"] == "building"
        and f["properties"]["qc_status"] == "on_road"
    ]
    assert len(flagged) == summary["buildings_on_roads"] > 0


def test_png_written(built):
    pytest.importorskip("matplotlib")
    out, _ = built
    png = out / "map.png"
    assert png.exists()
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def _outputs(nb):
    return [o for c in nb.cells if c.cell_type == "code" for o in c.get("outputs", [])]


def test_committed_notebook_has_saved_image():
    nbformat = pytest.importorskip("nbformat")
    nb = nbformat.read(SHOWCASE / "showcase.ipynb", as_version=4)
    outputs = _outputs(nb)
    assert not [o for o in outputs if o.get("output_type") == "error"]
    assert any("image/png" in o.get("data", {}) for o in outputs)


def test_notebook_executes(tmp_path, monkeypatch):
    nbformat = pytest.importorskip("nbformat")
    nbclient = pytest.importorskip("nbclient")
    pytest.importorskip("matplotlib")
    pytest.importorskip("ipykernel")
    # The kernel must use the inline backend so the map is captured as image/png.
    monkeypatch.delenv("MPLBACKEND", raising=False)
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "mpl"))
    # Execute an in-memory copy; the committed file is never modified.
    nb = nbformat.read(SHOWCASE / "showcase.ipynb", as_version=4)
    client = nbclient.NotebookClient(
        nb,
        timeout=300,
        kernel_name="python3",
        resources={"metadata": {"path": str(SHOWCASE)}},
    )
    client.execute()  # raises CellExecutionError on any failing cell
    outputs = _outputs(nb)
    assert not [o for o in outputs if o.get("output_type") == "error"]
    assert any("image/png" in o.get("data", {}) for o in outputs)
