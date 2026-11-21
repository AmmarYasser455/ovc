<div align="center">

<img src="docs/assets/logo.png" alt="OVC Logo" width="300"/>

# OVC Architecture Overview

**Design decisions and system structure for maintainers and contributors**

</div>

>  **For user documentation, see the [Full Documentation](docs/index.md)**

---

## Table of Contents

- [Project Structure](#project-structure)
- [Separation of Concerns](#separation-of-concerns)
- [Configuration vs Logic](#configuration-vs-logic)
- [Backward Compatibility](#backward-compatibility)
- [Design Principles](#design-principles)
- [Future Considerations](#future-considerations)

---

## Project Structure

```
ovc/
├── engine/       # Topology engine: overlaps, gaps, input quality, area measurement
├── io/           # Read layers with their FIDs; export findings
├── api.py        # check_file(): read a layer, run the engine
├── app/          # Map app: local server, launcher, browser UI
├── cli.py        # `ovc` command (`ovc check`, `ovc gui`, pipeline options)
├── sample_data/  # Sample GeoPackage bundled with the app
├── core/         # CRS helpers, config, logging for the pipeline
├── loaders/      # Pipeline data loading
├── checks/       # Pipeline building checks
├── metrics/      # Pipeline statistics
├── export/       # Pipeline orchestration and outputs
├── precheck/     # GeoQA pre-check
└── road_qc/      # Road network QC
packaging/windows/  # OVC.exe build script
examples/           # Sample generator, GeoQA -> OVC walkthrough
tests/              # Test suite
```

---

## One engine, several interfaces

```
map app (ovc/app) ──┐
ovc check (cli.py) ─┼─> ovc.api.check_file ─> ovc.io.read_layer ─> ovc.engine.check_polygons ─> ScanResult
Python users ───────┘                                                        │
building pipeline ─> checks.find_building_overlaps ─> ovc.engine.overlaps ───┘
```

### `engine/`

**Purpose:** decide what is an overlap or a gap, and how areas are measured.

- `scan.py`: `check_polygons()` validates the input, classifies every feature (usable, invalid, empty, not a polygon), runs the requested checks and returns a `ScanResult`.
- `overlaps.py`: STRtree candidate pairs, exact polygonal intersection, classification (`overlap`, `containment`, `duplicate`).
- `gaps.py`: coverage area minus the union of the features; one finding per connected part.
- `measure.py`: picks the working CRS. Planar area in the layer's projected CRS when it distorts area by at most 1%; otherwise the WGS 84 / UTM zone at the layer's centre.
- `model.py`: `ScanResult`, `CheckOutcome`, `Measurement`, issue types.

**Constraints:**
- No file I/O and no mutation of inputs. Repairs happen on copies, only when asked.
- Data problems never raise and never produce a `clean` status. The status is `clean`, `issues`, `partial` or `failed`.
- Area thresholds are in m²; a finding whose area equals the threshold is reported.

### `io/`

- `layers.py`: `list_layers()` and `read_layer()`. The file's feature ID (FID) becomes the GeoDataFrame index, so findings can always be traced to source features.
- `findings.py`: `export_findings()` writes GeoPackage (source CRS) or GeoJSON (EPSG:4326) through a temporary file, refuses to write to an input file, and refuses to replace an existing file unless told to.

### `app/`

- `server.py`: `http.server` bound to 127.0.0.1 with a per-launch token. Scans run in a worker thread; the page polls for progress.
- `launcher.py`: starts the server, opens the browser, reuses a running instance, stops after Quit or 15 idle minutes. `--self-test` checks an installed or frozen copy.
- `native.py`: the app window (pywebview on Edge WebView2, with the browser as fallback), the Windows file dialogs and the splash window (Tk). A dialog runs in a short child process; without a desktop the page's own file browser is used.
- `branding.py`: app name, organisation and founder shown in the title bar, splash and About box.
- `static/`: the page (plain JavaScript and a bundled Leaflet, so it works offline). Layers are listed in a panel (visibility, order, symbology); the toolbar holds the map, selection and review tools.

---

### Module: `road_qc/`

**Purpose:** Road network quality control

Contains:
- Disconnected segment detection
- Self-intersection detection
- Dangle (dead-end) detection with boundary filtering
- Road-specific web map generation

**Architecture:**
- Follows the same patterns as Building QC
- Modular checks in `road_qc/checks/`
- Unified output structure

---

### Module: `precheck/` (GeoQA Integration)

**Purpose:** Automated data-readiness assessment via the external `geoqa` dependency.

**Architecture:**
- Acts as a strict validation gate **before** the heavy OVC QC pipeline runs.
- Offloads basic topology compliance (empty, null, invalid, unprojected geometries) to the `geoqa` Python package.
- Ensures all inputs passed to OVC algorithms are fundamentally sound, preventing runtime failures mid-pipeline.
- Generates its own independent suite of HTML quality reports via `geoqa`.

---

## Separation of Concerns

OVC is intentionally split into clear, independent layers to maintain modularity and testability.

### `core/`

**Purpose:** Shared, low-level utilities and infrastructure

Contains:
- CRS handling and transformations
- Geometry helper functions
- Configuration objects
- Spatial indexing utilities

**Constraints:**
-  Must remain domain-agnostic
-  No QC-specific logic allowed
-  No I/O operations

---

### `loaders/`

**Purpose:** Data ingestion and normalization

Responsible for:
- Reading input data from local files (buildings, roads, boundaries)
- Supporting multiple formats: Shapefile, GeoJSON, GeoPackage, etc.
- Schema normalization across different sources
- Reprojecting geometries to WGS 84
- Data preprocessing and cleaning

**Constraints:**
-  Handles all data reading operations
-  Works with local files only (no network/API calls)
-  Does not perform validation or QC checks
-  Does not contain business logic

---

### `checks/`

**Purpose:** Quality control logic and validation algorithms

Contains all spatial quality checks:
- Building overlap detection
- Boundary compliance validation
- Road conflict analysis
- Topological error detection

**Each check module:**
-  Is deterministic and reproducible
-  Accepts prepared GeoDataFrames as input
-  Returns structured error outputs
-  Does not perform I/O operations
-  Does not load configuration directly

---

### `export/`

**Purpose:** Pipeline orchestration and output generation

Responsible for:
- Running the complete QC pipeline
- Writing results to disk (GeoJSON, CSV)
- Generating interactive web maps
- Producing summary reports

**Constraints:**
-  Orchestrates the entire workflow
-  Handles all output operations
-  Does not contain QC algorithms
-  Does not perform data validation

---

### `metrics/`

**Purpose:** Statistics computation and summary generation

Responsible for:
- Computing overlap statistics (counts, areas)
- Generating summary metrics for reports
- Aggregating error counts by type
- Calculating error ratios and percentages

**Constraints:**
-  Pure computation, no side effects
-  Takes prepared GeoDataFrames as input
-  Does not perform I/O operations
-  Does not perform data validation

---

## Configuration vs Logic

A **strict separation** is enforced between configuration and business logic:

### Configuration (`core/config.py`)

Defines runtime behavior:
- User-adjustable parameters
- Threshold values (e.g., overlap tolerance)
- Output preferences
- System settings

### Logic (`checks/*`)

Implements algorithms:
- Geometry operations
- Spatial analysis
- Error classification
- Validation rules

**Why this matters:**
- Prevents tight coupling between parameters and implementation
- Allows algorithms to be tested independently
- Enables configuration changes without code modifications
- Supports multiple configuration profiles

---

## Backward Compatibility

OVC maintains backward compatibility through **configuration wrappers** that support legacy API usage.

### Legacy Support

Some configuration wrappers exist to:
- Accept deprecated parameter names
- Normalize arguments internally
- Preserve behavior for existing users

### Implementation

```python
# Example: Legacy parameter support
def run_check(data, overlap_threshold=None, threshold=None):
    # Normalize to current API
    active_threshold = threshold if threshold is not None else overlap_threshold
    # ... rest of logic
```

**Benefits:**
- Existing code continues to work
- APIs can evolve gracefully
- Core logic remains unaffected
- Clear deprecation path for future versions

---

## Design Principles

OVC follows these core architectural principles:

### 1. **Explicit over Implicit**
- Function parameters are clearly named
- Dependencies are explicitly passed
- No hidden global state

### 2. **Clear Module Boundaries**
- Each module has a single, well-defined responsibility
- Cross-module dependencies are minimized
- Interfaces are clean and documented

### 3. **No Hidden Side Effects**
- Functions do not modify global state
- I/O operations are isolated to specific modules
- Pure functions whenever possible

### 4. **Testability over Convenience**
- Architecture prioritizes unit testing
- Modules can be tested in isolation
- Mock-friendly interfaces

### 5. **Backward Compatibility**
- Breaking changes are avoided when possible
- Deprecation warnings guide users to new APIs
- Legacy support is time-limited and documented

---

## Future Considerations

### Completed in v3.1.0

-  Full migration of vectorization endpoints from `unary_union` to `union_all()`.
-  Centralized `__init__.py` API exports for straightforward third-party integration.
-  Global `ERROR_COLOR_MAP` added to `ovc.export.maps`.
-  GeoQA formally decoupled as an independent upstream package for the `precheck` module.

**Short-term:**
- Deprecation of legacy configuration wrappers
- Move the pipeline's boundary and road checks onto the engine's result model

**Medium-term:**
- Additional Building QC checks:
  - Minimum area validation
  - Attribute completeness checks
- Plugin system for custom validators

**Long-term:**
- Distributed processing support for large datasets
- Real-time validation API
- Integration with external QC frameworks

---

## Contributing to Architecture

When proposing architectural changes:

1. **Open an issue first** to discuss the design
2. **Explain the problem** you're solving
3. **Consider backward compatibility** impacts
4. **Update this document** if your PR changes structure
5. **Add tests** that validate the new architecture

---

<div align="center">

**Questions about the architecture?**

[Open an issue](https://github.com/AmmarYasser455/ovc/issues) or reach out to the maintainers.

</div>
