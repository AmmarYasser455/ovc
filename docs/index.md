---
layout: default
title: OVC – Overlap Violation Checker
---

<div align="center">

<img src="assets/logo.png" alt="OVC Logo" width="360"/>

# Overlap Violation Checker (OVC)

**A modular spatial quality control framework for detecting geometric and topological issues in OpenStreetMap‑like datasets**

<p align="center">
  <img src="https://img.shields.io/badge/version-v1.0.0-blue.svg" />
  <img src="https://img.shields.io/badge/license-MIT-green.svg" />
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" />
</p>

</div>

---

## Overview

<div align="center">
<img src="assets/ov.png" alt="OVC Workflow" width="820"/>
</div>

OVC is a **Python‑based spatial quality control framework** designed to identify geometric and topological issues in geospatial datasets, with a strong focus on OpenStreetMap‑derived data.

It detects:
- overlapping and duplicate building geometries
- boundary containment violations
- road–building and road–road conflicts
- common topology errors affecting spatial integrity

OVC is built around **clear architectural boundaries**, making it suitable for:
- command‑line usage
- automated QC pipelines
- integration into GIS and ETL workflows
- extension by contributors and advanced users

---

## Documentation

| Document | Description |
|----------|-------------|
| **[User Guide](user-guide.md)** | Installation, configuration, CLI usage, troubleshooting |
| **[Tutorials](tutorials.md)** | Step-by-step learning paths from beginner to advanced |
| **[Examples](examples.md)** | Practical code snippets and real-world use cases |
| **[API Reference](api-reference.md)** | Python API documentation for programmatic usage |
| **[Architecture](../ARCHITECTURE.md)** | Design decisions and system structure for contributors |

---

## Design Philosophy

OVC is intentionally designed as a **framework**, not a monolithic script.

Key principles:
- **Separation of concerns** between data loading, validation logic, and output generation
- **Configuration‑driven behavior** without hard‑coded thresholds
- **Deterministic, testable QC checks**
- **No hidden side effects or implicit state**

For architectural details, see:
👉 **[Architecture Overview](../ARCHITECTURE.md)**

---

## Core Capabilities

### Geometry Validation
- Detect overlapping and duplicate building footprints
- Identify partial and full containment violations
- Flag self‑intersections and invalid geometries
- Classify issues by severity and impact

### Data Handling
- Accept user‑provided datasets or fetch data from OpenStreetMap
- Normalize schemas across heterogeneous sources
- Reproject data to metric CRS for accurate spatial analysis
- Scale to large datasets through spatial indexing

### Output & Reporting
- Export violations as **GeoJSON** and **CSV**
- Generate interactive **HTML web maps** for visual inspection
- Produce analysis‑ready outputs for GIS software
- Maintain consistent, structured result schemas

### Automation & Extensibility
- Command‑line interface for batch processing
- Modular QC checks that can be extended independently
- Clean Python API for advanced workflows
- Designed for CI/CD and scheduled validation runs

---

## Typical Use Cases

### Data Quality Assurance
- Pre‑publication validation of OSM contributions
- Continuous QC for institutional OSM deployments
- Compliance checks against administrative boundaries

### GIS & ETL Workflows
- Cleaning building inventories before analysis
- Detecting conflicts in road networks
- Automated QC steps in spatial pipelines

### Urban & Infrastructure Analysis
- Validation of digitized building footprints
- Conflict detection in dense urban environments
- Pre‑processing for planning and analytics tools

---

## Getting Started

### Installation

Clone the repository:
```bash
git clone https://github.com/AmmarYasser455/ovc.git
cd ovc
```

Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate    # Linux / macOS
venv\Scripts\activate       # Windows
```

Install dependencies:
```bash
pip install -r requirements.txt
```

### Quick Start

Run a basic overlap check on your building data:

```bash
python scripts/run_qc.py \
  --buildings path/to/buildings.shp \
  --out outputs
```

For more usage options, see the **[User Guide](user-guide.md)**.

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

## Requirements

- Python 3.10+
- GeoPandas
- Shapely
- PyProj
- Pandas
- Folium

For the complete dependency list, refer to `requirements.txt`.

---

## Next Steps

- **New users:** Start with the [User Guide](user-guide.md) for installation and CLI usage
- **Learn by doing:** Follow the [Tutorials](tutorials.md) for hands-on learning
- **Quick reference:** Browse [Examples](examples.md) for copy-paste solutions
- **Developers:** Explore the [API Reference](api-reference.md) for Python integration
- **Contributors:** Read the [Architecture](../ARCHITECTURE.md) documentation

---

<div align="center">

**Questions or issues?**

[Open an issue](https://github.com/AmmarYasser455/ovc/issues) or check the [User Guide](user-guide.md) for troubleshooting.

</div>
