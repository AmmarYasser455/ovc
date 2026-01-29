---
layout: default
title: OVC – Overlap Violation Checker
---

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

<div align="center">
<img src="assets/ov.png" alt="OVC Workflow" width="800"/>
</div>

OVC is designed to identify overlapping buildings, boundary violations, and road-related conflicts in geospatial datasets. It produces analysis-ready outputs and interactive web maps, making it ideal for real-world GIS quality assurance and data validation workflows.

The tool is built with modularity and extensibility in mind, allowing seamless integration into automated spatial data pipelines.

---

## Key Features

**Geometry Validation**
- **Building Overlap Detection** — Identify duplicate and partial overlaps in building geometries
- **Boundary Compliance** — Validate building footprints against administrative boundaries
- **Road Conflict Analysis** — Detect road–building and road–road intersections
- Flag self-intersections and topology violations

**Data Processing**
- Process large-scale OSM datasets efficiently with spatial indexing
- Automatic data download from OpenStreetMap when needed
- Flexible input options: use your own data or fetch from OSM
- Memory-optimized for complex spatial operations

**Output & Reporting**
- **Multi-Format Export** — Generate GeoJSON and CSV outputs for further analysis
- **Interactive Visualization** — Produce web-based HTML maps for visual inspection
- Severity classification and detailed violation reports
- Analysis-ready datasets for GIS workflows

**Automation & Extensibility**
- **Modular Architecture** — Easily extend and customize validation workflows
- Command-line interface for automation and CI/CD integration
- Configurable thresholds and validation parameters
- Seamless pipeline integration

---

## Use Cases

**Data Quality Assurance**
- Pre-publication validation for OSM contributors and organizations
- Continuous quality monitoring for corporate OSM deployments
- Compliance checking against administrative boundaries and data specifications

**GIS Workflows**
- Building inventory verification and conflict detection
- Road network topology validation
- Data cleaning prior to spatial analysis or urban modeling
- Automated QC steps in ETL pipelines

**Urban Planning & Infrastructure**
- Validation of digitized building footprints
- Detection of geometric conflicts in urban datasets
- Quality control for crowd-sourced mapping projects
- Pre-processing for urban analytics and planning tools

---

## Quick Start

### Installation

**Option 1: Clone the repository**
```bash
git clone https://github.com/AmmarYasser455/ovc.git
cd ovc
```

**Option 2: Create a virtual environment (recommended)**
```bash
python -m venv venv
source venv/bin/activate    # Linux / macOS
venv\Scripts\activate       # Windows
```

**Option 3: Install dependencies**
```bash
pip install -r requirements.txt
```

### Basic Usage

OVC can be run in multiple flexible modes depending on the data you have. You do not need to write any Python code — just run a single command.

**✅ Option 1: You have your own buildings only**

If you already have a buildings dataset, run OVC directly on it:
```bash
python scripts/run_qc.py \
  --buildings path/to/buildings.shp \
  --out outputs
```

**In this mode:**
- OVC uses your buildings as the analysis area
- Roads are automatically downloaded from OpenStreetMap
- Building overlaps and building–road conflicts are detected
- No boundary checks are performed

---

**✅ Option 2: You have your own buildings and roads**

If you have both datasets:
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

---

**✅ Option 3: You have a boundary and want OSM data**

If you provide a boundary file, OVC automatically downloads from OpenStreetMap:
```bash
python scripts/run_qc.py \
  --boundary path/to/boundary.geojson \
  --out outputs
```

**This mode:**
- Downloads buildings and roads from OSM within the boundary
- Runs all QC checks, including boundary-related validation
- Boundary must be a polygon (WGS84 recommended)

---

**ℹ️ Usage Notes**

- The boundary file must be a polygon geometry
- If `--buildings` is provided, OVC skips downloading OSM buildings
- If `--roads` is provided, OVC skips downloading OSM roads
- If no boundary is provided, OVC derives the analysis area from buildings extent
- Road conflict checks are always enabled when roads are available

---

## Outputs

