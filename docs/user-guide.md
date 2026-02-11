---
layout: default
title: User Guide - OVC
---

# OVC User Guide

Complete guide to installing, configuring, and using the Overlap Violation Checker.

**Version:** v3.0.0

---

## Table of Contents

1. [Installation](#installation)
2. [System Requirements](#system-requirements)
3. [Configuration](#configuration)
4. [Command-Line Usage](#command-line-usage)
5. [Road QC Module](#road-qc-module)
6. [Input Data Formats](#input-data-formats)
7. [Output Formats](#output-formats)
8. [Troubleshooting](#troubleshooting)
9. [Programmatic Usage](#programmatic-usage)
10. [Best Practices](#best-practices)

---

## Installation

### Prerequisites

Before installing OVC, ensure you have the following:

- **Python 3.10 or newer** (Python 3.11 recommended)
- **Git 2.30+** (Git 2.40+ recommended)
- **pip** package manager
- **GDAL/OGR libraries** (for GeoPandas support)

### Step 1: Install GDAL

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install gdal-bin libgdal-dev
```

**macOS (using Homebrew):**
```bash
brew install gdal
```

**Windows:**
Download and install from [OSGeo4W](https://trac.osgeo.org/osgeo4w/) or use conda:
```bash
conda install -c conda-forge gdal
```

### Step 2: Clone the Repository

```bash
git clone https://github.com/AmmarYasser455/ovc.git
cd ovc
```

### Step 3: Create Virtual Environment

It's strongly recommended to use a virtual environment:

```bash
# Create virtual environment
python -m venv venv

# Activate on Linux/macOS
source venv/bin/activate

# Activate on Windows
venv\Scripts\activate
```

### Step 4: Install Dependencies

```bash
pip install -e .
```

### Step 5: Verify Installation

Test that OVC is properly installed:

```bash
python scripts/run_qc.py --help
```

You should see the help message with available options.

---

## System Requirements

### Minimum Requirements

- **CPU:** Dual-core processor (2 GHz or faster)
- **RAM:** 4 GB
- **Storage:** 500 MB for installation + space for data
- **OS:** Windows 10/11, macOS 10.14+, Ubuntu 20.04+

### Recommended Requirements

- **CPU:** Quad-core processor (2.5 GHz or faster)
- **RAM:** 8 GB or more
- **Storage:** 2 GB + space for data
- **OS:** Latest stable version of your OS

### Performance Considerations

- **Large datasets (>100,000 buildings):** 16+ GB RAM recommended
- **Complex geometries:** SSD storage for faster I/O
- **Parallel processing:** Multi-core CPU for future versions

---

## Configuration

### Configuration System

OVC uses a dataclass-based configuration system defined in:

```
ovc/core/config.py       # Building QC configuration
ovc/road_qc/config.py    # Road QC configuration
```

### Building QC Configuration

**OverlapConfig** — Controls building overlap detection:
```python
@dataclass(frozen=True)
class OverlapConfig:
    duplicate_ratio_min: float = 0.98    # Ratio >= 0.98 = duplicate
    partial_ratio_min: float = 0.30      # Ratio >= 0.30 = partial overlap
    min_intersection_area_m2: float = 0.5  # Ignore smaller overlaps
```

**RoadConflictThresholds** — Controls road conflict detection:
```python
@dataclass(frozen=True)
class RoadConflictThresholds:
    road_buffer_m: float = 1.0           # Buffer around roads
    min_intersection_area_m2: float = 0.5  # Minimum overlap to flag
```

### Road QC Configuration (New in v1.0.2)

**RoadQCConfig** — Controls road network checks:
```python
@dataclass(frozen=True)
class RoadQCConfig:
    disconnect_tolerance_m: float = 5.0   # Endpoint connection tolerance
    dangle_tolerance_m: float = 2.0       # Dangle grouping tolerance
```

### Customizing Configuration

```python
from ovc.core.config import Config, OverlapConfig
from ovc.road_qc.config import RoadQCConfig
from ovc.export.pipeline import run_pipeline
from ovc.road_qc import run_road_qc

# Building QC with custom config
custom_config = Config(
    overlap=OverlapConfig(
        min_intersection_area_m2=0.1,  # Stricter detection
        partial_ratio_min=0.15         # Flag smaller overlaps
    )
)

run_pipeline(..., config=custom_config)

# Road QC with custom config
road_config = RoadQCConfig(
    disconnect_tolerance_m=10.0,  # More tolerant
    dangle_tolerance_m=5.0
)

run_road_qc(..., config=road_config)
```

---

## Command-Line Usage

### Basic Syntax

```bash
python scripts/run_qc.py [OPTIONS]
```

### Common Options

| Option | Type | Description |
|--------|------|-------------|
| `--buildings` | Path | Path to buildings dataset (Shapefile, GeoJSON, GPKG). **Required.** |
| `--roads` | Path | Path to roads dataset (optional) |
| `--boundary` | Path | Path to boundary polygon (optional) |
| `--road-qc` | Flag | Enable Road QC checks (New in v1.0.2) |
| `--out` | Path | Output directory for results |
| `--help` | Flag | Show help message |

### Usage Modes

#### Mode 1: Buildings Only

Provide your buildings data for overlap detection.

```bash
python scripts/run_qc.py \
  --buildings data/my_buildings.shp \
  --out results/mode1
```

**What happens:**
- Loads your building dataset
- Performs building overlap detection
- Generates reports and interactive map

#### Mode 2: Buildings and Roads

Provide both buildings and roads datasets for full conflict analysis.

```bash
python scripts/run_qc.py \
  --buildings data/my_buildings.geojson \
  --roads data/my_roads.geojson \
  --out results/mode2
```

**What happens:**
- Loads both datasets
- Performs all validation checks including road-building conflicts
- Uses provided data exclusively

#### Mode 3: Buildings with Boundary

Add a boundary for containment checks.

```bash
python scripts/run_qc.py \
  --buildings data/my_buildings.shp \
  --boundary data/city_boundary.geojson \
  --out results/mode3
```

**What happens:**
- Loads buildings and boundary
- Performs overlap detection and boundary containment checks
- Flags buildings outside or crossing the boundary

#### Mode 4: Complete QC with Road QC (New in v1.0.2)

Run both Building QC and Road QC together.

```bash
python scripts/run_qc.py \
  --buildings data/my_buildings.shp \
  --roads data/my_roads.shp \
  --boundary data/city_boundary.geojson \
  --road-qc \
  --out results/mode4
```

**What happens:**
- Runs full Building QC pipeline
- Also runs Road QC checks:
  - Disconnected road segments
  - Self-intersecting roads
  - Dangle endpoints (dead ends)
- Outputs to unified folder structure

---

## Road QC Module

### Overview

The Road QC module (new in v1.0.2) detects spatial errors in road networks:

| Check | Error Type | Description |
|-------|------------|-------------|
| Disconnected | `disconnected_segment` | Roads not connected to any other road |
| Self-Intersection | `self_intersection` | Roads that cross themselves |
| Dangles | `dangle` | Dead-end endpoints (excludes boundary edges) |

### CLI Usage

```bash
python scripts/run_qc.py \
  --buildings path/to/buildings.shp \
  --roads path/to/roads.shp \
  --road-qc \
  --out outputs
```

### Python API

```python
from pathlib import Path
from ovc.road_qc import run_road_qc

outputs = run_road_qc(
    roads_path=Path("data/roads.shp"),
    boundary_path=Path("boundary.shp"),  # Optional, for dangle filtering
    out_dir=Path("outputs/road_qc"),
)

print(f"Total errors: {outputs.total_errors}")
print(f"Top 3: {outputs.top_3_errors}")
```

### Outputs

```
outputs/road_qc/
├── road_qc.gpkg            # GeoPackage with roads, errors, boundary
├── road_qc_map.html        # Interactive web map with legend
└── road_qc_metrics.csv     # Summary metrics
```

### GeoPackage Layers

| Layer | Description |
|-------|-------------|
| `roads` | All roads in the analysis area |
| `errors` | Detected errors (with `error_type` column) |
| `boundary` | Analysis boundary |

### Metrics CSV

```csv
category,metric,value
summary,total_errors,142
error_counts,count_dangle,89
error_counts,count_disconnected_segment,38
error_counts,count_self_intersection,15
ranking,top_1_error_type,dangle
ranking,top_1_count,89
```

### Understanding Dangle Detection

Dangles are endpoints that connect to only one road segment. OVC intelligently filters out:

- **Boundary edges:** Endpoints near the study area boundary (roads exiting the area)
- **Network endpoints:** True network endpoints are correctly identified as issues

This prevents false positives for roads that naturally exit the analysis area.

---

## Input Data Formats

### Supported Formats

OVC supports the following geospatial formats:

- **Shapefile** (`.shp`) — Classic GIS format
- **GeoJSON** (`.geojson`, `.json`) — Web-friendly format
- **GeoPackage** (`.gpkg`) — Modern SQLite-based format
- **KML** (`.kml`) — Google Earth format
- **GML** (`.gml`) — Geography Markup Language

### Data Requirements

#### Buildings Dataset

**Required fields:**
- Geometry type: `Polygon` or `MultiPolygon`

**Optional fields:**
- `id` or `osm_id` — Unique identifier
- `name` — Building name
- `building` — Building type
- Any additional attributes are preserved in outputs

#### Roads Dataset

**Required fields:**
- Geometry type: `LineString` or `MultiLineString`

**Optional fields:**
- `id` or `osm_id` — Unique identifier
- `name` — Road name
- `highway` — Road classification
- `surface` — Road surface type

#### Boundary Dataset

**Required fields:**
- Geometry type: `Polygon` or `MultiPolygon`
- Must be a single feature (if multiple features, union is performed)

**Coordinate System:**
- WGS84 (EPSG:4326) recommended
- Any projected CRS is acceptable

---

## Output Formats

### Output Directory Structure

When OVC completes, your output directory contains:

```
outputs/
├── building_qc/
│   ├── building_qc.gpkg          # All building layers
│   ├── building_qc_map.html      # Interactive web map
│   └── building_qc_metrics.csv   # Summary metrics
└── road_qc/                      # Only when --road-qc enabled
    ├── road_qc.gpkg
    ├── road_qc_map.html
    └── road_qc_metrics.csv
```

### GeoPackage Files

Building QC GeoPackage layers:
- `buildings` — All buildings analyzed
- `errors` — Buildings with issues (overlap, road conflict, boundary violation)
- `roads` — Road network
- `boundary` — Analysis boundary

Road QC GeoPackage layers:
- `roads` — All roads analyzed
- `errors` — Road errors (disconnected, self-intersection, dangle)
- `boundary` — Analysis boundary

### CSV Reports

Metrics CSV format:
```csv
category,metric,value
summary,total_errors,45
error_counts,count_overlap,23
error_counts,count_road_conflict,15
ranking,top_1_error_type,overlap
ranking,top_1_count,23
```

### Interactive HTML Maps

**Features:**
- Pan and zoom controls
- Layer toggles (toggle visibility)
- Click features for attribute information
- Color-coded by error type
- Legend with error type definitions
- Copyright: © OVC — Overlap Violation Checker

**Opening the map:**
```bash
# Linux/macOS
open outputs/building_qc/building_qc_map.html

# Windows
start outputs/building_qc/building_qc_map.html
```

---

## Troubleshooting

### Common Issues

#### 1. GDAL Not Found

**Error:**
```
ImportError: GDAL library not found
```

**Solution:**
```bash
# Ubuntu/Debian
sudo apt-get install libgdal-dev

# macOS
brew install gdal

# Windows - use conda
conda install -c conda-forge gdal
```

#### 2. Memory Issues

**Error:**
```
MemoryError: Unable to allocate array
```

**Solution:**
- Process smaller areas
- Increase system RAM
- Use spatial filtering:
```bash
ogr2ogr -clipsrc minx miny maxx maxy subset.shp large.shp
```

#### 3. Invalid Geometries

**Error:**
```
TopologyException: Invalid geometry
```

**Solution:**
```bash
# Fix geometries using GDAL
ogr2ogr -makevalid fixed.shp broken.shp
```

#### 4. Data Loading Errors

**Error:**
```
File not found or unsupported format
```

**Solution:**
- Verify the file path is correct
- Ensure the file format is supported (Shapefile, GeoJSON, GeoPackage, KML, GML)
- Check that all sidecar files are present (e.g., `.shx`, `.dbf` for Shapefiles)

### Getting Help

If you encounter issues not covered here:

1. **Check existing issues:** [GitHub Issues](https://github.com/AmmarYasser455/ovc/issues)
2. **Open a new issue** with:
   - Your command/code
   - Error message
   - System information (OS, Python version)
   - Sample data (if possible)

---

## Programmatic Usage

### Building QC API

```python
from pathlib import Path
from ovc.export.pipeline import run_pipeline

outputs = run_pipeline(
    buildings_path=Path("data/buildings.gpkg"),
    out_dir=Path("results"),
    boundary_path=Path("data/boundary.shp"),
    roads_path=Path("data/roads.gpkg"),
)

print(f"GeoPackage: {outputs.gpkg_path}")
print(f"Web map: {outputs.webmap_html}")
```

### Road QC API

```python
from pathlib import Path
from ovc.road_qc import run_road_qc

outputs = run_road_qc(
    roads_path=Path("data/roads.shp"),
    boundary_path=Path("data/boundary.shp"),
    out_dir=Path("results/road_qc")
)

print(f"Total errors: {outputs.total_errors}")
print(f"Top 3 errors: {outputs.top_3_errors}")
```

### Combined Pipeline

```python
from pathlib import Path
from ovc.export.pipeline import run_pipeline
from ovc.road_qc import run_road_qc

boundary = Path("data/boundary.shp")
buildings = Path("data/buildings.gpkg")
roads = Path("data/roads.shp")
out = Path("results")

# Run Building QC
building_outputs = run_pipeline(
    buildings_path=buildings,
    out_dir=out,
    boundary_path=boundary,
    roads_path=roads,
)

# Run Road QC
road_outputs = run_road_qc(
    roads_path=roads,
    boundary_path=boundary,
    out_dir=out / "road_qc"
)

print(f"Building errors: see {building_outputs.gpkg_path}")
print(f"Road errors: {road_outputs.total_errors}")
```

---

## Best Practices

### Data Preparation

1. **Always validate geometries first:**
   ```bash
   ogr2ogr -makevalid clean.shp raw.shp
   ```

2. **Use consistent coordinate systems:**
   - WGS84 (EPSG:4326) for global data
   - Local projected CRS for accurate measurements

3. **Clean attribute tables:**
   - Remove unnecessary fields
   - Ensure unique identifiers exist

### Quality Control Workflow

1. **Start small:** Test with a subset before processing entire dataset
2. **Review outputs:** Always inspect the HTML map visually
3. **Iterate:** Adjust configuration thresholds based on results
4. **Document:** Keep notes on configuration changes and results

### Performance Tips

1. **Use GeoPackage for large datasets** (faster than Shapefile)
2. **Process in projected CRS** for accurate area calculations
3. **Limit analysis extent** to areas of interest
4. **Close unnecessary applications** to free memory

---

## Next Steps

- **Learn by example:** Check out [Examples](examples.md)
- **Follow tutorials:** See [Tutorials](tutorials.md)
- **Explore the API:** Read [API Reference](api-reference.md)
- **Get involved:** Visit [Contributing Guide](https://github.com/AmmarYasser455/ovc/blob/main/CONTRIBUTING.md)

---

[← Back to Documentation](index.md) | [Examples →](examples.md)