# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