The pipeline generates the following analysis-ready outputs:

| Output Type | Description |
|------------|-------------|
| **GeoJSON files** | Spatial layers containing detected violations |
| **CSV reports** | Summary statistics and detailed metrics |
| **HTML web map** | Interactive Folium map for visual inspection |

All outputs are saved to the specified output directory and ready for integration into GIS software.

---

## Configuration

Runtime thresholds and validation settings can be customized in:
```
ovc/core/config.py
```

Available configuration options include:
- Overlap tolerance thresholds
- Buffer distances for road conflicts
- Validation rule parameters
- Output format preferences

---

## Documentation

- **[User Guide](user-guide.md)** – Detailed installation and usage instructions
- **[Architecture](https://github.com/AmmarYasser455/ovc/blob/main/ARCHITECTURE.md)** – Design decisions and module responsibilities  
- **[Contributing](https://github.com/AmmarYasser455/ovc/blob/main/CONTRIBUTING.md)** – Development workflow and guidelines
- **[API Reference](api-reference.md)** – Python module documentation

---

## Requirements

**Python Version**
- Python 3.10 or newer
- Recommended: Python 3.11

**Core Dependencies**
- GeoPandas
- Shapely
- PyProj
- Pandas
- Folium

**Additional Tools**
- Git 2.30+ (recommended: Git 2.40+)

For the complete dependency list, refer to `requirements.txt`.

---

## Testing

Run the full test suite:
```bash
pytest
```

Ensure all tests pass before contributing changes.

---

## Project Links

- **GitHub Repository:** [github.com/AmmarYasser455/ovc](https://github.com/AmmarYasser455/ovc)
- **Documentation:** [ammaryasser455.github.io/ovc](https://ammaryasser455.github.io/ovc)
- **Issue Tracker:** [github.com/AmmarYasser455/ovc/issues](https://github.com/AmmarYasser455/ovc/issues)

---

## Roadmap

- [ ] Support for additional feature types (landuse, water bodies, parcels)
- [ ] Real-time validation API service
- [ ] QGIS plugin integration
- [ ] Performance benchmarks and parallel processing optimization
- [ ] Machine learning-based anomaly detection
- [ ] Support for PostgreSQL/PostGIS backends
- [ ] Multi-language documentation

---

## Contributing

Contributions, issues, and feature requests are welcome! 

Please read our **[CONTRIBUTING.md](https://github.com/AmmarYasser455/ovc/blob/main/CONTRIBUTING.md)** guide for:
- How to report bugs and request features
- Development workflow and coding guidelines
- Testing requirements and documentation standards

Feel free to check the [issues page](https://github.com/AmmarYasser455/ovc/issues) to get started.

**How to Contribute:**
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

This project is licensed under the **MIT License**. See [LICENSE](https://github.com/AmmarYasser455/ovc/blob/main/LICENSE) for details.

---

## Citation

If you use OVC in research or publications, please cite:
```
Yasser, A. (2025). OVC: Overlap Violation Checker for OpenStreetMap Data.
https://github.com/AmmarYasser455/ovc
```

---

## Author

**Ammar Yasser**

- GitHub: [@AmmarYasser455](https://github.com/AmmarYasser455)
- Project: [OVC - Overlap Violation Checker](https://github.com/AmmarYasser455/ovc)

---

## Acknowledgments

Built with support from the OpenStreetMap community and the open-source GIS ecosystem.

Special thanks to the developers of GeoPandas, Shapely, and Folium for their excellent spatial analysis libraries.

---

## Get Started

Ready to improve your spatial data quality? 

- [Install OVC](#installation) and run your first validation
- Explore the [documentation](user-guide.md) for detailed guides
- Check out [example workflows](examples.md) and tutorials

For questions or support, visit our [GitHub repository](https://github.com/AmmarYasser455/ovc) or open an [issue](https://github.com/AmmarYasser455/ovc/issues).

---

<div align="center">

**⭐ If you find this project useful, please consider giving it a star!**

[⬆ Back to top](#overlap-violation-checker-ovc)

</div>
