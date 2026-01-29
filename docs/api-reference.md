---
layout: default
title: API Reference - OVC
---

# OVC API Reference

This document details the Python API for the Overlap Violation Checker (OVC).

> [!NOTE]
> The API is designed around functional components and data classes rather than large stateful objects. The main entry point is `run_pipeline`.

---

## Table of Contents

1. [Pipeline (Main Entry Point)](#pipeline-main-entry-point)
2. [Configuration](#configuration)
3. [Quality Checks](#quality-checks)
4. [Data Structures](#data-structures)

---

## Pipeline (Main Entry Point)

### `ovc.export.pipeline.run_pipeline`

This is the primary function to execute the full quality control workflow programmatically.

```python
def run_pipeline(
    boundary_path: Path | None,
    out_dir: Path,
    buildings_path: Path | None = None,
    roads_path: Path | None = None,
    config: Config = DEFAULT_CONFIG,
) -> PipelineOutputs:
```

**Parameters:**

- `boundary_path` (Path | None): Path to the boundary file (GeoJSON/SHP). Required for downloading OSM data.
- `out_dir` (Path): Directory where results will be saved.
- `buildings_path` (Path | None): Path to local buildings file. If None, buildings are downloaded from OSM.
- `roads_path` (Path | None): Path to local roads file. If None, roads are downloaded from OSM (if boundary is provided).
- `config` (Config): Configuration object controlling thresholds and behavior.

**Returns:**

- `PipelineOutputs`: Object containing paths to generated files.

**Example:**

```python
from pathlib import Path
from ovc.export.pipeline import run_pipeline

outputs = run_pipeline(
    boundary_path=Path("data/boundary.geojson"),
    out_dir=Path("results/my_run"),
    buildings_path=Path("data/buildings.gpkg")
)

print(f"Results saved to: {outputs.metrics_csv}")
```

---

## Configuration

### `ovc.core.config.Config`

Configuration object used to pass settings to the pipeline.

```python
@dataclass(frozen=True)
class Config:
    overlap: OverlapConfig = OverlapConfig()
    road_conflict: RoadConflictThresholds = RoadConflictThresholds()
    tags: Tags = ...
```

### `ovc.core.config.OverlapConfig`

Settings for building overlap detection.

```python
@dataclass(frozen=True)
class OverlapConfig:
    duplicate_ratio_min: float = 0.98        # Ratio > 0.98 considered duplicate
    partial_ratio_min: float = 0.30          # Ratio > 0.30 considered partial overlap
    min_intersection_area_m2: float = 0.5    # Ignore overlaps smaller than this
```

### `ovc.core.config.RoadConflictThresholds`

Settings for road conflict detection.

```python
@dataclass(frozen=True)
class RoadConflictThresholds:
    road_buffer_m: float = 1.0               # Buffer around road lines
    min_intersection_area_m2: float = 0.5    # Minimum overlap to flag
```

**Example: Custom Configuration**

```python
from ovc.core.config import Config, OverlapConfig, RoadConflictThresholds
from ovc.export.pipeline import run_pipeline

# Create strict custom config
my_config = Config(
    overlap=OverlapConfig(
        min_intersection_area_m2=0.1,  # Stricter area check
        partial_ratio_min=0.1          # Flag even small overlaps
    ),
    road_conflict=RoadConflictThresholds(
        road_buffer_m=2.0              # Larger road buffer
    )
)

run_pipeline(..., config=my_config)
```

---

## Quality Checks

These functions are strictly pure functions that take `GeoDataFrames` (projected to meters) and return a new `GeoDataFrame` containing the errors.

### `ovc.checks.overlap.find_building_overlaps`

Detects overlaps between buildings in the same layer.

```python
def find_building_overlaps(
    buildings_metric: gpd.GeoDataFrame,
    thresholds: OverlapConfig,
) -> gpd.GeoDataFrame:
```

**Returns:**
- GeoDataFrame with intersection geometries and error types (`duplicate`, `partial`, `sliver`).

### `ovc.checks.boundary_overlap.find_buildings_touching_boundary`

Finds buildings that cross or touch the analysis boundary buffer.

```python
def find_buildings_touching_boundary(
    buildings_metric: gpd.GeoDataFrame,
    boundary_metric: gpd.GeoDataFrame,
    boundary_buffer_m: float = 0.5,
) -> gpd.GeoDataFrame:
```

### `ovc.checks.road_conflict.find_buildings_on_roads`

Identifies buildings that intersect with buffered road network.

```python
def find_buildings_on_roads(
    buildings_metric: gpd.GeoDataFrame,
    roads_metric: gpd.GeoDataFrame,
    road_buffer_m: float,
    min_intersection_area_m2: float,
) -> gpd.GeoDataFrame:
```

---

## Data Structures

### `ovc.export.pipeline.PipelineOutputs`

Result object returned by `run_pipeline`.

```python
@dataclass(frozen=True)
class PipelineOutputs:
    gpkg_path: Path       # Path to the Output GeoPackage
    metrics_csv: Path     # Path to statistics CSV
    webmap_html: Path     # Path to interactive HTML map
```