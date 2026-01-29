<div align="center">

<img src="docs/assets/logo.png" alt="OVC Logo" width="400"/>

# Overlap Violation Checker (OVC)

**A Python-based spatial quality control tool for detecting geometric and topological issues in OpenStreetMap-like datasets**

<p align="center">
  <img src="https://img.shields.io/badge/version-v1.0.1-blue.svg" />
  <img src="https://img.shields.io/badge/license-MIT-green.svg" />
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" />
</p>

</div>

---

## Overview

<div align="center">
<img src="docs/assets/ov.png" alt="OVC Workflow" width="800"/>
</div>

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

## Documentation

📚 **[Full Documentation](docs/index.md)** — User Guide, Tutorials, Examples, and API Reference

---

## Requirements

### Python

OVC requires Python 3.10 or newer.

**Recommended version:**
```
Python 3.11
```

**Minimum supported version:**
```
Python 3.10
```

### Git

OVC requires Git 2.30 or newer.

**Recommended version:**
```
Git 2.40+
```

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

OVC can be run in multiple flexible modes depending on the data you already have. You do not need to write any Python code — just run a single command.

### ✅ Option 1: You have your own buildings only (no boundary required)

If you already have a buildings dataset (e.g., digitized manually or from another source), you can run OVC directly on it:

```bash
python scripts/run_qc.py \
  --buildings path/to/buildings.shp \
  --out outputs
```

**In this mode:**
- OVC uses your buildings as the analysis area
- Roads are automatically downloaded from OpenStreetMap using the buildings extent
- Building overlaps and building–road conflicts are detected
- No boundary checks are performed

This is the simplest way to run QC on local datasets.

### ✅ Option 2: You have your own buildings and roads

If you already have both buildings and roads datasets:

```bash
python scripts/run_qc.py \
  --buildings path/to/buildings.shp \
  --roads path/to/roads.shp \
  --out outputs
```

**In this mode:**
- OVC uses only your provided data
- No OpenStreetMap downloads are performed
- All overlap and road conflict checks are enabled

### ✅ Option 3: You have a boundary and want OSM data

If you provide a boundary file (e.g., governorate, district, or AOI), OVC will automatically download buildings and roads from OpenStreetMap:

```bash
python scripts/run_qc.py \
  --boundary path/to/boundary.geojson \
  --out outputs
```

**This mode:**
- Downloads buildings and roads from OSM
- Runs all QC checks, including boundary-related checks
- Requires the boundary to be a polygon (WGS84 recommended)

### ℹ️ Notes

- The boundary file must be a polygon geometry
- If `--buildings` is provided, OVC skips downloading OSM buildings
- If `--roads` is provided, OVC skips downloading OSM roads
- If no boundary is provided, OVC automatically derives the analysis area from the buildings extent
- Road conflict checks are always enabled when roads are available

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
