---
layout: default
title: Tutorial 2 - Working with OSM Data
parent: Tutorials
nav_order: 2
---

# Tutorial 2: Working with OpenStreetMap Data

**Goal:** Download and validate OpenStreetMap data for your area of interest.

**Prerequisites:**
- OVC installed
- Boundary file for your area

**Time:** 15 minutes

### Step 1: Create a Boundary File

Create a GeoJSON file for your area using [geojson.io](https://geojson.io):

1. Go to https://geojson.io
2. Draw a polygon around your area of interest
3. Click "Save" → "GeoJSON"
4. Save as `data/my_area.geojson`

**Or use an existing boundary:**
```bash
# Download a city boundary
wget "https://nominatim.openstreetmap.org/search?q=Cairo,Egypt&format=geojson&polygon_geojson=1" \
  -O data/cairo_boundary.geojson
```

### Step 2: Run OVC with Boundary

Download OSM data and run QC:

```bash
python scripts/run_qc.py \
  --boundary data/my_area.geojson \
  --out results/osm_qc \
  --verbose
```

**What's happening:**
1. OVC reads your boundary
2. Queries OpenStreetMap Overpass API
3. Downloads buildings within boundary
4. Downloads roads within boundary
5. Performs all QC checks
6. Generates comprehensive reports

### Step 3: Monitor the Progress

With `--verbose` flag, you'll see:

```
[INFO] Loading boundary from data/my_area.geojson
[INFO] Boundary area: 2.45 km²
[INFO] Downloading buildings from OpenStreetMap...
[INFO] Downloaded 3,421 buildings
[INFO] Downloading roads from OpenStreetMap...
[INFO] Downloaded 245 road segments
[INFO] Running overlap detection...
[INFO] Found 156 overlapping building pairs
[INFO] Running boundary validation...
[INFO] Found 12 boundary violations
[INFO] Running road conflict detection...
[INFO] Found 45 road conflicts
[INFO] Generating outputs...
[INFO] QC complete! Results saved to results/osm_qc
```

### Step 4: Analyze OSM Data Quality

Open the results and look for:

**Common OSM issues:**
- Duplicate buildings (100% overlap)
- Buildings extending beyond boundary
- Buildings intersecting roads
- Incomplete geometries

### Step 5: Export Issues for OSM Editing

Extract critical issues to fix in JOSM or iD editor:

```python
import geopandas as gpd

# Load critical overlaps
overlaps = gpd.read_file('results/osm_qc/building_overlaps.geojson')
critical = overlaps[overlaps['severity'] == 'critical']

# Export for OSM editing
critical.to_file('osm_fixes_needed.geojson', driver='GeoJSON')

print(f"Export {len(critical)} buildings needing fixes")
```

### Step 6: Validate Your Fixes

After editing in OSM:

1. Wait 24 hours for OSM to update
2. Re-run OVC with the same boundary
3. Compare results to verify improvements

```bash
# Re-run QC
python scripts/run_qc.py \
  --boundary data/my_area.geojson \
  --out results/osm_qc_after_fixes

# Compare results
diff results/osm_qc/summary_statistics.csv \
     results/osm_qc_after_fixes/summary_statistics.csv
```

---

[Next: Custom Configuration →](03-custom-configuration.md)
