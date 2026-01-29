# Road QC Module

Road quality control checks for the OVC framework.

## Overview

The Road QC module detects common spatial errors in road datasets, whether digitized manually or imported from OpenStreetMap. It identifies and ranks the **top 3 most frequent road-related errors**.

## Checks Performed

| Check | Description |
|-------|-------------|
| **Disconnected Segments** | Roads not connected to the network |
| **Self-Intersections** | Roads that cross themselves |
| **Dangles** | Dead-end endpoints (potential incomplete digitization) |

## Usage

### Python API

```python
from pathlib import Path
from ovc.road_qc import run_road_qc, RoadQCConfig

# Run with local road file
outputs = run_road_qc(
    roads_path=Path("data/roads.geojson"),
    out_dir=Path("outputs/road_qc")
)

# Or download from OSM
outputs = run_road_qc(
    boundary_path=Path("data/boundary.geojson"),
    out_dir=Path("outputs/road_qc")
)

# Or with custom config
config = RoadQCConfig(
    dangle_tolerance_m=2.0,
    disconnect_tolerance_m=5.0
)
outputs = run_road_qc(
    roads_path=Path("data/roads.geojson"),
    out_dir=Path("outputs/road_qc"),
    config=config
)

print(f"Total errors: {outputs.total_errors}")
print(f"Top 3 errors: {outputs.top_3_errors}")
```

### CLI

```bash
python scripts/run_qc.py \
  --roads data/roads.geojson \
  --road-qc \
  --out outputs
```

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `dangle_tolerance_m` | 1.0 | Max gap to consider endpoints connected |
| `disconnect_tolerance_m` | 2.0 | Max distance to nearest road endpoint |
| `self_intersection_buffer_m` | 0.1 | Buffer for intersection detection |
| `min_segment_length_m` | 0.5 | Ignore shorter segments |

## Outputs

| File | Description |
|------|-------------|
| `road_qc_errors.gpkg` | GeoPackage with error geometries |
| `road_qc_metrics.csv` | Error counts and top-3 ranking |

## Module Structure

```
ovc/road_qc/
├── __init__.py       # Public exports
├── config.py         # RoadQCConfig
├── checks/
│   ├── disconnected.py
│   ├── self_intersection.py
│   └── dangles.py
├── metrics.py        # Error aggregation
├── pipeline.py       # run_road_qc()
└── README.md
```
