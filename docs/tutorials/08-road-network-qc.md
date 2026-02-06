---
layout: default
title: "Tutorial 8: Road Network QC"
parent: Tutorials
---

# Tutorial 8: Road Network QC

Learn how to detect and analyze road network issues using OVC's Road QC module.

**Difficulty:** Intermediate
**Time:** 20 minutes
**Version:** v1.0.2

---

## What You'll Learn

- How to run Road QC checks
- Understanding disconnected segments, self-intersections, and dangles
- Interpreting Road QC outputs
- Filtering false positives with boundary awareness

---

## Prerequisites

- OVC installed and configured
- A boundary file or road dataset
- Basic understanding of road network concepts

---

## Step 1: Understanding Road QC Checks

Road QC detects three types of issues in road networks:

| Check | Error Type | Description |
|-------|------------|-------------|
| **Disconnected** | `disconnected_segment` | Roads not connected to any other road |
| **Self-Intersection** | `self_intersection` | Roads that cross themselves |
| **Dangle** | `dangle` | Dead-end endpoints (may indicate incomplete digitization) |

---

## Step 2: Run Road QC via CLI

### Basic Usage

```bash
python scripts/run_qc.py \
  --boundary data/boundary.geojson \
  --road-qc \
  --out outputs
```

This downloads roads from OSM and runs all Road QC checks.

### With Custom Roads

```bash
python scripts/run_qc.py \
  --boundary data/boundary.geojson \
  --roads data/my_roads.shp \
  --road-qc \
  --out outputs
```

---

## Step 3: Understanding the Outputs

After running Road QC, you'll find:

```
outputs/road_qc/
├── road_qc.gpkg            # GeoPackage with all layers
├── road_qc_map.html        # Interactive web map
└── road_qc_metrics.csv     # Summary metrics
```

### GeoPackage Layers

Open `road_qc.gpkg` in QGIS to explore:

| Layer | Description |
|-------|-------------|
| `roads` | All roads analyzed |
| `errors` | Detected errors (filter by `error_type`) |
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

### Web Map

Open `road_qc_map.html` in a browser to see:

- **Blue lines:** All roads (reference layer)
- **Red lines:** Disconnected segments
- **Purple lines:** Self-intersecting roads
- **Orange points:** Dangle endpoints

---

## Step 4: Run Road QC via Python

```python
from pathlib import Path
from ovc.road_qc import run_road_qc

outputs = run_road_qc(
    boundary_path=Path("data/boundary.geojson"),
    out_dir=Path("outputs/road_qc")
)

print(f"Total errors: {outputs.total_errors}")
print(f"GeoPackage: {outputs.gpkg_path}")
print(f"Web map: {outputs.webmap_html}")

# Print top 3 errors
print("Top 3 errors:")
for error_type, count in outputs.top_3_errors:
    print(f"  {error_type}: {count}")
```

---

## Step 5: Customizing Road QC

### Adjust Tolerances

```python
from ovc.road_qc.config import RoadQCConfig
from ovc.road_qc import run_road_qc

# More tolerant settings
config = RoadQCConfig(
    disconnect_tolerance_m=10.0,  # 10m tolerance for connections
    dangle_tolerance_m=5.0        # 5m tolerance for dangle grouping
)

outputs = run_road_qc(
    boundary_path=...,
    out_dir=...,
    config=config
)
```

### Using Pre-loaded Data

```python
import geopandas as gpd
from ovc.road_qc import run_road_qc

# Load your own roads
roads = gpd.read_file("data/my_roads.gpkg")
boundary = gpd.read_file("data/boundary.geojson")

outputs = run_road_qc(
    roads_gdf=roads,
    boundary_gdf=boundary,  # Used for dangle filtering
    out_dir=Path("outputs/road_qc")
)
```

---

## Step 6: Understanding Dangle Detection

Dangles are endpoints that connect to only one road segment. However, not all dangles are errors:

### True Dangles (Issues)
- Incomplete digitization (road should continue)
- Missing connections between roads
- Data gaps

### False Positives (Filtered Out)
- Roads naturally exiting the study area boundary
- Cul-de-sacs (intentional dead ends)
- Highway on-ramps

### How OVC Filters Boundary Edges

OVC automatically filters out endpoints near the boundary:

```python
# Boundary is passed for filtering
outputs = run_road_qc(
    boundary_path=Path("boundary.geojson"),  # Used for filtering
    out_dir=Path("outputs/road_qc")
)
```

This prevents false positives for roads that exit your study area.

---

## Step 7: Analyzing Results in QGIS

1. **Open GeoPackage:**
   - Drag `road_qc.gpkg` into QGIS

2. **Filter by Error Type:**
   ```
   "error_type" = 'dangle'
   ```

3. **Style by Error Type:**
   - Categorized renderer on `error_type` field
   - Use distinct colors for each type

4. **Identify Patterns:**
   - Clusters of dangles may indicate systematic issues
   - Isolated disconnected segments need individual review

---

## Step 8: Combining with Building QC

Run both Building QC and Road QC together:

```bash
python scripts/run_qc.py \
  --boundary data/boundary.geojson \
  --road-qc \
  --out outputs
```

Outputs:
```
outputs/
├── building_qc/
│   ├── building_qc.gpkg
│   ├── building_qc_map.html
│   └── building_qc_metrics.csv
└── road_qc/
    ├── road_qc.gpkg
    ├── road_qc_map.html
    └── road_qc_metrics.csv
```

---

## Summary

You've learned how to:

- Run Road QC checks via CLI and Python
- Interpret disconnected segments, self-intersections, and dangles
- Customize Road QC configuration
- Use boundary filtering to reduce false positives
- Analyze results in QGIS

---

## Next Steps

- **[Tutorial 7: Automating with Python](07-automating-qc-with-python.md)** — Build automated pipelines
- **[Examples](../examples.md)** — Quick code snippets
- **[API Reference](../api-reference.md)** — Full Python API documentation

---

[← Tutorials](../tutorials.md) | [Examples →](../examples.md)
