from pathlib import Path

from ovc.export.pipeline import run_pipeline
from ovc.core.config import DEFAULT_CONFIG


TESTS_DIR = Path(__file__).parent
BOUNDARY = TESTS_DIR / "data" / "sample_boundary.geojson"
BUILDINGS = TESTS_DIR / "data" / "sample_buildings.geojson"
ROADS = TESTS_DIR / "data" / "sample_roads.geojson"


def test_pipeline_buildings_only(tmp_path):
    """Pipeline runs with buildings only (no boundary, no roads)."""
    out_dir = tmp_path / "outputs"
    outputs = run_pipeline(
        buildings_path=BUILDINGS,
        out_dir=out_dir,
        config=DEFAULT_CONFIG,
    )
    assert outputs.gpkg_path.exists()
    assert outputs.metrics_csv.exists()
    assert outputs.webmap_html.exists()


def test_pipeline_with_boundary(tmp_path):
    """Pipeline runs with buildings and boundary."""
    out_dir = tmp_path / "outputs"
    outputs = run_pipeline(
        buildings_path=BUILDINGS,
        boundary_path=BOUNDARY,
        out_dir=out_dir,
        config=DEFAULT_CONFIG,
    )
    assert outputs.gpkg_path.exists()
    assert outputs.metrics_csv.exists()
    assert outputs.webmap_html.exists()


def test_pipeline_with_roads(tmp_path):
    """Pipeline runs with buildings and roads."""
    out_dir = tmp_path / "outputs"
    outputs = run_pipeline(
        buildings_path=BUILDINGS,
        roads_path=ROADS,
        out_dir=out_dir,
        config=DEFAULT_CONFIG,
    )
    assert outputs.gpkg_path.exists()
    assert outputs.metrics_csv.exists()
    assert outputs.webmap_html.exists()


def test_pipeline_full(tmp_path):
    """Pipeline runs with all inputs: buildings, roads, boundary."""
    out_dir = tmp_path / "outputs"
    outputs = run_pipeline(
        buildings_path=BUILDINGS,
        boundary_path=BOUNDARY,
        roads_path=ROADS,
        out_dir=out_dir,
        config=DEFAULT_CONFIG,
    )
    assert outputs.gpkg_path.exists()
    assert outputs.metrics_csv.exists()
    assert outputs.webmap_html.exists()
