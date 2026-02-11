---
layout: default
title: Tutorial 2 - Working with Local Data
parent: Tutorials
nav_order: 2
---

# Tutorial 2: Working with Local Data

**Goal:** Load and validate your own buildings and roads datasets with OVC.

**Prerequisites:**
- OVC installed
- Local buildings dataset (Shapefile, GeoJSON, or GeoPackage)

**Time:** 15 minutes

### Step 1: Prepare Your Data

OVC works with local geospatial files. Gather your datasets:

- **Buildings** (required): Polygon geometries representing building footprints
- **Roads** (optional): LineString geometries for road-building conflict checks
- **Boundary** (optional): A polygon defining your area of interest

**Supported formats:** Shapefile (`.shp`), GeoJSON (`.geojson`), GeoPackage (`.gpkg`), KML (`.kml`), GML (`.gml`)

### Step 2: Organize Your Files

Create a clean project structure:

```bash
mkdir -p project/{data,results}

# Copy your data files into the data directory
cp /path/to/my_buildings.shp project/data/
cp /path/to/my_roads.shp project/data/
cp /path/to/my_boundary.geojson project/data/
```

### Step 3: Run QC with Buildings Only

The simplest workflow — just provide your buildings file:

```bash
python scripts/run_qc.py \
  --buildings project/data/my_buildings.shp \
  --out project/results/basic_qc
```

**What happens:**
- OVC loads your buildings
- Checks for overlapping and duplicate geometries
- Generates reports and an interactive map

### Step 4: Add Roads for Conflict Checks

Provide a roads file to detect buildings that overlap roads:

```bash
python scripts/run_qc.py \
  --buildings project/data/my_buildings.shp \
  --roads project/data/my_roads.shp \
  --out project/results/full_qc
```

**What happens:**
- Buildings are checked for overlaps
- Buildings intersecting road buffers are flagged
- All results are saved to the output directory

### Step 5: Add a Boundary for Containment Checks

Provide a boundary to also check that buildings fall within your area of interest:

```bash
python scripts/run_qc.py \
  --buildings project/data/my_buildings.shp \
  --roads project/data/my_roads.shp \
  --boundary project/data/my_boundary.geojson \
  --out project/results/complete_qc \
  --verbose
```

With `--verbose`, you'll see progress:

```
[INFO] Loading buildings from project/data/my_buildings.shp
[INFO] Loaded 3,421 buildings
[INFO] Loading roads from project/data/my_roads.shp
[INFO] Loaded 245 road segments
[INFO] Loading boundary from project/data/my_boundary.geojson
[INFO] Running overlap detection...
[INFO] Found 156 overlapping building pairs
[INFO] Running boundary validation...
[INFO] Found 12 boundary violations
[INFO] Running road conflict detection...
[INFO] Found 45 road conflicts
[INFO] Generating outputs...
[INFO] QC complete! Results saved to project/results/complete_qc
```

### Step 6: Examine the Results

Navigate to the output directory:

```bash
cd project/results/complete_qc/building_qc
ls -lh
```

You should see:
```
building_qc.gpkg
building_qc_map.html
building_qc_metrics.csv
```

Open the interactive map in your browser:

```bash
# Linux
xdg-open building_qc_map.html

# macOS
open building_qc_map.html

# Windows
start building_qc_map.html
```

### Step 7: Common Data Preparation Tips

If your data needs cleaning before QC:

```bash
# Reproject to WGS84
ogr2ogr -t_srs EPSG:4326 buildings_wgs84.shp buildings_local_crs.shp

# Fix invalid geometries
ogr2ogr -makevalid buildings_clean.shp buildings_wgs84.shp

# Convert Shapefile to GeoPackage
ogr2ogr -f GPKG buildings.gpkg buildings.shp
```

### Step 8: Using the Python API

You can also load local data programmatically:

```python
from pathlib import Path
from ovc.export.pipeline import run_pipeline

outputs = run_pipeline(
    buildings_path=Path("project/data/my_buildings.shp"),
    out_dir=Path("project/results/api_qc"),
    roads_path=Path("project/data/my_roads.shp"),
    boundary_path=Path("project/data/my_boundary.geojson"),
)

print(f"GeoPackage: {outputs.gpkg_path}")
print(f"Web map: {outputs.webmap_html}")
print(f"Metrics: {outputs.metrics_csv}")
```

**Congratulations!** You know how to load and validate local geospatial data with OVC.

---

[Next: Custom Configuration →](03-custom-configuration.md)
