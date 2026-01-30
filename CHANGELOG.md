# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.2] - 2026-01-30

### Added
- **Road QC Module**: New module (`ovc.road_qc`) detecting disconnected segments, self-intersections, and dangles.
- **Unified Output Structure**: Outputs are now organized into `outputs/building_qc/` and `outputs/road_qc/`.
- **Dangle Filtering**: Boundary-aware filtering to prevent false positives at study area edges.
- **CLI Support**: Added `--road-qc` flag to `scripts/run_qc.py`.
- **Tutorial 8**: New guide for Road Network QC.

### Changed
- **Documentation**: Complete rewrite of User Guide and API Reference to reflect v1.0.2.
- **Web Maps**: Enhanced styling with legend and copyright notice.
- **Pipeline**: Merged duplicate output logic into a unified exporter.

## [1.0.1] - 2026-01-29

### Changed
- **Documentation**: Completely aligned `docs/api-reference.md` with the actual functional API structure.
- **Documentation**: Rewrote `Tutorial 7` to use the correct `run_pipeline` usage and handling of GeoPackage outputs.
- **Documentation**: Updated `User Guide` and `Examples` to remove incorrect Object-Oriented API usage.
- **Cleanup**: Removed unused development script `rename_to_ovc.sh`.
- **Cleanup**: Removed extraneous QGIS metadata file `tests/data/sample_boundary.qmd`.

## [1.0.0] - 2026-01-01

### Added
- Initial release of Overlap Violation Checker (OVC).
- Core checks for building overlaps, boundary violations, and road conflicts.
- Automated data pipeline with OpenStreetMap integration.
