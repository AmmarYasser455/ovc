# Road QC Module

Road quality control module for OVC. Detects spatial errors in road networks.

## Checks

| Check | Error Type | Description |
|-------|------------|-------------|
| Disconnected | `disconnected_segment` | Roads not connected to any other road |
| Self-Intersection | `self_intersection` | Roads that cross themselves |
| Dangles | `dangle` | Dead-end endpoints (excludes boundary edges) |

## Usage

### CLI

```bash
python scripts/run_qc.py \
  --boundary path/to/boundary.shp \
  --road-qc \
  --out outputs
```

### Python API

```python
from pathlib import Path
from ovc.road_qc import run_road_qc

outputs = run_road_qc(
    boundary_path=Path("boundary.shp"),
    out_dir=Path("outputs/road_qc"),
)

print(f"Total errors: {outputs.total_errors}")
print(f"Top 3: {outputs.top_3_errors}")
```

## Outputs

```
outputs/road_qc/
├── road_qc.gpkg            # GeoPackage with roads, errors, boundary
├── road_qc_map.html        # Interactive web map with legend
└── road_qc_metrics.csv     # Summary metrics
```

## Configuration

```python
from ovc.road_qc.config import RoadQCConfig

config = RoadQCConfig(
    disconnect_tolerance_m=5.0,   # Endpoint connection tolerance
    dangle_tolerance_m=2.0,       # Dangle grouping tolerance
)
```

## Module Structure

```
ovc/road_qc/
├── __init__.py           # Exports: run_road_qc, RoadQCConfig
├── config.py             # RoadQCConfig dataclass
├── checks/
│   ├── disconnected.py   # Disconnected segment detection
│   ├── self_intersection.py
│   └── dangles.py        # Dangle detection (filters boundary edges)
├── metrics.py            # Error counting and ranking
├── pipeline.py           # run_road_qc() orchestration
└── webmap.py             # Interactive map generation
```
