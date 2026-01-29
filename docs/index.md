---
layout: default
title: OVC – Overlap Violation Checker
---

# OVC – Overlap Violation Checker

**An open-source spatial quality control toolkit for OpenStreetMap data validation**

OVC automates the detection of geometric and topological errors in OSM datasets, focusing on overlaps, containment violations, and geometry conflicts in building footprints and road networks. Built for scalability, it delivers clean, actionable outputs that integrate seamlessly into GIS workflows.

---

## Features

**Geometry Validation**
- Detect overlapping building polygons with configurable tolerance thresholds
- Identify invalid containment relationships (buildings within buildings, roads through structures)
- Flag self-intersections and topology violations

**Data Processing**
- Process large-scale OSM datasets efficiently with spatial indexing
- Batch validation with multi-threaded processing support
- Memory-optimized for datasets exceeding millions of features

**Output & Reporting**
- Export violation reports to GeoPackage (GPKG) for GIS analysis
- Generate interactive HTML reports with spatial previews
- JSON/CSV output options for pipeline integration
- Severity classification (critical, warning, info)

**Automation & Extensibility**
- Command-line interface for CI/CD integration
- Configurable rulesets and validation parameters
- Plugin architecture for custom checks

---

## Use Cases

**Data Quality Assurance**
- Pre-publication validation for OSM contributors and organizations
- Continuous quality monitoring for corporate OSM deployments
- Compliance checking against data specifications

**GIS Workflows**
- Data cleaning prior to spatial analysis or modeling
- Automated QC steps in ETL pipelines
- Validation layer for crowd-sourced mapping projects

**Urban Planning & Infrastructure**
- Building inventory verification
- Road network topology validation
- Conflict detection in urban development datasets

---

## Quick Start

### Installation

Install via pip:
```bash
pip install ovc
```

Or install from source:
```bash
git clone https://github.com/AmmarYasser455/ovc.git
cd ovc
pip install -e .
```

### Basic Usage
```bash
# Validate multiple layers in a GeoPackage
ovc check \
  --input data.gpkg \
  --layers buildings roads \
  --output results.gpkg

# Check buildings in an OSM file
ovc check buildings input.osm.pbf --output violations.gpkg

# Validate road network topology with HTML report
ovc check roads city.osm.pbf --report report.html

# Run all checks with custom tolerance
ovc check all region.osm.pbf --tolerance 0.5 --output results/
```

---

## Documentation

- **[User Guide](user-guide.md)** – Installation, configuration, and usage
- **[API Reference](api-reference.md)** – Python API documentation  
- **[Examples](examples.md)** – Sample workflows and use cases
- **[Tutorials](tutorials.md)** – Step-by-step guides for common tasks

---

## Requirements

- Python 3.8+
- GDAL/OGR 3.0+
- Optional: PostgreSQL/PostGIS for advanced processing

---

## Project Links

- **GitHub Repository:** [github.com/AmmarYasser455/ovc](https://github.com/AmmarYasser455/ovc)
- **Documentation:** [ammaryasser455.github.io/ovc](https://ammaryasser455.github.io/ovc)
- **Issue Tracker:** [github.com/AmmarYasser455/ovc/issues](https://github.com/AmmarYasser455/ovc/issues)

---

## Roadmap

- [ ] Support for additional OSM feature types (landuse, water bodies)
- [ ] Real-time validation API service
- [ ] QGIS plugin integration
- [ ] Performance benchmarks and optimization
- [ ] Machine learning-based anomaly detection

---

## Contributing

Contributions, issues, and feature requests are welcome! Please check the [repository](https://github.com/AmmarYasser455/ovc) for contribution guidelines.

**How to Contribute:**
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

This project is released under the **MIT License**. See [LICENSE](https://github.com/AmmarYasser455/ovc/blob/main/LICENSE) for details.

---

## Citation

If you use OVC in research or publications, please cite:
```
Yasser, A. (2025). OVC: Overlap Violation Checker for OpenStreetMap Data.
https://github.com/AmmarYasser455/ovc
```

---

## Acknowledgments

Built with support from the OpenStreetMap community and the open-source GIS ecosystem.

---

## Get Started

Ready to improve your OSM data quality? [Install OVC](#installation) or explore the [documentation](user-guide.md) to get started.

For questions or support, visit our [GitHub repository](https://github.com/AmmarYasser455/ovc) or open an [issue](https://github.com/AmmarYasser455/ovc/issues).
