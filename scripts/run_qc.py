from pathlib import Path
import argparse
import sys

# Add project root to PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ovc.export.pipeline import run_pipeline
from ovc.core.logging import get_logger

DEFAULT_BOUNDARIES_DIR = Path("data/boundaries")

logger = get_logger("ovc.cli")


def resolve_boundary(boundary_arg: str) -> Path:
    p = Path(boundary_arg)

    if p.exists():
        return p

    candidate = DEFAULT_BOUNDARIES_DIR / f"{boundary_arg}.geojson"
    if candidate.exists():
        return candidate

    raise FileNotFoundError(
        f"Boundary not found: '{boundary_arg}'. "
        f"Provide a valid file path or a name existing in {DEFAULT_BOUNDARIES_DIR}"
    )


def main():
    logger.info("OVC started. Preparing your data...")

    parser = argparse.ArgumentParser(
        description="OVC – OpenStreetMap Building Quality Control"
    )

    parser.add_argument(
        "--boundary",
        required=True,
        help="Path to boundary file (shp/geojson/gpkg) or boundary name",
    )

    parser.add_argument(
        "--buildings",
        required=False,
        help="Optional: path to buildings file (shp/geojson/gpkg). "
        "If not provided, OSM buildings will be downloaded.",
    )

    parser.add_argument(
        "--roads",
        required=False,
        help="Optional: path to roads file (shp/geojson/gpkg). "
        "If not provided, OSM roads will be downloaded.",
    )

    parser.add_argument(
        "--out",
        default="outputs",
        help="Output directory",
    )

    args = parser.parse_args()

    logger.info("Resolving boundary...")
    try:
        boundary_path = resolve_boundary(args.boundary)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    if args.buildings:
        buildings_path = Path(args.buildings)
        logger.info("Using provided buildings file")
    else:
        buildings_path = None
        logger.info("Downloading buildings from OpenStreetMap")

    if args.roads:
        roads_path = Path(args.roads)
        logger.info("Using provided roads file")
    else:
        roads_path = None
        logger.info("Downloading roads from OpenStreetMap")

    logger.info("Running QC pipeline...")
    outputs = run_pipeline(
        boundary_path=boundary_path,
        buildings_path=buildings_path,
        roads_path=roads_path,
        out_dir=Path(args.out),
    )

    logger.info("QC finished successfully")
    logger.info(f"GeoPackage: {outputs.gpkg_path}")
    logger.info(f"Metrics CSV: {outputs.metrics_csv}")
    logger.info(f"Web map: {outputs.webmap_html}")


if __name__ == "__main__":
    main()
