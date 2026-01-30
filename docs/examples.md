---
layout: default
title: Examples - OVC
---

# OVC Examples

Practical examples demonstrating common OVC workflows and use cases.

> [!TIP]
> **Examples vs Tutorials:** Examples provide **quick, copy-paste code snippets** for common tasks. For **guided, step-by-step learning** that builds understanding progressively, see [Tutorials](tutorials.md).

---

## Table of Contents

1. [Quick Start Examples](#quick-start-examples)
2. [Road QC Examples](#road-qc-examples)
3. [Data Preparation Examples](#data-preparation-examples)
4. [Quality Control Workflows](#quality-control-workflows)
5. [Integration Examples](#integration-examples)
6. [Advanced Use Cases](#advanced-use-cases)

---

## Quick Start Examples

### Example 1: Basic Building Overlap Check

**Scenario:** You have digitized buildings and want to check for overlaps.

```bash
python scripts/run_qc.py \
  --buildings data/my_buildings.shp \
  --out results/overlap_check
```

**Output:**
```
results/overlap_check/
└── building_qc/
    ├── building_qc.gpkg
    ├── building_qc_map.html
    └── building_qc_metrics.csv
```

**What you get:**
- GeoPackage with all layers (buildings, errors, roads)
- Interactive web map with legend
- Summary metrics CSV

---

### Example 2: Complete QC with OSM Data

**Scenario:** Download OSM data for a city and run complete QC.

```bash
python scripts/run_qc.py \
  --boundary data/city_boundary.geojson \
  --out results/city_qc
```

**Output:**
```
results/city_qc/
├── building_overlaps.geojson
├── building_overlaps.csv
├── boundary_violations.geojson
├── boundary_violations.csv
├── road_conflicts.geojson
├── road_conflicts.csv
├── validation_report.html
└── summary_statistics.csv
```

**What you get:**
- Building overlap detection
- Boundary violation checks
- Road-building conflict analysis
- Comprehensive HTML report

---

### Example 3: Custom Buildings with OSM Roads

**Scenario:** You have your own buildings but need road data from OSM.

```bash
python scripts/run_qc.py \
  --buildings data/field_survey_buildings.gpkg \
  --out results/survey_qc
```

**What happens:**
- Your buildings are analyzed
- Roads are automatically downloaded from OSM
- Overlap and road conflict checks are performed
- No boundary validation (since no boundary provided)

---

## Road QC Examples

### Example 4: Basic Road Network Check (New in v1.0.2)

**Scenario:** Check road network for connectivity issues.

```bash
python scripts/run_qc.py \
  --boundary data/city.geojson \
  --road-qc \
  --out results/road_check
```

**Output:**
```
results/road_check/
├── building_qc/
│   └── ...
└── road_qc/
    ├── road_qc.gpkg
    ├── road_qc_map.html
    └── road_qc_metrics.csv
```

**What you get:**
- Disconnected road segments
- Self-intersecting roads
- Dangle endpoints (dead ends)

---

### Example 5: Road QC Only (Python)

**Scenario:** Run only Road QC programmatically.

```python
from pathlib import Path
from ovc.road_qc import run_road_qc

outputs = run_road_qc(
    boundary_path=Path("data/boundary.geojson"),
    out_dir=Path("results/road_qc")
)

print(f"Total errors: {outputs.total_errors}")

# Print error breakdown
for error_type, count in outputs.top_3_errors:
    print(f"  {error_type}: {count}")
```

---

### Example 6: Road QC with Custom Roads

**Scenario:** Use your own road dataset instead of OSM.

```python
from pathlib import Path
from ovc.road_qc import run_road_qc

outputs = run_road_qc(
    roads_path=Path("data/my_roads.shp"),
    boundary_path=Path("data/boundary.geojson"),  # For dangle filtering
    out_dir=Path("results/road_qc")
)

print(f"GeoPackage: {outputs.gpkg_path}")
print(f"Web map: {outputs.webmap_html}")
```

---

## Data Preparation Examples

### Example 7: Prepare Shapefile Data

**Converting and cleaning data before QC:**

```bash
# 1. Convert to WGS84
ogr2ogr -t_srs EPSG:4326 \
  buildings_wgs84.shp \
  buildings_utm.shp

# 2. Fix invalid geometries
ogr2ogr -makevalid \
  buildings_clean.shp \
  buildings_wgs84.shp

# 3. Simplify complex geometries
ogr2ogr -simplify 0.5 \
  buildings_simplified.shp \
  buildings_clean.shp

# 4. Run OVC
python scripts/run_qc.py \
  --buildings buildings_simplified.shp \
  --out results/prepared_data
```

---

### Example 8: Merge Multiple Building Datasets

**Combining buildings from different sources:**

```bash
# Merge shapefiles into GeoPackage
ogr2ogr merged_buildings.gpkg source1.shp

ogr2ogr -update -append \
  merged_buildings.gpkg source2.shp

ogr2ogr -update -append \
  merged_buildings.gpkg source3.shp

# Run QC on merged data
python scripts/run_qc.py \
  --buildings merged_buildings.gpkg \
  --out results/merged_qc
```

---

### Example 9: Extract Buildings from OSM Extract

**Using a local OSM extract instead of API:**

```bash
# Extract buildings using osmium
osmium tags-filter egypt-latest.osm.pbf \
  building \
  -o buildings.osm.pbf

# Convert to GeoPackage
ogr2ogr -f GPKG buildings.gpkg buildings.osm.pbf

# Run QC
python scripts/run_qc.py \
  --buildings buildings.gpkg \
  --out results/osm_extract_qc
```

---

## Quality Control Workflows

### Example 10: District-Level QC Campaign

**Quality control for multiple districts:**

```bash
#!/bin/bash
# qc_campaign.sh

DISTRICTS=(
  "district1.geojson"
  "district2.geojson"
  "district3.geojson"
)

for district in "${DISTRICTS[@]}"; do
  name=$(basename "$district" .geojson)
  
  echo "Processing $name..."
  
  python scripts/run_qc.py \
    --boundary "boundaries/$district" \
    --out "results/$name" \
    --verbose
    
  echo "Completed $name"
done

echo "All districts processed!"
```

**Run the script:**
```bash
chmod +x qc_campaign.sh
./qc_campaign.sh
```

---

### Example 11: Incremental QC for Updates

**Check only new/updated buildings:**

```bash
# Get buildings modified in last 30 days
ogr2ogr -where "date_modified > '2024-12-01'" \
  new_buildings.shp \
  all_buildings.shp

# Run QC on new buildings only
python scripts/run_qc.py \
  --buildings new_buildings.shp \
  --boundary study_area.geojson \
  --out results/incremental_qc
```

---

### Example 12: Pre-Publication Validation

**Complete validation before publishing data:**

```bash
# Step 1: Run OVC
python scripts/run_qc.py \
  --buildings final_buildings.gpkg \
  --roads final_roads.gpkg \
  --boundary aoi_boundary.geojson \
  --out results/pre_publication

# Step 2: Check results
OVERLAPS=$(wc -l < results/pre_publication/building_overlaps.csv)
BOUNDARY=$(wc -l < results/pre_publication/boundary_violations.csv)

if [ "$OVERLAPS" -gt 1 ] || [ "$BOUNDARY" -gt 1 ]; then
  echo "❌ Validation failed! Issues found."
  echo "Overlaps: $OVERLAPS, Boundary violations: $BOUNDARY"
  exit 1
else
  echo "✅ Validation passed! Data is clean."
fi
```

---

## Integration Examples

### Example 13: Python Script Integration

**# Using OVC in a custom Python workflow:

```python
#!/usr/bin/env python3
"""
Custom QC workflow with notifications
"""
import sys
from pathlib import Path
from ovc.export.pipeline import run_pipeline

def send_notification(message):
    """Send email/Slack notification (implement as needed)"""
    print(f"📧 Notification: {message}")

def main():
    # Run QC
    try:
        outputs = run_pipeline(
            boundary_path=None,
            buildings_path=Path("data/buildings.gpkg"),
            roads_path=Path("data/roads.gpkg"),
            out_dir=Path("results/automated_qc")
        )
        
        # Note: Analysis would normally read the generated GPKG/CSV here
        # For simplicity we just report success
        
        message = f"""
        QC Complete!
        ============
        Results saved to: {outputs.gpkg_path}
        Report: {outputs.webmap_html}
        """
        
        send_notification(f"✅ Workflow finished!\n{message}")
            
    except Exception as e:
        send_notification(f"❌ QC Failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

**Run the script:**
```bash
python custom_qc.py
```

---

### Example 14: QGIS Integration

**Load OVC results into QGIS:**

```python
# QGIS Python Console
from qgis.core import QgsVectorLayer, QgsProject

# Add overlaps layer
overlaps = QgsVectorLayer(
    'results/building_overlaps.geojson',
    'Building Overlaps',
    'ogr'
)

# Style by severity
from qgis.core import QgsGraduatedSymbolRenderer, QgsStyle

# Get severity field
severity_field = 'severity'

# Apply graduated renderer
renderer = QgsGraduatedSymbolRenderer(severity_field)

# Add to project
QgsProject.instance().addMapLayer(overlaps)
```

**Or use QGIS GUI:**
1. Layer → Add Layer → Add Vector Layer
2. Navigate to `results/building_overlaps.geojson`
3. Right-click layer → Properties → Symbology
4. Choose "Categorized" and select "severity" field
5. Click "Classify"

---

### Example 15: PostGIS Integration

**Load OVC results into PostgreSQL/PostGIS:**

```bash
# Create database
createdb qc_results

# Enable PostGIS
psql -d qc_results -c "CREATE EXTENSION postgis;"

# Import results
ogr2ogr -f PostgreSQL \
  PG:"dbname=qc_results user=postgres" \
  results/building_overlaps.geojson \
  -nln building_overlaps

ogr2ogr -f PostgreSQL \
  PG:"dbname=qc_results user=postgres" \
  results/road_conflicts.geojson \
  -nln road_conflicts
```

**Query in PostgreSQL:**
```sql
-- Count overlaps by severity
SELECT severity, COUNT(*) as count
FROM building_overlaps
GROUP BY severity
ORDER BY count DESC;

-- Find critical overlaps
SELECT building_a, building_b, overlap_area
FROM building_overlaps
WHERE severity = 'critical'
ORDER BY overlap_area DESC;

-- Buildings with multiple conflicts
SELECT building_a, COUNT(*) as conflict_count
FROM building_overlaps
GROUP BY building_a
HAVING COUNT(*) > 1
ORDER BY conflict_count DESC;
```

---

## Advanced Use Cases

### Example 16: Automated CI/CD Pipeline

**GitHub Actions workflow for automated QC:**

```yaml
# .github/workflows/qc.yml
name: Building QC

on:
  push:
    paths:
      - 'data/buildings/**'
  pull_request:
    paths:
      - 'data/buildings/**'

jobs:
  quality-control:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v3
      
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: Install GDAL
      run: |
        sudo apt-get update
        sudo apt-get install -y gdal-bin libgdal-dev
        
    - name: Install OVC
      run: |
        git clone https://github.com/AmmarYasser455/ovc.git
        cd ovc
        pip install -r requirements.txt
        
    - name: Run QC
      run: |
        python ovc/scripts/run_qc.py \
          --buildings data/buildings/latest.gpkg \
          --boundary data/boundaries/aoi.geojson \
          --out results/qc
          
    - name: Check for issues
      run: |
        OVERLAPS=$(wc -l < results/qc/building_overlaps.csv)
        if [ "$OVERLAPS" -gt 1 ]; then
          echo "::error::Found $OVERLAPS overlapping buildings"
          exit 1
        fi
        
    - name: Upload results
      uses: actions/upload-artifact@v3
      with:
        name: qc-results
        path: results/qc/
```

---

### Example 17: Batch Processing with Parallel Execution

**Process multiple areas in parallel:**

```bash
#!/bin/bash
# parallel_qc.sh

# List of boundaries
BOUNDARIES=(
  "area1.geojson"
  "area2.geojson"
  "area3.geojson"
  "area4.geojson"
)

# Function to run QC
run_qc() {
  boundary=$1
  name=$(basename "$boundary" .geojson)
  
  python scripts/run_qc.py \
    --boundary "boundaries/$boundary" \
    --out "results/$name"
  
  echo "✅ Completed $name"
}

export -f run_qc

# Run in parallel (4 jobs at a time)
parallel -j 4 run_qc ::: "${BOUNDARIES[@]}"

echo "All areas processed!"
```

**Install GNU Parallel first:**
```bash
# Ubuntu/Debian
sudo apt-get install parallel

# macOS
brew install parallel
```

**Run the script:**
```bash
chmod +x parallel_qc.sh
./parallel_qc.sh
```

---

### Example 18: Custom Threshold Configuration

**# Creating a custom configuration for specific use case:

```python
# custom_config.py
"""
Custom OVC configuration for urban high-rise validation
"""
from ovc.core.config import Config, OverlapConfig, RoadConflictThresholds
from ovc.export.pipeline import run_pipeline
from pathlib import Path

# Create custom config object
custom_config = Config(
    overlap=OverlapConfig(
        min_intersection_area_m2=0.5,     # Lower threshold
        partial_ratio_min=0.20            # More sensitive (20%)
    ),
    road_conflict=RoadConflictThresholds(
        road_buffer_m=5.0                 # Larger road buffer for highways
    )
)

# Run pipeline with custom config
outputs = run_pipeline(
    boundary_path=None,
    buildings_path=Path("data/downtown_buildings.gpkg"),
    roads_path=Path("data/highways.gpkg"),
    out_dir=Path("results/urban_qc"),
    config=custom_config
)

print(f"Results saved to {outputs.gpkg_path}")
```

---

### Example 19: Generate QC Summary Report

**Create a comprehensive summary report:**

```python
#!/usr/bin/env python3
"""
Generate QC summary report from OVC results
"""
import pandas as pd
import geopandas as gpd
from pathlib import Path

def generate_report(results_dir):
    results_dir = Path(results_dir)
    
    # Load results
    overlaps = gpd.read_file(results_dir / 'building_overlaps.geojson')
    boundaries = gpd.read_file(results_dir / 'boundary_violations.geojson')
    roads = gpd.read_file(results_dir / 'road_conflicts.geojson')
    
    # Generate statistics
    report = {
        'Total Overlaps': len(overlaps),
        'Critical Overlaps': len(overlaps[overlaps['severity'] == 'critical']),
        'High Severity': len(overlaps[overlaps['severity'] == 'high']),
        'Medium Severity': len(overlaps[overlaps['severity'] == 'medium']),
        'Low Severity': len(overlaps[overlaps['severity'] == 'low']),
        'Boundary Violations': len(boundaries),
        'Road Conflicts': len(roads),
        'Total Issues': len(overlaps) + len(boundaries) + len(roads)
    }
    
    # Create report
    report_df = pd.DataFrame([report]).T
    report_df.columns = ['Count']
    
    # Save to CSV
    report_df.to_csv(results_dir / 'qc_summary_report.csv')
    
    # Print summary
    print("\n" + "="*50)
    print("QC SUMMARY REPORT")
    print("="*50)
    print(report_df)
    print("="*50 + "\n")
    
    return report

# Run
if __name__ == "__main__":
    generate_report("results/my_qc")
```

---

### Example 20: Filter and Export Specific Issues

**Extract only high-priority issues:**

```python
#!/usr/bin/env python3
"""
Filter and export high-priority QC issues
"""
import geopandas as gpd

# Load all overlaps
overlaps = gpd.read_file('results/building_overlaps.geojson')

# Filter critical and high severity
priority_overlaps = overlaps[
    overlaps['severity'].isin(['critical', 'high'])
]

# Filter large overlaps (>50 sq meters)
large_overlaps = overlaps[overlaps['overlap_area'] > 50]

# Filter high percentage overlaps (>30%)
high_pct_overlaps = overlaps[
    (overlaps['overlap_pct_a'] > 30) | 
    (overlaps['overlap_pct_b'] > 30)
]

# Export filtered results
priority_overlaps.to_file(
    'results/priority_overlaps.geojson',
    driver='GeoJSON'
)

large_overlaps.to_file(
    'results/large_overlaps.geojson',
    driver='GeoJSON'
)

high_pct_overlaps.to_file(
    'results/high_percentage_overlaps.geojson',
    driver='GeoJSON'
)

print(f"Priority overlaps: {len(priority_overlaps)}")
print(f"Large overlaps: {len(large_overlaps)}")
print(f"High percentage overlaps: {len(high_pct_overlaps)}")
```

---

### Example 18: Temporal QC Analysis

**Compare QC results over time:**

```bash
#!/bin/bash
# temporal_analysis.sh

# QC for different time periods
DATES=("2024-01" "2024-06" "2024-12")

for date in "${DATES[@]}"; do
  echo "Processing $date..."
  
  # Extract buildings for this date
  ogr2ogr -where "date_created <= '$date-31'" \
    "buildings_$date.shp" \
    all_buildings.shp
  
  # Run QC
  python scripts/run_qc.py \
    --buildings "buildings_$date.shp" \
    --out "results/temporal/$date"
done

# Compare results
echo "Temporal Analysis"
echo "================="
for date in "${DATES[@]}"; do
  overlaps=$(wc -l < "results/temporal/$date/building_overlaps.csv")
  echo "$date: $overlaps overlaps"
done
```

---

## Real-World Scenarios

### Example 19: Humanitarian Mapping QC

**Quality control for humanitarian mapping project:**

```bash
# Download HOT OSM data
wget https://export.hotosm.org/downloads/region_buildings.geojson

# Run comprehensive QC
python scripts/run_qc.py \
  --buildings region_buildings.geojson \
  --boundary affected_area.geojson \
  --out results/humanitarian_qc

# Generate priority list for field verification
python filter_priority_issues.py \
  --input results/humanitarian_qc \
  --output field_verification_list.csv
```

---

### Example 20: Government Cadastre Validation

**Validate official building registry:**

```bash
# Export from cadastre database
ogr2ogr -f GPKG cadastre_buildings.gpkg \
  PG:"dbname=cadastre user=admin" \
  -sql "SELECT * FROM buildings WHERE status='active'"

# Run QC with strict thresholds
python scripts/run_qc.py \
  --buildings cadastre_buildings.gpkg \
  --boundary administrative_boundary.geojson \
  --out results/cadastre_validation

# Generate compliance report
python generate_compliance_report.py \
  --results results/cadastre_validation \
  --template templates/official_report.docx \
  --output cadastre_compliance_report.pdf
```

---

## Next Steps

- **Learn step-by-step:** Follow detailed [Tutorials](tutorials.md)
- **Explore the API:** Read [API Reference](api-reference.md)
- **Understand configuration:** Check [User Guide](user-guide.md)

---

[← Back to Documentation](index.md) | [API Reference →](api-reference.md)