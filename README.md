<div align="center">

<img src="assets/logo.png" alt="OVC Logo" width="400"/>

# Overlap Violation Checker (OVC)

**A Python-based spatial quality control tool for detecting geometric and topological issues in OpenStreetMap-like datasets**

<p align="center">
  <img src="https://img.shields.io/badge/version-v1.0.2-blue.svg" />
  <img src="https://img.shields.io/badge/license-MIT-green.svg" />
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" />
</p>

</div>

---

## Overview

OVC is designed to identify overlapping buildings, boundary violations, and road-related conflicts in geospatial datasets. It produces analysis-ready outputs and interactive web maps, making it ideal for real-world GIS quality assurance and data validation workflows.

The tool is built with modularity and extensibility in mind, allowing seamless integration into automated spatial data pipelines.

## Key Features

### Building QC
- **Overlap Detection** — Identify duplicate and partial overlaps in building geometries
- **Boundary Compliance** — Validate building footprints against administrative boundaries
- **Road Conflict Analysis** — Detect buildings conflicting with roads

### Road QC
- **Disconnected Segments** — Detect roads not connected to the network
- **Self-Intersections** — Find roads that cross themselves
- **Dangles** — Identify dead-end endpoints (incomplete digitization)

### Shared
- **Multi-Format Export** — GeoPackage, CSV, and HTML outputs
- **Interactive Visualization** — Web-based maps with legends
- **Modular Architecture** — Easily extend and customize workflows

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/AmmarYasser455/ovc.git
cd ovc
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate    # Linux / macOS
venv\Scripts\activate       # Windows
```

### 3. Install dependencies

```bash
pip install -e .
```

---

## Quick Start

### Building QC Only

```bash
python scripts/run_qc.py \
  --boundary path/to/boundary.shp \
  --out outputs
```

### Building + Road QC

```bash
python scripts/run_qc.py \
  --boundary path/to/boundary.shp \
  --road-qc \
  --out outputs
```

### With Custom Data

```bash
python scripts/run_qc.py \
  --boundary path/to/boundary.shp \
  --buildings path/to/buildings.geojson \
  --roads path/to/roads.geojson \
  --road-qc \
  --out outputs
```

---

## Outputs

Both modules produce outputs in a unified folder structure:

```
outputs/
├── building_qc/
│   ├── building_qc.gpkg          # GeoPackage with layers
│   ├── building_qc_map.html      # Interactive web map
│   └── building_qc_metrics.csv   # Summary metrics
└── road_qc/
    ├── road_qc.gpkg
    ├── road_qc_map.html
    └── road_qc_metrics.csv
```

| Output Type | Description |
|------------|-------------|
| **GeoPackage** | Spatial layers with detected issues |
| **CSV metrics** | Summary statistics and top errors |
| **HTML web map** | Interactive map with legend and layer control |

---

## Configuration

Configuration is managed through dataclasses:

```python
# Building QC
from ovc.core.config import OverlapConfig

# Road QC
from ovc.road_qc.config import RoadQCConfig
```

See [ovc/core/config.py](ovc/core/config.py) and [ovc/road_qc/config.py](ovc/road_qc/config.py).

---

## Testing

```bash
source venv/bin/activate
pytest tests/ -v
```

---

## Architecture

For detailed design decisions and module responsibilities, see:

**[ARCHITECTURE.md](ARCHITECTURE.md)**

---

## Requirements

- Python 3.10+
- GeoPandas
- Shapely
- PyProj
- Pandas
- Folium
- OSMnx

For the complete dependency list, refer to `pyproject.toml`.

---

## License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.

---

## Author

**Ammar Yasser**

- GitHub: [@AmmarYasser455](https://github.com/AmmarYasser455)

---

## Contributing

Contributions, issues, and feature requests are welcome!

Please read our **[CONTRIBUTING.md](CONTRIBUTING.md)** guide for:
- How to report bugs and request features
- Development workflow and coding guidelines
- Testing requirements and documentation standards

Feel free to check the [issues page](https://github.com/AmmarYasser455/ovc/issues) to get started.

---

<div align="center">

**⭐ If you find this project useful, please consider giving it a star!**

</div>
