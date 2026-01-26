from pathlib import Path

from ovc.export.pipeline import run_pipeline
from ovc.core.config import DEFAULT_CONFIG


def test_pipeline_runs_and_creates_outputs(tmp_path):
    """
    End-to-end smoke test for the OVC pipeline.
    Ensures the pipeline runs without errors and produces outputs.
    """

    # Arrange
    tests_dir = Path(__file__).parent
    boundary = tests_dir / "data" / "sample_boundary.geojson"
    out_dir = tmp_path / "outputs"

    # Act
    outputs = run_pipeline(
        boundary_path=boundary,
        out_dir=out_dir,
        config=DEFAULT_CONFIG,
    )

    # Assert
    assert outputs.gpkg_path.exists()
    assert outputs.metrics_csv.exists()
    assert outputs.webmap_html.exists()
