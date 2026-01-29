---
layout: default
title: Tutorial 5 - Analyzing Issues
parent: Tutorials
nav_order: 5
---

# Tutorial 5: Analyzing and Fixing Issues

**Goal:** Identify, analyze, and fix quality issues found by OVC.

**Time:** 25 minutes

### Step 1: Load and Explore Results

```python
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt

# Load results
overlaps = gpd.read_file('results/building_overlaps.geojson')
boundaries = gpd.read_file('results/boundary_violations.geojson')
roads = gpd.read_file('results/road_conflicts.geojson')

# Overview
print(f"Total overlaps: {len(overlaps)}")
print(f"Boundary violations: {len(boundaries)}")
print(f"Road conflicts: {len(roads)}")

# Severity distribution
print("\nOverlap severity distribution:")
print(overlaps['severity'].value_counts())
```

### Step 2: Prioritize Issues

**Create priority list:**

```python
# Define priority scoring
def calculate_priority_score(row):
    severity_scores = {
        'critical': 100,
        'high': 75,
        'medium': 50,
        'low': 25
    }
    
    base_score = severity_scores.get(row['severity'], 0)
    area_score = min(row['overlap_area'] / 10, 50)  # Max 50 points for area
    
    return base_score + area_score

# Add priority scores
overlaps['priority_score'] = overlaps.apply(calculate_priority_score, axis=1)

# Sort by priority
priority_list = overlaps.sort_values('priority_score', ascending=False)

# Export top 20 for immediate action
top_priority = priority_list.head(20)
top_priority.to_file('priority_fixes.geojson', driver='GeoJSON')

print(f"\nTop 20 priority issues exported to priority_fixes.geojson")
```

### Step 3: Analyze Patterns

**Spatial clustering of issues:**

```python
from sklearn.cluster import DBSCAN
import numpy as np

# Extract centroids
centroids = overlaps.geometry.centroid
coords = np.array([[p.x, p.y] for p in centroids])

# Cluster overlaps
clustering = DBSCAN(eps=0.001, min_samples=3).fit(coords)
overlaps['cluster'] = clustering.labels_

# Identify hotspots
cluster_counts = overlaps[overlaps['cluster'] != -1]['cluster'].value_counts()
print(f"\nFound {len(cluster_counts)} hotspot areas")
print(f"Largest hotspot has {cluster_counts.max()} overlaps")

# Export hotspots
for cluster_id in cluster_counts.head(5).index:
    hotspot = overlaps[overlaps['cluster'] == cluster_id]
    hotspot.to_file(f'hotspot_{cluster_id}.geojson', driver='GeoJSON')
```

### Step 4: Categorize Issues by Type

```python
# Categorize overlaps by type
def categorize_overlap(row):
    pct_a = row['overlap_pct_a']
    pct_b = row['overlap_pct_b']
    
    if pct_a > 95 and pct_b > 95:
        return 'duplicate'
    elif pct_a > 90 or pct_b > 90:
        return 'near_duplicate'
    elif pct_a > 50 or pct_b > 50:
        return 'major_overlap'
    else:
        return 'minor_overlap'

overlaps['issue_type'] = overlaps.apply(categorize_overlap, axis=1)

# Statistics by type
print("\nIssue types:")
print(overlaps['issue_type'].value_counts())

# Export by type
for issue_type in overlaps['issue_type'].unique():
    subset = overlaps[overlaps['issue_type'] == issue_type]
    subset.to_file(f'issues_{issue_type}.geojson', driver='GeoJSON')
```

### Step 5: Generate Fix Recommendations

```python
def recommend_fix(row):
    """Generate fix recommendation based on issue type"""
    issue_type = row['issue_type']
    
    recommendations = {
        'duplicate': 'DELETE: Remove one of the duplicate buildings',
        'near_duplicate': 'MERGE: Combine geometries and verify',
        'major_overlap': 'EDIT: Adjust boundaries to remove overlap',
        'minor_overlap': 'REVIEW: Verify if overlap is acceptable'
    }
    
    return recommendations.get(issue_type, 'REVIEW: Manual inspection needed')

overlaps['recommendation'] = overlaps.apply(recommend_fix, axis=1)

# Export with recommendations
overlaps[['building_a', 'building_b', 'issue_type', 'recommendation']].to_csv(
    'fix_recommendations.csv',
    index=False
)

print("\nFix recommendations exported to fix_recommendations.csv")
```

### Step 6: Create Fix Workflow

```python
#!/usr/bin/env python3
"""
fix_workflow.py - Automated fixing where possible
"""
import geopandas as gpd
from shapely.ops import unary_union

# Load original buildings
buildings = gpd.read_file('data/buildings.gpkg')

# Load duplicates to remove
duplicates = overlaps[overlaps['issue_type'] == 'duplicate']

# Create fix list
buildings_to_remove = set(duplicates['building_b'].values)

# Filter out duplicates
cleaned_buildings = buildings[~buildings['id'].isin(buildings_to_remove)]

# Save cleaned version
cleaned_buildings.to_file(
    'data/buildings_cleaned.gpkg',
    driver='GPKG'
)

print(f"Removed {len(buildings_to_remove)} duplicate buildings")
print(f"Cleaned dataset: {len(cleaned_buildings)} buildings")

# Re-run QC on cleaned data
print("\nRe-running QC on cleaned data...")
# (Run OVC again here)
```

### Step 7: Validate Fixes

```bash
# Run QC on cleaned data
python scripts/run_qc.py \
    --buildings data/buildings_cleaned.gpkg \
    --out results/qc_after_fixes

# Compare before/after
echo "Issues before fixes:"
wc -l < results/qc_original/building_overlaps.csv

echo "Issues after fixes:"
wc -l < results/qc_after_fixes/building_overlaps.csv
```

### Step 8: Document Changes

```python
import json
from datetime import datetime

# Create change log
changes = {
    'date': datetime.now().isoformat(),
    'original_building_count': len(buildings),
    'cleaned_building_count': len(cleaned_buildings),
    'buildings_removed': len(buildings_to_remove),
    'issues_fixed': {
        'duplicates': len(duplicates),
        'near_duplicates': 0,  # Update with actual numbers
        'major_overlaps': 0,
    },
    'remaining_issues': len(overlaps) - len(duplicates)
}

# Save change log
with open('fix_changelog.json', 'w') as f:
    json.dump(changes, f, indent=2)

print("\nChange log saved to fix_changelog.json")
```

---

[Next: Integration with QGIS →](06-integration-with-qgis.md)
