# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.1.0] - 2026-02-11

### Added
- **GeoQA pre-check integration** — Automated data quality assessment before QC pipeline runs.
- New `ovc/precheck/` module wrapping GeoQA for input data validation.
- `--precheck` CLI flag: runs GeoQA quality assessment on all inputs before QC.
- `--precheck-only` CLI flag: runs only the quality assessment, skips QC checks.
- `precheck_buildings()`, `precheck_roads()`, `precheck_boundary()`, `precheck_all()` API functions.
- `PrecheckResult` dataclass with quality score, blockers, warnings, and report paths.
- Generates per-dataset HTML quality reports with charts (quality gauge, completeness bar, histograms).
- Detects blockers (missing CRS, wrong geometry type, empty datasets, >10% invalid geometries).
- `run_pipeline()` now accepts `run_precheck=True` to embed pre-check into the pipeline.
- `PipelineOutputs` extended with `precheck_report` and `precheck_score` fields.
- 12 new integration tests in `tests/test_precheck.py`.

### Changed
- `geoqa` added as a project dependency.

## [3.0.0] - 2026-02-11

### Breaking Changes
- **Removed all OpenStreetMap / Overpass API integration.** OVC is now a **local-data-only** tool.
- `--buildings` is now **required** (was optional when `--boundary` was provided for OSM download).
- `--boundary` is now optional (only enables boundary overlap / outside-boundary checks).
- `--roads` is now optional (only enables building-on-road conflict checks).
- `load_buildings()` now accepts a file path instead of a boundary GeoDataFrame + OSM tags.
- `load_roads()` now accepts a file path instead of a boundary GeoDataFrame + OSM tags.
- `run_pipeline()` signature changed: `buildings_path` is now the first required argument.
- `Config.tags` removed — no more OSM tag configuration.
- `osmnx` is no longer a dependency.

### Why
- Overpass API rate limits and timeouts caused frequent freezes and incomplete downloads.
- Users invariably had their own data and only needed the QC checks.
- Removing the network dependency makes OVC faster, more reliable, and usable offline.

### Changed
- Loaders (`buildings.py`, `roads.py`) rewritten to load from local files (Shapefile, GeoJSON, GeoPackage, etc.).
- Pipeline (`export/pipeline.py`) simplified — no more OSM download fallback paths.
- CLI (`scripts/run_qc.py`) simplified — `--buildings` is required, no OSM download messaging.
- Road QC pipeline no longer has an OSM download fallback.
- All documentation updated to reflect local-data-only workflow.

### Kept (unchanged)
- All QC checks: overlap detection, road conflict, boundary overlap, geometry quality.
- All Road QC checks: disconnected segments, self-intersections, dangles.
- Vectorized spatial join optimizations from v2.0.0.
- Interactive web map generation.
- GeoPackage + CSV + HTML output structure.
- Geometry quality checks (duplicate, invalid, area, compactness, setback).

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
