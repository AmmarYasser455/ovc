"""Keep the GeoQA -> OVC walkthrough honest: its data must give the results it documents."""

from pathlib import Path

import geopandas as gpd
import pandas as pd

from ovc.core.config import DEFAULT_CONFIG
from ovc.export.pipeline import run_pipeline

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "geoqa-to-ovc"


def test_walkthrough_finds_documented_issues(tmp_path):
    outputs = run_pipeline(
        buildings_path=EXAMPLE / "buildings.geojson",
        roads_path=EXAMPLE / "roads.geojson",
        boundary_path=EXAMPLE / "boundary.geojson",
        out_dir=tmp_path,
        config=DEFAULT_CONFIG,
    )
    metrics = pd.read_csv(outputs.metrics_csv).set_index("metric")["value"]
    assert metrics["total_buildings"] == 8
    assert metrics["overlap_count"] == 1
    assert metrics["overlap_partial_count"] == 1
    assert 39 < metrics["overlap_total_area_m2"] < 41  # the 4 m x 10 m strip
    assert metrics["count_building_on_road"] == 1

    errors = gpd.read_file(outputs.gpkg_path, layer="errors")
    found = set(zip(errors["bldg_id"], errors["error_type"]))
    # bldg_id is the 0-based row of buildings.geojson: 4 = B5, 5 = B6, 7 = B8
    assert found == {
        (4, "building_overlap"),
        (5, "building_overlap"),
        (7, "building_on_road"),
    }

    clean = gpd.read_file(outputs.gpkg_path, layer="buildings_clean")
    assert len(clean) == 5


def test_webmap_uses_keyless_basemap_and_fits_data(tmp_path):
    outputs = run_pipeline(
        buildings_path=EXAMPLE / "buildings.geojson",
        boundary_path=EXAMPLE / "boundary.geojson",
        out_dir=tmp_path,
        config=DEFAULT_CONFIG,
    )
    html = outputs.webmap_html.read_text(encoding="utf-8")
    assert "tile.openstreetmap.org" in html
    assert "cartocdn" not in html  # CartoDB now renders "API KEY REQUIRED" tiles
    assert "fitBounds" in html
    assert "openstreetmap.org/copyright" in html  # OSM attribution is kept


def test_road_webmap_fits_data(tmp_path):
    from ovc.road_qc.webmap import generate_road_qc_webmap

    roads = gpd.read_file(EXAMPLE / "roads.geojson")
    out = generate_road_qc_webmap(roads, None, tmp_path / "roads.html")
    html = out.read_text(encoding="utf-8")
    assert "tile.openstreetmap.org" in html
    assert "fitBounds" in html
