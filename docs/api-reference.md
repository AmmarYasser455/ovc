---
layout: default
title: API Reference - OVC
---

# OVC API Reference

This document details the Python API for the Overlap Violation Checker (OVC).

**Version:** v3.0.0

> [!NOTE]
> The API is designed around functional components and data classes rather than large stateful objects.

---

## Table of Contents

1. [Building QC Pipeline](#building-qc-pipeline)
2. [Road QC Pipeline](#road-qc-pipeline)
3. [Configuration](#configuration)
4. [Quality Checks](#quality-checks)
5. [Data Structures](#data-structures)

---

## Building QC Pipeline

### `ovc.export.pipeline.run_pipeline`

Main entry point for building quality control.

```python
def run_pipeline(
    buildings_path: Path,
    out_dir: Path,
    boundary_path: Path | None = None,
    roads_path: Path | None = None,
    config: Config = DEFAULT_CONFIG,
) -> PipelineOutputs:
```

**Parameters:**

- `buildings_path` (Path): Path to local buildings file (Shapefile, GeoJSON, GPKG). **Required.**
- `out_dir` (Path): Directory where results will be saved.
- `boundary_path` (Path | None): Path to the boundary file (GeoJSON/SHP). Optional; enables boundary containment checks.
- `roads_path` (Path | None): Path to local roads file. Optional; enables road-building conflict checks.
- `config` (Config): Configuration object controlling thresholds and behavior.

**Returns:**

- `PipelineOutputs`: Object containing paths to generated files.

**Example:**

```python
from pathlib import Path
from ovc.export.pipeline import run_pipeline

outputs = run_pipeline(
    buildings_path=Path("data/buildings.gpkg"),
    out_dir=Path("results/my_run"),
    boundary_path=Path("data/boundary.geojson"),
)

print(f"GeoPackage: {outputs.gpkg_path}")
print(f"Web map: {outputs.webmap_html}")
print(f"Metrics: {outputs.metrics_csv}")
```

---

## Road QC Pipeline

### `ovc.road_qc.run_road_qc`

Main entry point for road quality control (New in v1.0.2).

```python
def run_road_qc(
    roads_path: Path | None = None,
    roads_gdf: gpd.GeoDataFrame | None = None,
    boundary_path: Path | None = None,
    boundary_gdf: gpd.GeoDataFrame | None = None,
    out_dir: Path = Path("outputs/road_qc"),
    config: RoadQCConfig = RoadQCConfig(),
) -> RoadQCOutputs:
```

**Parameters:**

- `roads_path` (Path | None): Path to road dataset file.
- `roads_gdf` (GeoDataFrame | None): Pre-loaded road GeoDataFrame.
- `boundary_path` (Path | None): Path to boundary for dangle filtering.
- `boundary_gdf` (GeoDataFrame | None): Pre-loaded boundary GeoDataFrame.
- `out_dir` (Path): Output directory for results.
- `config` (RoadQCConfig): Road QC configuration.

**Returns:**

- `RoadQCOutputs`: Object containing paths and metrics.

**Example:**

```python
from pathlib import Path
from ovc.road_qc import run_road_qc

outputs = run_road_qc(
    roads_path=Path("data/my_roads.shp"),
    out_dir=Path("results/road_qc")
)

print(f"GeoPackage: {outputs.gpkg_path}")
print(f"Web map: {outputs.webmap_html}")
print(f"Total errors: {outputs.total_errors}")
print(f"Top 3 errors: {outputs.top_3_errors}")
```

**With boundary for dangle filtering:**

```python
outputs = run_road_qc(
    roads_path=Path("data/my_roads.shp"),
    boundary_path=Path("data/boundary.geojson"),  # For dangle filtering
    out_dir=Path("results/road_qc")
)
```

---

## Configuration

### Building QC Configuration

#### `ovc.core.config.Config`

Main configuration container for building QC.

```python
@dataclass(frozen=True)
class Config:
    overlap: OverlapConfig = OverlapConfig()
    road_conflict: RoadConflictThresholds = RoadConflictThresholds()
    tags: Tags = ...
```

#### `ovc.core.config.OverlapConfig`

Settings for building overlap detection.

```python
@dataclass(frozen=True)
class OverlapConfig:
    duplicate_ratio_min: float = 0.98        # Ratio > 0.98 considered duplicate
    partial_ratio_min: float = 0.30          # Ratio > 0.30 considered partial overlap
    min_intersection_area_m2: float = 0.5    # Ignore overlaps smaller than this
```

#### `ovc.core.config.RoadConflictThresholds`

Settings for road conflict detection.

```python
@dataclass(frozen=True)
class RoadConflictThresholds:
    road_buffer_m: float = 1.0               # Buffer around road lines
    min_intersection_area_m2: float = 0.5    # Minimum overlap to flag
```

### Road QC Configuration

#### `ovc.road_qc.config.RoadQCConfig`

Settings for road network checks (New in v1.0.2).

```python
@dataclass(frozen=True)
class RoadQCConfig:
    disconnect_tolerance_m: float = 5.0   # Endpoint connection tolerance
    dangle_tolerance_m: float = 2.0       # Dangle grouping tolerance
```

**Example: Custom Road QC Configuration**

```python
from ovc.road_qc.config import RoadQCConfig
from ovc.road_qc import run_road_qc

config = RoadQCConfig(
    disconnect_tolerance_m=10.0,  # More tolerant connection detection
    dangle_tolerance_m=5.0        # Larger dangle grouping
)

run_road_qc(
    boundary_path=...,
    out_dir=...,
    config=config
)
```

---

## Quality Checks

These functions are pure functions that take `GeoDataFrames` (projected to meters) and return a new `GeoDataFrame` containing the errors.

### Building QC Checks

#### `ovc.checks.overlap.find_building_overlaps`

Detects overlaps between buildings in the same layer.

```python
def find_building_overlaps(
    buildings_metric: gpd.GeoDataFrame,
    thresholds: OverlapConfig,
) -> gpd.GeoDataFrame:
```

**Returns:**
- GeoDataFrame with intersection geometries and error types (`duplicate`, `partial`, `sliver`).

#### `ovc.checks.boundary_overlap.find_buildings_touching_boundary`

Finds buildings that cross or touch the analysis boundary buffer.

```python
def find_buildings_touching_boundary(
    buildings_metric: gpd.GeoDataFrame,
    boundary_metric: gpd.GeoDataFrame,
    boundary_buffer_m: float = 0.5,
) -> gpd.GeoDataFrame:
```

#### `ovc.checks.road_conflict.find_buildings_on_roads`

Identifies buildings that intersect with buffered road network.

```python
def find_buildings_on_roads(
    buildings_metric: gpd.GeoDataFrame,
    roads_metric: gpd.GeoDataFrame,
    road_buffer_m: float,
    min_intersection_area_m2: float,
) -> gpd.GeoDataFrame:
```

### Road QC Checks

#### `ovc.road_qc.checks.disconnected.find_disconnected_segments`

Detects roads not connected to any other road (New in v1.0.2).

```python
def find_disconnected_segments(
    roads_metric: gpd.GeoDataFrame,
    config: RoadQCConfig,
) -> gpd.GeoDataFrame:
```

**Returns:**
- GeoDataFrame with disconnected road geometries and `error_type="disconnected_segment"`.

#### `ovc.road_qc.checks.self_intersection.find_self_intersections`

Finds roads that cross themselves (New in v1.0.2).

```python
def find_self_intersections(
    roads_metric: gpd.GeoDataFrame,
    config: RoadQCConfig,
) -> gpd.GeoDataFrame:
```

**Returns:**
- GeoDataFrame with self-intersecting road geometries and `error_type="self_intersection"`.

#### `ovc.road_qc.checks.dangles.find_dangles`

Identifies dead-end endpoints (New in v1.0.2).

```python
def find_dangles(
    roads_metric: gpd.GeoDataFrame,
    config: RoadQCConfig,
    boundary_metric: gpd.GeoDataFrame | None = None,
) -> gpd.GeoDataFrame:
```

**Parameters:**
- `boundary_metric`: If provided, endpoints near the boundary are filtered out (not considered dangles).

**Returns:**
- GeoDataFrame with dangle point geometries and `error_type="dangle"`.

---

## Data Structures

### Building QC Outputs

#### `ovc.export.pipeline.PipelineOutputs`

Result object returned by `run_pipeline`.

```python
@dataclass(frozen=True)
class PipelineOutputs:
    gpkg_path: Path       # Path to the Output GeoPackage
    metrics_csv: Path     # Path to statistics CSV
    webmap_html: Path     # Path to interactive HTML map
```

### Road QC Outputs

#### `ovc.road_qc.pipeline.RoadQCOutputs`

Result object returned by `run_road_qc` (New in v1.0.2).

```python
@dataclass(frozen=True)
class RoadQCOutputs:
    gpkg_path: Path           # Path to road_qc.gpkg
    metrics_csv: Path         # Path to road_qc_metrics.csv
    webmap_html: Path         # Path to road_qc_map.html
    total_errors: int         # Total number of errors detected
    top_3_errors: list        # List of (error_type, count) tuples
```

**Example:**

```python
outputs = run_road_qc(...)

print(f"Total: {outputs.total_errors}")
for error_type, count in outputs.top_3_errors:
    print(f"  {error_type}: {count}")
```

---

## Module Structure

```
ovc/
├── core/
│   ├── config.py           # Building QC configuration
│   ├── crs.py              # Coordinate system utilities
│   ├── geometry.py         # Geometry utilities
│   └── logging.py          # Logging utilities
├── checks/
│   ├── overlap.py          # Building overlap detection
│   ├── road_conflict.py    # Building-road conflict detection
│   └── boundary_overlap.py # Boundary violation detection
├── export/
│   ├── pipeline.py         # Main Building QC pipeline
│   ├── geopackage.py       # GeoPackage export
│   ├── webmap.py           # Web map generation
│   └── tables.py           # CSV export
└── road_qc/                # NEW in v1.0.2
    ├── __init__.py         # Exports: run_road_qc, RoadQCConfig
    ├── config.py           # RoadQCConfig
    ├── checks/
    │   ├── disconnected.py
    │   ├── self_intersection.py
    │   └── dangles.py
    ├── metrics.py          # Error counting and ranking
    ├── pipeline.py         # run_road_qc() orchestration
    └── webmap.py           # Road QC web map
```

---

[← Back to Documentation](index.md) | [Examples →](examples.md)