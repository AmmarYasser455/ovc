---
layout: default
title: Tutorial 4 - Building a QC Workflow
parent: Tutorials
nav_order: 4
---

# Tutorial 4: Building a QC Workflow

**Goal:** Create an automated, repeatable QC workflow for your project.

**Time:** 30 minutes

### Step 1: Project Structure

Create a organized project structure:

```bash
mkdir -p qc_project/{data,scripts,results,config,logs}
cd qc_project

tree .
```

```
qc_project/
├── data/
│   ├── raw/          # Original data
│   ├── processed/    # Cleaned data
│   └── boundaries/   # Area boundaries
├── scripts/
│   ├── prepare_data.sh
│   ├── run_qc.sh
│   └── generate_report.py
├── results/
│   └── archive/      # Historical results
├── config/
│   └── qc_config.py
└── logs/
```

### Step 2: Data Preparation Script

Create `scripts/prepare_data.sh`:

```bash
#!/bin/bash
# prepare_data.sh - Prepare data for QC

set -e  # Exit on error

echo "=== Data Preparation Started ==="

# Variables
RAW_DATA="data/raw/buildings.shp"
PROCESSED_DATA="data/processed/buildings_clean.gpkg"
LOG_FILE="logs/preparation_$(date +%Y%m%d_%H%M%S).log"

# Log function
log() {
    echo "[$(date +%Y-%m-%d\ %H:%M:%S)] $1" | tee -a "$LOG_FILE"
}

# Step 1: Validate file exists
log "Checking input file..."
if [ ! -f "$RAW_DATA" ]; then
    log "ERROR: Input file not found: $RAW_DATA"
    exit 1
fi

# Step 2: Reproject to WGS84
log "Reprojecting to WGS84..."
ogr2ogr -t_srs EPSG:4326 \
    -f GPKG \
    data/processed/buildings_wgs84.gpkg \
    "$RAW_DATA"

# Step 3: Fix invalid geometries
log "Fixing invalid geometries..."
ogr2ogr -makevalid \
    -f GPKG \
    "$PROCESSED_DATA" \
    data/processed/buildings_wgs84.gpkg

# Step 4: Add unique IDs if missing
log "Ensuring unique IDs..."
ogrinfo "$PROCESSED_DATA" -sql "ALTER TABLE buildings ADD COLUMN uid INTEGER"
ogrinfo "$PROCESSED_DATA" -sql "UPDATE buildings SET uid = rowid"

# Step 5: Create spatial index
log "Creating spatial index..."
ogrinfo "$PROCESSED_DATA" -sql "CREATE SPATIAL INDEX ON buildings"

log "=== Data Preparation Complete ==="
echo "Processed data: $PROCESSED_DATA"
```

### Step 3: QC Execution Script

Create `scripts/run_qc.sh`:

```bash
#!/bin/bash
# run_qc.sh - Execute quality control

set -e

echo "=== Quality Control Started ==="

# Variables
BUILDINGS="data/processed/buildings_clean.gpkg"
BOUNDARY="data/boundaries/study_area.geojson"
OUTPUT_DIR="results/qc_$(date +%Y%m%d)"
LOG_FILE="logs/qc_$(date +%Y%m%d_%H%M%S).log"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Run QC
echo "Running OVC..." | tee -a "$LOG_FILE"
python /path/to/ovc/scripts/run_qc.py \
    --buildings "$BUILDINGS" \
    --boundary "$BOUNDARY" \
    --out "$OUTPUT_DIR" \
    --verbose 2>&1 | tee -a "$LOG_FILE"

# Archive results
echo "Archiving results..." | tee -a "$LOG_FILE"
tar -czf "results/archive/qc_$(date +%Y%m%d).tar.gz" "$OUTPUT_DIR"

echo "=== Quality Control Complete ===" | tee -a "$LOG_FILE"
echo "Results: $OUTPUT_DIR"
echo "Archive: results/archive/qc_$(date +%Y%m%d).tar.gz"
```

### Step 4: Report Generation Script

Create `scripts/generate_report.py`:

