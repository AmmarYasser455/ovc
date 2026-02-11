from pathlib import Path
import argparse
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ovc.export.pipeline import run_pipeline
from ovc.core.logging import get_logger

logger = get_logger("ovc.cli")


def main():
    logger.info("OVC started. Preparing your data...")

    parser = argparse.ArgumentParser(
        description="OVC – Spatial Data Quality Control (local data only)"
    )

    parser.add_argument(
        "--buildings",
        required=False,
        help="Path to buildings file (shp/geojson/gpkg). "
        "Required unless --road-qc-only is used.",
    )

    parser.add_argument(
        "--boundary",
        required=False,
        help="Optional: path to boundary file (shp/geojson/gpkg). "
        "Enables boundary overlap and outside-boundary checks.",
    )

    parser.add_argument(
        "--roads",
        required=False,
        help="Optional: path to roads file (shp/geojson/gpkg). "
        "Enables building-on-road conflict checks.",
    )

    parser.add_argument(
        "--road-qc",
        action="store_true",
        help="Enable road quality control checks (detect disconnected segments, self-intersections, dangles). "
        "Requires --roads.",
    )

    parser.add_argument(
        "--road-qc-only",
        action="store_true",
        help="Run ONLY road quality control checks (skip building QC). "
        "Requires --roads.",
    )

    parser.add_argument(
        "--out",
        default="outputs",
        help="Output directory (default: outputs)",
    )

    args = parser.parse_args()

    buildings_path = None
    if args.buildings:
        buildings_path = Path(args.buildings)
        if not buildings_path.exists():
            logger.error(f"Buildings file not found: {buildings_path}")
            sys.exit(1)
        logger.info(f"Buildings: {buildings_path}")

    boundary_path = None
    if args.boundary:
        boundary_path = Path(args.boundary)
        if not boundary_path.exists():
            logger.error(f"Boundary file not found: {boundary_path}")
            sys.exit(1)
        logger.info(f"Boundary: {boundary_path}")

    roads_path = None
    if args.roads:
        roads_path = Path(args.roads)
        if not roads_path.exists():
            logger.error(f"Roads file not found: {roads_path}")
            sys.exit(1)
        logger.info(f"Roads: {roads_path}")

    # --- Road QC only mode ---
    if args.road_qc_only:
        if roads_path is None:
            logger.error("--road-qc-only requires --roads to be provided.")
            sys.exit(1)

        from ovc.road_qc import run_road_qc

        logger.info("Running Road QC checks (road-qc-only mode)...")
        road_qc_outputs = run_road_qc(
            roads_path=roads_path,
            boundary_path=boundary_path,
            out_dir=Path(args.out) / "road_qc",
        )

        logger.info("Road QC finished")
        logger.info(f"GeoPackage: {road_qc_outputs.gpkg_path}")
        logger.info(f"Metrics CSV: {road_qc_outputs.metrics_csv}")
        logger.info(f"Web map: {road_qc_outputs.webmap_html}")
        logger.info(f"Total errors: {road_qc_outputs.total_errors}")
        if road_qc_outputs.top_3_errors:
            logger.info("Top 3 errors:")
            for error_type, count in road_qc_outputs.top_3_errors:
                logger.info(f"  • {error_type}: {count}")
        return

    # --- Building QC ---
    if buildings_path is None:
        logger.error("--buildings is required (unless using --road-qc-only).")
        sys.exit(1)

    logger.info("Running Building QC pipeline...")
    outputs = run_pipeline(
        buildings_path=buildings_path,
        boundary_path=boundary_path,
        roads_path=roads_path,
        out_dir=Path(args.out),
    )

    logger.info("Building QC finished successfully")
    logger.info(f"GeoPackage: {outputs.gpkg_path}")
    logger.info(f"Metrics CSV: {outputs.metrics_csv}")
    logger.info(f"Web map: {outputs.webmap_html}")

    # Run road QC if enabled
    if args.road_qc:
        if roads_path is None:
            logger.error("Road QC requires --roads to be provided.")
            sys.exit(1)

        from ovc.road_qc import run_road_qc

        logger.info("Running Road QC checks...")
        road_qc_outputs = run_road_qc(
            roads_path=roads_path,
            boundary_path=boundary_path,
            out_dir=Path(args.out) / "road_qc",
        )

        logger.info("Road QC finished")
        logger.info(f"GeoPackage: {road_qc_outputs.gpkg_path}")
        logger.info(f"Metrics CSV: {road_qc_outputs.metrics_csv}")
        logger.info(f"Web map: {road_qc_outputs.webmap_html}")
        logger.info(f"Total errors: {road_qc_outputs.total_errors}")
        if road_qc_outputs.top_3_errors:
            logger.info("Top 3 errors:")
            for error_type, count in road_qc_outputs.top_3_errors:
                logger.info(f"  • {error_type}: {count}")


if __name__ == "__main__":
    main()
