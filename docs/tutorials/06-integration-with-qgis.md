---
layout: default
title: Tutorial 6 - Integration with QGIS
parent: Tutorials
nav_order: 6
---

# Tutorial 6: Integration with QGIS

**Goal:** Use OVC results in QGIS for visualization and editing.

**Time:** 20 minutes

### Step 1: Load OVC Results into QGIS

**Method 1: Drag and Drop**

1. Open QGIS
2. Drag `building_overlaps.geojson` into the map canvas
3. Drag `road_conflicts.geojson` into the map canvas
4. Drag `boundary_violations.geojson` into the map canvas

**Method 2: Add Vector Layer**

1. Layer → Add Layer → Add Vector Layer
2. Navigate to your results directory
3. Select all GeoJSON files
4. Click "Add"

### Step 2: Style Layers by Severity

**For building overlaps:**

1. Right-click "building_overlaps" layer
2. Properties → Symbology
3. Select "Categorized"
4. Column: "severity"
5. Click "Classify"
6. Customize colors:
   - Critical: Red (#FF0000)
   - High: Orange (#FF8800)
   - Medium: Yellow (#FFFF00)
   - Low: Green (#88FF00)
7. Click "OK"

**For road conflicts:**

1. Right-click "road_conflicts" layer
2. Properties → Symbology
3. Select "Categorized"
4. Column: "conflict_type"
5. Click "Classify"
6. Apply

### Step 3: Create Custom Labels

1. Right-click "building_overlaps" layer
2. Properties → Labels
3. Select "Single Labels"
4. Value: Select "overlap_area"
5. Text tab: Adjust font size
6. Placement tab: Choose "Horizontal"
7. Click "OK"

### Step 4: Filter Features

**Show only critical issues:**

1. Right-click "building_overlaps" layer
2. Filter → Filter Features
3. Expression: `"severity" = 'critical'`
4. Click "OK"

**Show large overlaps:**

1. Filter expression: `"overlap_area" > 50`

### Step 5: Use Selection Tools

**Select buildings with multiple conflicts:**

1. Open Attribute Table for "building_overlaps"
2. Select by Expression
3. Expression: 
   ```sql
   "building_a" IN (
     SELECT "building_a"
     FROM "building_overlaps"
     GROUP BY "building_a"
     HAVING COUNT(*) > 1
   )
   ```
4. Click "Select Features"

### Step 6: Export Selected Features

1. Right-click layer → Export → Save Selected Features As
2. Format: GeoJSON or Shapefile
3. File name: `multiple_conflicts.geojson`
4. Click "OK"

### Step 7: Edit Geometries

**Fix overlapping buildings:**

1. Select layer with buildings (not overlaps)
2. Toggle Editing (yellow pencil icon)
3. Select the building to edit
4. Use "Vertex Tool" to adjust boundaries
5. Save Edits

**Merge duplicates:**

1. Select both duplicate buildings
2. Vector → Geoprocessing Tools → Dissolve
3. Dissolve field: Leave blank
4. Click "Run"

### Step 8: Create Print Layout

1. Project → New Print Layout
2. Add Map item
3. Add Legend item
4. Add Title: "QC Results - [Date]"
5. Add Scale Bar
6. Export as PDF

### Step 9: Automate with Python Console

Open QGIS Python Console and run:

```python
from qgis.core import QgsVectorLayer, QgsProject

# Add layer
layer = QgsVectorLayer(
    'results/building_overlaps.geojson',
    'Overlaps',
    'ogr'
)

# Add to project
QgsProject.instance().addMapLayer(layer)

# Filter critical issues
layer.setSubsetString("severity = 'critical'")

# Zoom to layer
iface.mapCanvas().setExtent(layer.extent())
iface.mapCanvas().refresh()

print(f"Loaded {layer.featureCount()} critical overlaps")
```

---

[Next: Automating QC with Python →](07-automating-qc-with-python.md)
