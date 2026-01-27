<div align="center">

<img src="assets/logo.png" alt="OVC Logo" width="400"/>

# Overlap Violation Checker (OVC)

**A Python-based spatial quality control tool for detecting geometric and topological issues in OpenStreetMap-like datasets**

<p align="center">
  <img src="https://img.shields.io/badge/version-v1.0.0-blue.svg" />
  <img src="https://img.shields.io/badge/license-MIT-green.svg" />
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" />
</p>

</div>

---

## Overview

OVC is designed to identify overlapping buildings, boundary violations, and road-related conflicts in geospatial datasets. It produces analysis-ready outputs and interactive web maps, making it ideal for real-world GIS quality assurance and data validation workflows.

The tool is built with modularity and extensibility in mind, allowing seamless integration into automated spatial data pipelines.

## Key Features

- **Building Overlap Detection** — Identify duplicate and partial overlaps in building geometries
- **Boundary Compliance** — Validate building footprints against administrative boundaries
- **Road Conflict Analysis** — Detect road–building and road–road intersections
- **Multi-Format Export** — Generate GeoJSON and CSV outputs for further analysis
- **Interactive Visualization** — Produce web-based maps for visual inspection
- **Modular Architecture** — Easily extend and customize validation workflows

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
pip install -r requirements.txt
```

---

## Quick Start

OVC can be used in two simple ways depending on the data you have. You do not need to write Python code — just run a single command.

### ✅ Option 1: You already have your own GeoJSON buildings (and optionally roads)

If you have your own datasets (e.g., buildings you digitized manually), you can run OVC by providing both the boundary and buildings files:

```bash
python scripts/run_qc.py \
  --boundary path/to/boundary.geojson \
  --buildings path/to/buildings.geojson \
  --out outputs
```

- If you also have your own roads file, you can pass it the same way
- If you don't provide roads, OVC will download roads from OSM automatically

This mode skips OSM buildings and uses your own data.

### ✅ Option 2: You only have a boundary (Shapefile or GeoJSON)

If you only have a boundary file (e.g., a governorate, district, or AOI), OVC will automatically download buildings and roads from OpenStreetMap:

```bash
python scripts/run_qc.py \
  --boundary path/to/boundary.shp \
  --out outputs
```

This is the simplest mode. Just give OVC your boundary, and it handles everything else.

### ℹ️ Notes

- The boundary file must be a Polygon (WGS84 recommended)
- If you pass `--buildings`, OVC will use your buildings and skip OSM buildings
- If you pass `--roads`, OVC will use your roads and skip OSM roads
- If you don't pass them, OVC downloads everything automatically

---

## Outputs

The pipeline generates the following:

| Output Type | Description |
|------------|-------------|
| **GeoJSON files** | Spatial layers containing detected issues |
| **CSV reports** | Summary statistics and metrics |
| **HTML web map** | Interactive map for visual inspection |

All outputs are saved to the specified `output_dir`.

---

## Configuration

Runtime thresholds and validation settings can be customized in:

```
ovc/core/config.py
```

---

## Testing

Run the full test suite:

```bash
pytest
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

For the complete dependency list, refer to `requirements.txt`.

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
