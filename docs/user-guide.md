---
layout: default
title: User Guide - OVC
---

# OVC User Guide

Complete guide to installing, configuring, and using the Overlap Violation Checker.

---

## Table of Contents

1. [Installation](#installation)
2. [System Requirements](#system-requirements)
3. [Configuration](#configuration)
4. [Command-Line Usage](#command-line-usage)
5. [Input Data Formats](#input-data-formats)
6. [Output Formats](#output-formats)
7. [Troubleshooting](#troubleshooting)
8. [Programmatic Usage](#programmatic-usage)
9. [Best Practices](#best-practices)

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
pip install -r requirements.txt
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
ovc/core/config.py
```

### Configuration Classes

OVC provides three main configuration dataclasses:

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

**Config** — Main configuration container:
```python
@dataclass(frozen=True)
class Config:
    overlap: OverlapConfig = OverlapConfig()
    road_conflict: RoadConflictThresholds = RoadConflictThresholds()
    tags: Tags = Tags(
        buildings={"building": True},
        roads={"highway": True},
    )
```

### Customizing Configuration

Create a custom Config object and pass it to `run_pipeline`:

```python
from ovc.core.config import Config, OverlapConfig, RoadConflictThresholds
from ovc.export.pipeline import run_pipeline

# Create custom config
custom_config = Config(
    overlap=OverlapConfig(
        min_intersection_area_m2=0.1,  # Stricter detection
        partial_ratio_min=0.15         # Flag smaller overlaps
    ),
    road_conflict=RoadConflictThresholds(
        road_buffer_m=2.0              # Larger road buffer
    )
)

# Run with custom config
run_pipeline(
    boundary_path=...,
    out_dir=...,
    config=custom_config
)
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
| `--buildings` | Path | Path to buildings dataset (Shapefile, GeoJSON, GPKG) |
| `--roads` | Path | Path to roads dataset (optional) |
| `--boundary` | Path | Path to boundary polygon (optional) |
| `--out` | Path | Output directory for results |
| `--crs` | String | Target coordinate reference system (default: EPSG:4326) |
| `--verbose` | Flag | Enable detailed logging |
| `--help` | Flag | Show help message |

### Usage Modes

#### Mode 1: Buildings Only

Use your own buildings data; roads are downloaded from OSM.

```bash
python scripts/run_qc.py \
  --buildings data/my_buildings.shp \
  --out results/mode1
```

**What happens:**
- Loads your building dataset
- Derives analysis extent from buildings
- Downloads roads from OpenStreetMap
- Performs overlap and road conflict checks

#### Mode 2: Buildings and Roads

Use both your own buildings and roads datasets.

```bash
python scripts/run_qc.py \
  --buildings data/my_buildings.geojson \
  --roads data/my_roads.geojson \
  --out results/mode2
```

**What happens:**
- Loads both datasets
- No OSM downloads
- Performs all validation checks
- Uses provided data exclusively

#### Mode 3: Boundary-Based OSM Download

Download both buildings and roads from OSM within a boundary.

```bash
python scripts/run_qc.py \
  --boundary data/city_boundary.geojson \
  --out results/mode3
```

**What happens:**
- Downloads buildings from OSM
- Downloads roads from OSM
- Performs all checks including boundary validation
- Analyzes OSM data quality

#### Mode 4: Mixed Mode

Provide buildings and boundary; roads are downloaded from OSM.

```bash
python scripts/run_qc.py \
  --buildings data/my_buildings.shp \
  --boundary data/district.geojson \
  --out results/mode4
```

**What happens:**
- Uses your buildings
- Downloads roads from OSM
- Validates buildings against boundary
- Performs road conflict checks

### Advanced Options

**Specify coordinate system:**
```bash
python scripts/run_qc.py \
  --buildings data/buildings.shp \
  --crs EPSG:32633 \
  --out results
```

**Enable verbose logging:**
```bash
python scripts/run_qc.py \
  --buildings data/buildings.shp \
  --out results \
  --verbose
```

**Process multiple areas:**
```bash
for boundary in boundaries/*.geojson; do
  python scripts/run_qc.py \
    --boundary "$boundary" \
    --out "results/$(basename $boundary .geojson)"
done
```

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

**Example structure:**
```
buildings.shp
├── POLYGON geometries
└── attributes: id, name, building_type
```

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

### Data Preparation Tips

**1. Ensure valid geometries:**
```bash
# Using GDAL/OGR
ogr2ogr -makevalid output.shp input.shp
```

**2. Reproject if needed:**
```bash
ogr2ogr -t_srs EPSG:4326 output.shp input.shp
```

**3. Merge multiple files:**
```bash
ogr2ogr merged.gpkg file1.shp
ogr2ogr -update -append merged.gpkg file2.shp
```

**4. Simplify complex geometries:**
```bash
ogr2ogr -simplify 0.5 simplified.shp complex.shp
```

---

## Output Formats

### Output Directory Structure

When OVC completes, your output directory contains:

```
outputs/
├── building_overlaps.geojson       # Overlapping building pairs
├── building_overlaps.csv           # Overlap statistics
├── boundary_violations.geojson     # Buildings outside boundary
├── boundary_violations.csv         # Boundary violation details
├── road_conflicts.geojson          # Road-building intersections
├── road_conflicts.csv              # Road conflict metrics
├── validation_report.html          # Interactive web map
└── summary_statistics.csv          # Overall QC summary
```

### GeoJSON Files

**Purpose:** Spatial visualization and analysis in GIS software

**Structure:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {...},
      "properties": {
        "building_id": "123",
        "overlap_area": 45.2,
        "overlap_percentage": 12.5,
        "severity": "medium"
      }
    }
  ]
}
```

**Usage:**
- Load into QGIS, ArcGIS, or other GIS software
- Process with Python (GeoPandas, Fiona)
- Visualize in web mapping libraries (Leaflet, Mapbox)

### CSV Reports

**Purpose:** Statistical analysis and reporting

**Building Overlaps CSV:**
```csv
building_a,building_b,overlap_area,overlap_pct_a,overlap_pct_b,severity
101,102,45.23,12.5,8.3,medium
103,104,120.45,35.2,33.8,high
```

**Boundary Violations CSV:**
```csv
building_id,violation_type,distance_from_boundary,area_outside
201,outside_boundary,15.3,78.5
202,partial_overlap,0.0,22.1
```

**Road Conflicts CSV:**
```csv
building_id,road_id,conflict_type,intersection_area,distance
301,R45,intersection,5.2,0.0
302,R46,proximity,0.0,1.8
```

### Interactive HTML Map

**Purpose:** Visual inspection and stakeholder communication

**Features:**
- Pan and zoom controls
- Layer toggles (buildings, roads, violations)
- Click features for attribute information
- Color-coded by severity
- Basemap options (OSM, satellite)

**Opening the map:**
```bash
# Linux/macOS
open outputs/validation_report.html

# Windows
start outputs/validation_report.html
```

### Summary Statistics

**Purpose:** High-level QC metrics

**Example content:**
```csv
metric,value
total_buildings,1523
overlapping_buildings,87
boundary_violations,12
road_conflicts,34
overlap_percentage,5.7
critical_issues,8
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

#### 2. Projection Errors

**Error:**
```
CRS mismatch: buildings are in EPSG:4326 but roads are in EPSG:32633
```

**Solution:**
OVC automatically reprojects data, but you can manually ensure consistency:
```bash
ogr2ogr -t_srs EPSG:4326 roads_wgs84.shp roads.shp
```

#### 3. Memory Issues

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

#### 4. Invalid Geometries

**Error:**
```
TopologyException: Invalid geometry
```

**Solution:**
```bash
# Fix geometries using GDAL
ogr2ogr -makevalid fixed.shp broken.shp
```

#### 5. OSM Download Fails

**Error:**
```
OSM download timeout or connection error
```

**Solution:**
- Check internet connection
- Try smaller boundary area
- Use local OSM extracts instead
- Wait and retry (OSM servers may be busy)

### Performance Optimization

**For large datasets:**

1. **Use GeoPackage instead of Shapefile:**
```bash
ogr2ogr buildings.gpkg buildings.shp
```

2. **Simplify geometries before processing:**
```bash
ogr2ogr -simplify 1.0 simplified.shp original.shp
```

3. **Process in batches:**
```bash
# Split large dataset
ogr2ogr -where "id < 10000" batch1.shp large.shp
ogr2ogr -where "id >= 10000" batch2.shp large.shp
```

### Getting Help

If you encounter issues not covered here:

1. **Check existing issues:** [GitHub Issues](https://github.com/AmmarYasser455/ovc/issues)
2. **Search documentation:** [OVC Documentation](https://ammaryasser455.github.io/ovc)
3. **Ask the community:** Open a new issue with:
   - Your command/code
   - Error message
   - System information (OS, Python version)
   - Sample data (if possible)

---

## Programmatic Usage

While this User Guide focuses on command-line usage, OVC can also be used as a Python library for integration into custom workflows, automated pipelines, and advanced use cases.

### When to Use the Python API

- **Automated pipelines:** Integrate QC checks into ETL or CI/CD workflows
- **Custom processing:** Chain OVC with other Python geospatial libraries
- **Batch operations:** Process multiple datasets programmatically
- **Custom reporting:** Generate tailored reports from QC results

### Quick Example

```python
from pathlib import Path
from ovc.export.pipeline import run_pipeline

# Configure and run pipeline
outputs = run_pipeline(
    boundary_path=None,
    buildings_path=Path("data/buildings.shp"),
    roads_path=Path("data/roads.shp"),
    out_dir=Path("results")
)

print(f"Results saved to: {outputs.metrics_csv}")
```

### Learn More

For complete Python API documentation, see:
- **[API Reference](api-reference.md)** — Full class and method documentation
- **[Examples](examples.md)** — Python integration examples
- **[Tutorial 7: Automating QC with Python](tutorials/07-automating-qc-with-python.md)** — Step-by-step automation guide

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

### Integration with GIS Software

**QGIS:**
```
1. Drag and drop GeoJSON files into QGIS
2. Style by severity attribute
3. Use "Identify Features" tool to inspect violations
```

**ArcGIS Pro:**
```
1. Add Data → Navigate to output directory
2. Import GeoJSON or convert to Shapefile
3. Symbolize by attributes
```

**Python/GeoPandas:**
```python
import geopandas as gpd

# Load results
overlaps = gpd.read_file('outputs/building_overlaps.geojson')

# Filter high severity
critical = overlaps[overlaps['severity'] == 'high']

# Spatial join with original data
result = gpd.sjoin(buildings, overlaps, how='left')
```

---

## Next Steps

- **Learn by example:** Check out [Examples](examples.md)
- **Follow tutorials:** See [Tutorials](tutorials.md)
- **Explore the API:** Read [API Reference](api-reference.md)
- **Get involved:** Visit [Contributing Guide](https://github.com/AmmarYasser455/ovc/blob/main/CONTRIBUTING.md)

---

[← Back to Documentation](index.md) | [Examples →](examples.md)