```python
#!/usr/bin/env python3
"""
generate_report.py - Generate QC summary report
"""
import sys
import pandas as pd
import geopandas as gpd
from pathlib import Path
from datetime import datetime

def generate_report(results_dir, output_file):
    """Generate comprehensive QC report"""
    results_dir = Path(results_dir)

    # Load results
    try:
        overlaps = gpd.read_file(results_dir / 'building_overlaps.geojson')
        boundaries = gpd.read_file(results_dir / 'boundary_violations.geojson')
        roads = gpd.read_file(results_dir / 'road_conflicts.geojson')
    except Exception as e:
        print(f"Error loading results: {e}")
        return

    # Calculate statistics
    stats = {
        'Report Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'Total Overlaps': len(overlaps),
        'Critical Overlaps': len(overlaps[overlaps['severity'] == 'critical']),
        'High Severity': len(overlaps[overlaps['severity'] == 'high']),
        'Medium Severity': len(overlaps[overlaps['severity'] == 'medium']),
        'Low Severity': len(overlaps[overlaps['severity'] == 'low']),
        'Boundary Violations': len(boundaries),
        'Road Conflicts': len(roads),
        'Total Issues': len(overlaps) + len(boundaries) + len(roads),
        'Average Overlap Area': overlaps['overlap_area'].mean() if len(overlaps) > 0 else 0,
        'Max Overlap Area': overlaps['overlap_area'].max() if len(overlaps) > 0 else 0,
    }

    # Create DataFrame
    report_df = pd.DataFrame([stats]).T
    report_df.columns = ['Value']

    # Save report
    report_df.to_csv(output_file)

    # Print summary
    print("\n" + "="*60)
    print("QC SUMMARY REPORT")
    print("="*60)
    print(report_df.to_string())
    print("="*60 + "\n")

    # Generate recommendations
    if stats['Critical Overlaps'] > 0:
        print("⚠️  CRITICAL: Immediate action required for critical overlaps")
    if stats['Boundary Violations'] > 0:
        print("⚠️  WARNING: Buildings outside boundary detected")
    if stats['Total Issues'] == 0:
        print("✅ SUCCESS: No issues detected!")

    print(f"\nDetailed report saved to: {output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python generate_report.py <results_dir> <output_file>")
        sys.exit(1)

    generate_report(sys.argv[1], sys.argv[2])
```

### Step 5: Master Workflow Script

Create `scripts/master_workflow.sh`:

```bash
#!/bin/bash
# master_workflow.sh - Complete QC workflow

set -e

echo "╔════════════════════════════════════╗"
echo "║   Complete QC Workflow Pipeline    ║"
echo "╚════════════════════════════════════╝"

# Step 1: Prepare data
echo -e "\n[1/4] Preparing data..."
bash scripts/prepare_data.sh

# Step 2: Run QC
echo -e "\n[2/4] Running quality control..."
bash scripts/run_qc.sh

# Step 3: Generate report
echo -e "\n[3/4] Generating report..."
LATEST_RESULTS=$(ls -td results/qc_* | head -1)
python scripts/generate_report.py \
    "$LATEST_RESULTS" \
    "$LATEST_RESULTS/summary_report.csv"

# Step 4: Open results
echo -e "\n[4/4] Opening results..."
xdg-open "$LATEST_RESULTS/validation_report.html" 2>/dev/null || \
open "$LATEST_RESULTS/validation_report.html" 2>/dev/null || \
start "$LATEST_RESULTS/validation_report.html" 2>/dev/null

echo -e "\n✅ Workflow complete!"
echo "Results: $LATEST_RESULTS"
```

### Step 6: Run the Complete Workflow

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Run complete workflow
bash scripts/master_workflow.sh
```

### Step 7: Schedule Automated Runs

**Using cron (Linux/macOS):**

```bash
# Edit crontab
crontab -e

# Add weekly QC run (every Monday at 2 AM)
0 2 * * 1 cd /path/to/qc_project && bash scripts/master_workflow.sh

# Add daily QC run
0 2 * * * cd /path/to/qc_project && bash scripts/master_workflow.sh
```

**Using Windows Task Scheduler:**

1. Open Task Scheduler
2. Create Basic Task
3. Trigger: Weekly/Daily
4. Action: Start a program
5. Program: `bash.exe`
6. Arguments: `/path/to/qc_project/scripts/master_workflow.sh`

---

[Next: Analyzing and Fixing Issues →](05-analyzing-and-fixing-issues.md)
