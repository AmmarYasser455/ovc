import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SHOWCASE = ROOT / "showcase"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "make_showcase", SHOWCASE / "make_showcase.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("showcase_out")
    summary = _load_module().main(out_dir=out)
    return out, summary


def test_map_geojson_matches_committed(built):
    out, _ = built
    fresh = json.loads((out / "map.geojson").read_text(encoding="utf-8"))
    committed = json.loads((SHOWCASE / "map.geojson").read_text(encoding="utf-8"))
    assert fresh == committed


def test_map_geojson_is_lonlat_in_cairo(built):
    out, _ = built
    data = json.loads((out / "map.geojson").read_text(encoding="utf-8"))

    def walk(c):
        if isinstance(c[0], (int, float)):
            yield c
        else:
            for x in c:
                yield from walk(x)

    for feat in data["features"]:
        for lon, lat in walk(feat["geometry"]["coordinates"]):
            # Zamalek, Cairo is near 31.2 E, 30.06 N; a swapped axis fails here.
            assert 31.0 < lon < 31.5
            assert 29.9 < lat < 30.2


def test_summary_has_expected_findings(built):
    _, summary = built
    assert summary["buildings"] == 152
    assert summary["buildings_with_overlap"] == 2
    assert summary["buildings_on_road"] == 1
    assert summary["crs_metric"] == "EPSG:32636"


def test_html_written(built):
    out, _ = built
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "leaflet@1.9.4" in html and "map.geojson" in html


def test_notebook_executes_with_inline_image(tmp_path):
    nbformat = pytest.importorskip("nbformat")
    nbclient = pytest.importorskip("nbclient")
    pytest.importorskip("matplotlib")
    pytest.importorskip("ipykernel")
    nb = nbformat.read(SHOWCASE / "showcase.ipynb", as_version=4)
    # Run from the repository root; the notebook finds ovc/ and showcase/data.
    nbclient.NotebookClient(
        nb,
        timeout=300,
        kernel_name="python3",
        resources={"metadata": {"path": str(ROOT)}},
    ).execute()
    outputs = [o for c in nb.cells if c.cell_type == "code" for o in c.outputs]
    assert not [o for o in outputs if o.output_type == "error"]
    assert any("image/png" in o.get("data", {}) for o in outputs)
    text = "".join(o.get("text", "") for o in outputs if o.output_type == "stream")
    assert "152 buildings" in text


def test_map_png_produced(built):
    pytest.importorskip("matplotlib")
    out, _ = built
    png = out / "map.png"
    assert png.exists()
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
