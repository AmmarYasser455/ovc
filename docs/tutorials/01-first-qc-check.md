---
layout: default
title: Tutorial 1 - First QC Check
parent: Tutorials
nav_order: 1
---

# Tutorial 1: Your First QC Check

**Goal:** Run your first quality control check on a buildings dataset.

**Prerequisites:**
- OVC installed
- Sample buildings dataset

**Time:** 10 minutes

### Step 1: Prepare Your Data

Download the sample dataset or use your own:

```bash
# Create a data directory
mkdir -p data

# If using sample data
wget https://github.com/AmmarYasser455/ovc/raw/main/sample_data/buildings.shp -P data/
```

### Step 2: Run OVC

Execute the quality control check:

```bash
python scripts/run_qc.py \
  --buildings data/buildings.shp \
  --out results/my_first_qc
```

**What's happening:**
- OVC loads your buildings
- Checks for overlapping geometries
- Checks for road-building conflicts (if roads are provided)
- Generates reports and maps

### Step 3: Examine the Results

Navigate to the output directory:

```bash
cd results/my_first_qc
ls -lh
```

You should see:
```
building_overlaps.geojson
building_overlaps.csv
road_conflicts.geojson
road_conflicts.csv
validation_report.html
summary_statistics.csv
```

### Step 4: Open the Interactive Map

**On Linux/macOS:**
```bash
xdg-open validation_report.html  # Linux
open validation_report.html      # macOS
```

**On Windows:**
```bash
start validation_report.html
```

### Step 5: Interpret the Results

**In the map:**
- Overlapping buildings
- Road conflicts
- Roads
- Clean buildings

**In the CSV files:**

Open `building_overlaps.csv`:
```csv
building_a,building_b,overlap_area,overlap_pct_a,overlap_pct_b,severity
101,102,45.23,12.5,8.3,medium
103,104,120.45,35.2,33.8,high
```

- `building_a`, `building_b`: IDs of overlapping buildings
- `overlap_area`: Area of overlap in square meters
- `overlap_pct_a/b`: Percentage of each building overlapped
- `severity`: Issue priority (low, medium, high, critical)

### Step 6: View Summary Statistics

```bash
cat summary_statistics.csv
```

Expected output:
```csv
metric,value
total_buildings,1523
overlapping_buildings,87
overlap_percentage,5.7
road_conflicts,34
critical_issues,8
```

**Congratulations!** You've completed your first QC check! 🎉

---

[Next: Working with Local Data →](02-working-with-local-data.md)
