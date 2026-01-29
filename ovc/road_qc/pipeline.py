from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pandas as pd

from ovc.core.logging import get_logger
from ovc.core.crs import get_crs_pair, ensure_wgs84
from ovc.core.geometry import drop_empty_and_fix
from ovc.loaders.roads import load_roads

from ovc.road_qc.config import RoadQCConfig
from ovc.road_qc.checks.disconnected import find_disconnected_segments
from ovc.road_qc.checks.self_intersection import find_self_intersections
from ovc.road_qc.checks.dangles import find_dangles
from ovc.road_qc.metrics import compute_road_qc_metrics, merge_errors


@dataclass(frozen=True)
class RoadQCOutputs:
    """Result object returned by run_road_qc."""

    gpkg_path: Path
    metrics_csv: Path
    total_errors: int
    top_3_errors: list


def _ensure_road_id(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Ensure road_id column exists."""
    if "road_id" not in gdf.columns:
        gdf = gdf.copy()
        if "osmid" in gdf.columns:
            gdf["road_id"] = gdf["osmid"].astype(str)
        else:
            gdf["road_id"] = gdf.index.astype(str)
    return gdf


def run_road_qc(
    roads_path: Path | None = None,
    roads_gdf: gpd.GeoDataFrame | None = None,
    boundary_path: Path | None = None,
    out_dir: Path = Path("outputs/road_qc"),
    config: RoadQCConfig = RoadQCConfig(),
) -> RoadQCOutputs:
    """
    Run road quality control checks.

    Accepts either:
    - roads_path: Path to road file (manual or OSM export)
    - roads_gdf: Pre-loaded GeoDataFrame
    - boundary_path: Download roads from OSM for this boundary

    Parameters:
        roads_path: Path to road dataset file
        roads_gdf: Pre-loaded road GeoDataFrame
        boundary_path: Path to boundary for OSM download
        out_dir: Output directory for results
        config: Road QC configuration

    Returns:
        RoadQCOutputs with paths and metrics
    """
    log = get_logger("ovc.road_qc")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load roads from one of the sources
    if roads_gdf is not None:
        log.info("Using provided road GeoDataFrame")
        roads_4326 = ensure_wgs84(roads_gdf)
    elif roads_path is not None:
        log.info(f"Loading roads from {roads_path}")
        roads_4326 = gpd.read_file(roads_path)
        roads_4326 = ensure_wgs84(roads_4326)
    elif boundary_path is not None:
        log.info(f"Downloading roads from OSM within boundary {boundary_path}")
        boundary = gpd.read_file(boundary_path)
        boundary = ensure_wgs84(boundary)
        roads_4326 = load_roads(boundary, {"highway": True})
    else:
        raise ValueError(
            "Must provide one of: roads_path, roads_gdf, or boundary_path"
        )

    if roads_4326 is None or roads_4326.empty:
        log.warning("No roads found")
        # Return empty results
        gpkg_path = out_dir / "road_qc_errors.gpkg"
        metrics_csv = out_dir / "road_qc_metrics.csv"

        empty_gdf = gpd.GeoDataFrame(
            {"road_id": [], "error_type": [], "geometry": []},
            geometry="geometry",
            crs=4326,
        )
        empty_gdf.to_file(gpkg_path, layer="errors", driver="GPKG")

        metrics = {"total_errors": 0, "error_counts": {}, "top_3_errors": []}
        pd.DataFrame([
            {"metric": "total_errors", "value": 0},
        ]).to_csv(metrics_csv, index=False)

        return RoadQCOutputs(
            gpkg_path=gpkg_path,
            metrics_csv=metrics_csv,
            total_errors=0,
            top_3_errors=[],
        )

    # Filter to LineString/MultiLineString only
    roads_4326 = roads_4326[
        roads_4326.geometry.type.isin(["LineString", "MultiLineString"])
    ].copy()
    roads_4326 = drop_empty_and_fix(roads_4326)
    roads_4326 = _ensure_road_id(roads_4326)

    # Project to metric CRS for accurate distance calculations
    crs_pair = get_crs_pair(roads_4326)
    roads_metric = roads_4326.to_crs(crs_pair.crs_metric)

    log.info(f"Analyzing {len(roads_metric)} road segments")

    # Run all checks
    log.info("Checking for disconnected segments...")
    disconnected = find_disconnected_segments(roads_metric, config)
    log.info(f"  Found {len(disconnected)} disconnected segments")

    log.info("Checking for self-intersections...")
    self_intersections = find_self_intersections(roads_metric, config)
    log.info(f"  Found {len(self_intersections)} self-intersections")

    log.info("Checking for dangles...")
    dangles = find_dangles(roads_metric, config)
    log.info(f"  Found {len(dangles)} dangles")

    # Merge all errors
    all_errors = merge_errors(disconnected, self_intersections, dangles)

    # Compute metrics
    metrics = compute_road_qc_metrics(all_errors)
    log.info(f"Total errors: {metrics['total_errors']}")
    log.info(f"Top 3 errors: {metrics['top_3_errors']}")

    # Export results
    gpkg_path = out_dir / "road_qc_errors.gpkg"
    metrics_csv = out_dir / "road_qc_metrics.csv"

    # Convert errors to WGS84 for export
    if not all_errors.empty:
        all_errors_4326 = all_errors.to_crs(4326)
    else:
        all_errors_4326 = all_errors

    # Write GeoPackage
    gpkg_path.parent.mkdir(parents=True, exist_ok=True)
    if not all_errors_4326.empty:
        all_errors_4326.to_file(gpkg_path, layer="errors", driver="GPKG")
    else:
        # Write empty layer with schema
        gpd.GeoDataFrame(
            {"road_id": [], "error_type": [], "geometry": []},
            geometry="geometry",
            crs=4326,
        ).to_file(gpkg_path, layer="errors", driver="GPKG")

    # Write roads layer for reference
    roads_4326[["road_id", "geometry"]].to_file(gpkg_path, layer="roads", driver="GPKG")

    # Write metrics CSV
    metrics_rows = [
        {"metric": "total_errors", "value": metrics["total_errors"]},
    ]
    for error_type, count in metrics["error_counts"].items():
        metrics_rows.append({"metric": f"count_{error_type}", "value": count})
    for i, (error_type, count) in enumerate(metrics["top_3_errors"], 1):
        metrics_rows.append({"metric": f"top_{i}_error_type", "value": error_type})
        metrics_rows.append({"metric": f"top_{i}_count", "value": count})

    pd.DataFrame(metrics_rows).to_csv(metrics_csv, index=False)

    log.info(f"Results saved to {gpkg_path}")

    return RoadQCOutputs(
        gpkg_path=gpkg_path,
        metrics_csv=metrics_csv,
        total_errors=metrics["total_errors"],
        top_3_errors=metrics["top_3_errors"],
    )
