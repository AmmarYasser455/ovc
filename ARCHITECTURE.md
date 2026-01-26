# OVC Architecture Overview

This document explains the high-level architecture and design decisions
behind the Overlap Violation Checker (OVC) project.

It is intended for maintainers and contributors.

---

## Project Structure

/ovc
├── core/        # Core utilities and shared infrastructure
├── loaders/     # Data loading and preprocessing
├── checks/      # Quality checks and validation logic
├── export/      # Output generation (files, web maps, reports)
tests/           # Test suite


---

## Separation of Concerns

OVC is intentionally split into clear layers:

### `core`
Contains shared, low-level utilities:
- CRS handling
- Geometry helpers
- Configuration objects
- Spatial indexing helpers

This layer must remain free of domain-specific QC logic.

---

### `loaders`
Responsible for:
- Reading input data (buildings, roads, boundaries)
- Normalizing schemas
- Reprojecting to metric CRS

Loaders do **not** perform validation or QC.

---

### `checks`
Contains all quality control logic:
- Building overlap detection
- Boundary overlap checks
- Road conflict checks

Each check:
- Is deterministic
- Accepts prepared GeoDataFrames
- Returns structured error outputs

No I/O or configuration loading happens here.

---

### `export`
Responsible for:
- Running the full pipeline
- Writing outputs
- Generating web maps and reports

This layer orchestrates the system but does not contain QC logic itself.

---

## Configuration vs Logic

A strict distinction is enforced between:

### Configuration (`core.config`)
- Runtime parameters
- Threshold values
- User-adjustable settings

### Logic (`checks.*`)
- Algorithms
- Geometry operations
- Error classification

Even if configuration objects resemble logic thresholds,
they must remain separate to avoid tight coupling.

---

## Backward Compatibility

Some configuration wrappers exist to support legacy parameter names
used in earlier versions and tests.

These wrappers:
- Accept deprecated argument names
- Normalize them internally
- Do not affect core logic

This allows API evolution without breaking existing users.

---

## Design Principles

- Explicit over implicit
- Clear module boundaries
- No hidden side effects
- Testability over convenience
- Backward compatibility when evolving APIs

---

## Future Considerations

- Deprecation of legacy configuration wrappers
- Migration to `union_all()` for geometry unions
- Additional QC checks as independent modules

