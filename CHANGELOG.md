# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [3.5.1] - 2026-11-21

### Changed
- The app window is now Microsoft Edge (or Chrome) in app mode instead of a bundled WebView component. `OVC-windows.zip` no longer contains pywebview, pythonnet or their .NET bridge DLLs. Those files were new in 3.5.0, and Windows Defender's behaviour heuristic (`Behavior:Win32/DefenseEvasion.A!ml`) flagged the 3.5.0 zip on extraction; 3.4.0, which did not contain them, was not flagged. The `[window]` extra is removed; nothing extra is needed for the window.

## [3.5.0] - 2026-11-21

### Changed
- **OVC opens in its own window.** `OVC.exe` now shows the app in a desktop window (Edge WebView2, part of Windows 10 and 11) instead of a browser tab. Closing the window stops OVC. If no window can be shown, it opens in the default browser as before; `--browser` forces that.
- With pip, the window needs the optional extra: `pip install "ovc[window] @ git+https://github.com/AmmarYasser455/ovc.git"`. Without it `ovc-gui` uses the browser.

## [3.4.0] - 2026-11-21

### Added
- **Layers panel.** Every added layer is listed with a visibility box, zoom to layer, move up and down, remove, and symbology (colour, outline width, fill, fill opacity, dashed outline). Findings have their own entry with a legend. Any vector layer can be added for context; the layer to check and the coverage layer are chosen from the added layers.
- **Toolbar** with Add layer, Sample, Pan, Select, zoom tools (in, out, full extent, to layer, to selection), Clear, Delete, Restore, Run checks and Export, plus keyboard shortcuts (Ctrl+O, F5, Ctrl+E, S, P, Delete, Esc, Home).
- **Select tool.** Click a feature to highlight it and read its attributes.
- **Review edits.** Delete dismisses the selected finding (Restore brings it back); each finding takes a review note. Dismissed findings are left out of the export and notes are written to a `review_note` column. Input files are still never changed.
- **Windows file dialogs.** Add layer and Export open the Windows Explorer dialog. The in-page file browser remains as "Browse in app…" (for `.gdb` folders) and wherever no desktop dialog is available.
- **Splash window** at start-up and an About box with the app name, OpenTerra and the founder. Status bar with cursor coordinates, map scale and the layer CRS.
- **App icon** for `OVC.exe`, the splash window, the file dialogs and the browser tab.
- `export_findings(..., finding_ids=..., notes=...)`.

### Fixed
- A zoom requested while another zoom was still animating was ignored.

## [3.3.0] - 2026-11-21

### Added
- **Map app.** `OVC.exe` (Windows, built by the "Windows app" workflow) and the `ovc-gui` command open a local, offline map interface: file picker, layer selector with feature count and CRS, independent overlap and gap checks, a results list linked to the map, filter by issue type, and export to GeoPackage or GeoJSON.
- **Topology engine** (`ovc.engine`), shared by the app, the CLI, the Python API and the building pipeline. Overlaps are positive-area intersections reported once per pair, classed as `overlap`, `containment` or `duplicate`. Gaps are the uncovered parts of an analyst-supplied coverage layer (opt-in).
- Run status `clean`, `issues`, `partial` or `failed`. Unreadable files, missing CRS, invalid or empty geometries and failed geometry operations are reported and never look like a clean run.
- Area measurement in m² with a stated method: planar in the layer's projected CRS when its area distortion is at most 1%, otherwise in the WGS 84 / UTM zone of the layer's centre. Feet are converted to metres.
- `ovc.check_file()`, `ovc.check_polygons()`, `ovc.export_findings()`.
- `ovc` console command: `ovc check FILE`, `ovc gui`, and the existing pipeline options. `python scripts/run_qc.py` still works.
- Sample dataset `ovc/sample_data/ovc_sample.gpkg` and its generator in `examples/sample/`.
- The package version has a single source, `ovc.__version__`; the README badge follows the newest tag; publishing a release attaches `OVC-windows.zip` after checking the tag against the version.
- CONTRIBUTING: how to add a check and how to release.
- CI: browser test of the app workflow on Linux and Windows, wheel install check outside the checkout, Windows app build with a self-test.

### Changed
- `find_building_overlaps` uses the shared engine. A building inside another is now `overlap_type == "contained"` instead of `"duplicate"`; metrics gain `overlap_contained_count`. `duplicate` now means the overlap covers both buildings.
- `import ovc` loads its public functions on first use.
- The CLI moved from `scripts/run_qc.py` to `ovc/cli.py`.

### Fixed
- Overlap area counted only the largest part of a multi-part intersection (a U-shaped building crossed in two places reported 6 m² instead of 12 m²).
- A self-intersecting building was dropped from overlap detection without a message, hiding its overlaps. Invalid buildings are now repaired in memory with a logged warning.
- `find_duplicate_geometries` missed identical polygons whose rings start at a different vertex or run the other way.
- `load_buildings` numbered generated IDs after dropping non-polygon features, so IDs did not match source rows. It now also logs how many features were left out.
- `clip_to_boundary` returned the unclipped layer when clipping failed, and `drop_empty_and_fix` ignored a failed repair. Both errors now surface; repairs are logged.
- Raise the GeoPandas requirement to `>=1.0,<2.0`. The code calls `GeoDataFrame.union_all()`, which was added in GeoPandas 1.0, but the previous `<1.0` pin made a fresh install resolve to GeoPandas 0.14.x, where the QC pipeline and CRS helpers fail with `AttributeError`.

## [3.1.1] - 2026-02-12

### Fixed
- **Critical**: `ensure_wgs84()` now raises `ValueError` when input data has no CRS defined, instead of silently assuming EPSG:4326. This prevents coordinate corruption when projected data (e.g. UTM) is loaded without a `.prj` file. (OVC-001 from audit)
- **UX**: GeoPackage writer now logs a warning when a layer has no CRS, instead of silently setting EPSG:4326.
- **UX**: Building and road loaders now warn when file size exceeds 500 MB or feature count exceeds 100,000, setting expectations for runtime and memory usage.

### Added
- 9 new tests in `tests/test_crs.py` covering `ensure_wgs84`, `choose_utm_crs_from_gdf`, and `get_crs_pair` with valid, projected, missing, and edge-case CRS inputs.

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
