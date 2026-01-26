from pathlib import Path
import argparse
import sys

from ovc.export.pipeline import run_pipeline


DEFAULT_BOUNDARIES_DIR = Path("data/boundaries")


def resolve_boundary(boundary_arg: str) -> Path:
    p = Path(boundary_arg)

    if p.exists():
        return p

    candidate = DEFAULT_BOUNDARIES_DIR / f"{boundary_arg}.geojson"
    if candidate.exists():
        return candidate

    raise FileNotFoundError(
        f"Boundary not found: '{boundary_arg}'.\n"
        f"Provide a valid file path or a name existing in {DEFAULT_BOUNDARIES_DIR}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="OVC – OpenStreetMap Building Quality Control"
    )
    parser.add_argument(
        "--boundary",
        required=True,
        help="Path to boundary file (shp/geojson/gpkg) or boundary name",
    )
    parser.add_argument(
        "--out",
        default="outputs",
        help="Output directory",
    )

    args = parser.parse_args()

    try:
        boundary_path = resolve_boundary(args.boundary)
    except FileNotFoundError as e:
        print(e)
        sys.exit(1)

    outputs = run_pipeline(
        boundary_path=boundary_path,
        out_dir=Path(args.out),
    )

    print("\nOVC finished successfully:")
    print(f"- GeoPackage: {outputs.gpkg_path}")
    print(f"- Metrics CSV: {outputs.metrics_csv}")
    print(f"- Web map: {outputs.webmap_html}")


if __name__ == "__main__":
    main()
