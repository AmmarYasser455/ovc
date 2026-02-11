<p align="center">
  <img src="https://raw.githubusercontent.com/AmmarYasser455/ovc/main/docs/assets/logo.png" alt="OVC Logo" width="200">
</p>

<h1 align="center">OVC — Overlap Violation Checker</h1>

<p align="center">
  <strong>Spatial Quality Control for Building & Road Datasets</strong><br>
  <em>Detect overlaps, conflicts, and topological issues — locally, offline, and fast</em>
</p>

<p align="center">
  <a href="https://github.com/AmmarYasser455/ovc"><img src="https://img.shields.io/badge/version-v3.0.0-blue?style=flat-square" alt="Version"></a>
  <a href="https://github.com/AmmarYasser455/ovc"><img src="https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square" alt="Python"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License"></a>
  <a href="https://github.com/AmmarYasser455/ovc/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/AmmarYasser455/ovc/ci.yml?style=flat-square&label=CI" alt="CI"></a>
</p>

---

## What is OVC?

**OVC** is a Python-based spatial quality control tool for detecting geometric and topological issues in **building and road datasets**. It validates your local geospatial data — Shapefiles, GeoJSON, GeoPackage — detecting overlapping buildings, boundary violations, road conflicts, and road network problems.

- **Detect** building overlaps (duplicate and partial) with vectorized spatial joins
- **Validate** boundary compliance and building-road conflicts
- **Analyze** road networks — disconnected segments, self-intersections, dangles
- **Check** geometry quality — invalid geometries, area reasonableness, compactness
- **Visualize** results on interactive web maps with issue highlighting
- **Export** GeoPackage, CSV reports, and HTML web maps
- **Pre-check** data quality with [GeoQA](https://github.com/AmmarYasser455/geoqa) integration

No internet connection required. No API rate limits. Just point OVC at your data files and get results.

<div align="center">

### Building QC
<img src="docs/assets/buildings_wm.jpg" alt="OVC Building QC Results" width="800"/>

### Road QC
<img src="docs/assets/road_wm.jpg" alt="OVC Road QC Results" width="800"/>

</div>

## Key Features

| Feature | Description |
|---|---|
| **Building Overlap Detection** | Identify duplicate and partial overlaps via vectorized spatial joins |
| **Boundary Compliance** | Validate building footprints against administrative boundaries |
| **Road Conflict Analysis** | Detect buildings conflicting with road geometries |
| **Road Network QC** | Disconnected segments, self-intersections, and dangle detection |
| **Geometry Quality** | Invalid geometry, area reasonableness, compactness score, setback violations |
| **GeoQA Pre-Check** | Automated data-readiness gate before running QC pipeline |
| **Interactive Web Maps** | Folium-based maps with legends and issue highlighting |
| **Multi-Format I/O** | Shapefile, GeoJSON, GeoPackage input → GeoPackage, CSV, HTML output |
| **Offline & Fast** | No internet required, vectorized spatial joins (10–50× faster than loops) |

## Installation

```bash
git clone https://github.com/AmmarYasser455/ovc.git
cd ovc
pip install -e ".[dev]"
```

**Or install dependencies only:**

```bash
pip install -r requirements.txt
```

**Requirements:** Python 3.10+ — depends on geopandas, shapely, pyproj, pandas, folium, fiona, and rtree.

## Quick Start

### CLI

```bash
# Buildings only (minimum required)
python scripts/run_qc.py --buildings buildings.shp --out outputs

# Buildings + Roads
python scripts/run_qc.py --buildings buildings.shp --roads roads.shp --out outputs

# Buildings + Roads + Boundary
python scripts/run_qc.py --buildings buildings.shp --roads roads.shp --boundary boundary.shp --out outputs

# Enable Road QC
python scripts/run_qc.py --buildings buildings.shp --roads roads.shp --road-qc --out outputs

# Run GeoQA pre-check before QC
python scripts/run_qc.py --buildings buildings.shp --roads roads.shp --precheck --out outputs

# Run ONLY the pre-check (skip QC)
python scripts/run_qc.py --buildings buildings.shp --precheck-only --out outputs
```

### Python API

```python
from ovc.export.pipeline import run_pipeline
from pathlib import Path

outputs = run_pipeline(
    buildings_path=Path("data/buildings.shp"),
    roads_path=Path("data/roads.shp"),
    boundary_path=Path("data/boundary.shp"),
    out_dir=Path("outputs"),
)
print(f"GeoPackage: {outputs.gpkg_path}")
print(f"Web map:    {outputs.webmap_html}")
```

### Geometry Quality Checks API

```python
from ovc.checks.geometry_quality import (
    find_duplicate_geometries,
    find_invalid_geometries,
    find_unreasonable_areas,
    compute_compactness,
    find_min_road_distance_violations,
)

dupes = find_duplicate_geometries(buildings_metric)
invalid = find_invalid_geometries(buildings_metric)
area_issues = find_unreasonable_areas(buildings_metric, min_area_m2=4.0)
compact = compute_compactness(buildings_metric, min_compactness=0.2)
setback = find_min_road_distance_violations(buildings_metric, roads_metric, min_distance_m=3.0)
```

### Notes

- `--buildings` is **required** — this is the data OVC checks
- `--boundary` is optional — enables boundary overlap and outside-boundary checks
- `--roads` is optional — enables building-on-road conflict checks
- `--road-qc` requires `--roads` — runs road network quality checks
- All input files can be Shapefile, GeoJSON, GeoPackage, or any format supported by Fiona

## GeoQA Integration

OVC integrates with [**GeoQA**](https://github.com/AmmarYasser455/geoqa) — a Python package for geospatial data quality assessment — as a **data-readiness gate** before running the QC pipeline.

When you pass `--precheck`, OVC uses GeoQA to:

1. **Profile** each input dataset (buildings, roads, boundary)
2. **Compute** a quality score (0–100) based on geometry validity, attribute completeness, and CRS
3. **Detect** invalid, empty, duplicate, and null geometries
4. **Run** topology checks (slivers, bad rings, overlaps)
5. **Classify** issues as **warnings** (proceed with caution) or **blockers** (stop — fix data first)
6. **Generate** HTML quality reports for each dataset

Only when all datasets pass the pre-check does OVC proceed with the full QC pipeline. This catches fundamental data issues early — missing CRS, invalid geometries, empty features — saving compute time and giving clear diagnostics.

```bash
# Install GeoQA for pre-check support
pip install geoqa
```

| Workflow Step | Tool | What It Does |
|---|---|---|
| **Data Readiness** | GeoQA | Profile, validate, and score input datasets |
| **Building QC** | OVC | Overlap, boundary, and road conflict detection |
| **Road QC** | OVC | Disconnected segments, self-intersections, dangles |

## Quality Checks

### Building QC

| Check | Description |
|---|---|
| Overlap Detection | Duplicate and partial overlaps via spatial join |
| Boundary Compliance | Buildings touching or outside administrative boundary |
| Road Conflict | Buildings conflicting with road geometries |
| Duplicate Geometry | Identical building footprints (WKB comparison) |
| Invalid Geometry | Self-intersections, topology errors |
| Area Reasonableness | Unreasonably small or large buildings |
| Compactness Score | Polsby-Popper shape regularity check |
| Road Setback | Buildings too close to roads |

### Road QC

| Check | Description |
|---|---|
| Disconnected Segments | Roads not connected to the network |
| Self-Intersections | Roads that cross themselves |
| Dangles | Dead-end endpoints (incomplete digitization) |

## Outputs

```
outputs/
├── precheck/                      # GeoQA quality reports (when --precheck)
│   ├── buildings_quality_report.html
│   ├── roads_quality_report.html
│   └── boundary_quality_report.html
├── building_qc/
│   ├── building_qc.gpkg          # GeoPackage with issue layers
│   ├── building_qc_map.html      # Interactive web map
│   └── building_qc_metrics.csv   # Summary metrics
└── road_qc/                      # When --road-qc is enabled
    ├── road_qc.gpkg
    ├── road_qc_map.html
    └── road_qc_metrics.csv
```

| Output Type | Description |
|---|---|
| **GeoPackage** | Spatial layers containing detected issues |
| **CSV reports** | Summary statistics and metrics |
| **HTML web map** | Interactive map for visual inspection |
| **HTML quality report** | GeoQA pre-check assessment (when enabled) |

## Configuration

Runtime thresholds can be customized in `ovc/core/config.py`:

| Parameter | Default | Description |
|---|---|---|
| `duplicate_ratio_min` | 0.98 | Minimum overlap ratio for duplicate classification |
| `partial_ratio_min` | 0.30 | Minimum overlap ratio for partial classification |
| `min_intersection_area_m2` | 0.5 | Minimum overlap area threshold |
| `road_buffer_m` | 1.0 | Buffer distance around roads |

## Performance

| Operation | Typical Time |
|---|---|
| Building overlap detection (10k buildings) | ~20 sec |
| Road conflict detection (10k buildings) | ~30 sec |
| Full pipeline (10k buildings + roads + boundary) | ~1 min |

Key optimizations:
- Vectorized spatial joins (no Python-level loops)
- Spatial pre-filtering reduces geometry comparison count

## Architecture

```
ovc/
├── core/        # Shared utilities, CRS handling, config, spatial indexing
├── loaders/     # Data loading and preprocessing (multi-format)
├── checks/      # Building quality checks and validation logic
├── metrics/     # Statistics and summary computation
├── export/      # Output generation (GeoPackage, CSV, web maps)
├── precheck/    # GeoQA-powered data quality assessment
└── road_qc/    # Road network quality control
    ├── checks/  # Disconnected, self-intersection, dangle detection
    ├── config.py
    ├── metrics.py
    ├── pipeline.py
    └── webmap.py
```

For detailed design decisions, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Supported Formats

All vector formats readable by GeoPandas/Fiona: Shapefile, GeoJSON, GeoPackage, KML, GML, File Geodatabase, and more via GDAL/OGR drivers.

## Troubleshooting

| Issue | Cause | Fix |
|---|---|---|
| CRS warnings | Local CRS without `.prj` file | Ensure data has a valid `.prj` file |
| Out of memory | Very large areas (>500 km²) | Process in smaller boundary chunks |
| Slow processing | Large datasets with O(n²) comparisons | Vectorized joins used automatically; filter to area of interest |

## Testing

```bash
pytest                              # Run full test suite
pytest --cov=ovc --cov-report=html  # Run with coverage
```

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
git clone https://github.com/AmmarYasser455/ovc.git
cd ovc
pip install -e ".[dev]"
pytest
```

## Author

**Ammar Yasser Abdalazim**

- GitHub: [@AmmarYasser455](https://github.com/AmmarYasser455)

## License

[MIT License](LICENSE)

## Acknowledgments

OVC is part of a geospatial quality control ecosystem alongside [GeoQA](https://github.com/AmmarYasser455/geoqa). The project uses vectorized spatial operations powered by [GeoPandas](https://geopandas.org/), [Shapely](https://shapely.readthedocs.io/), and [Folium](https://python-visualization.github.io/folium/) for interactive visualization.

## Citation

```bibtex
@software{ovc2026,
  title   = {OVC: Overlap Violation Checker for Geospatial Data},
  author  = {Ammar Yasser Abdalazim},
  year    = {2026},
  url     = {https://github.com/AmmarYasser455/ovc},
  license = {MIT}
}
```

---

<div align="center">

**⭐ If you find this project useful, please consider giving it a star!**

</div>
