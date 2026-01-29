---
layout: default
title: Tutorial 3 - Custom Configuration
parent: Tutorials
nav_order: 3
---

# Tutorial 3: Custom Configuration for Different Scenarios

**Goal:** Configure OVC for different use cases and data quality standards.

**Time:** 20 minutes

### Scenario 1: Urban High-Density Areas

**Challenge:** Many legitimate buildings very close together.

**Solution:** Adjust thresholds to reduce false positives.

```python
# Create custom_config.py
"""
Configuration for urban high-density validation
"""
from ovc.core import config

# Higher area threshold (only flag larger overlaps)
config.MIN_OVERLAP_AREA = 5.0

# Higher percentage threshold
config.OVERLAP_PERCENTAGE_THRESHOLD = 10.0

# Smaller road buffer (buildings closer to roads is normal)
config.ROAD_BUFFER_DISTANCE = 1.0

print("Custom configuration loaded for urban areas")
```

**Run with custom config:**
```bash
# Import custom config first
python -c "import custom_config; from ovc.core.pipeline import QualityControlPipeline; \
           p = QualityControlPipeline(buildings_path='data/downtown.gpkg', output_dir='results/urban'); \
           p.run()"
```

### Scenario 2: Rural/Low-Density Areas

**Challenge:** Buildings should be well-separated; any overlap is suspicious.

**Solution:** Stricter thresholds to catch all potential issues.

```python
# rural_config.py
"""
Configuration for rural area validation
"""
from ovc.core import config

# Lower area threshold (flag even small overlaps)
config.MIN_OVERLAP_AREA = 0.5

# Lower percentage threshold
config.OVERLAP_PERCENTAGE_THRESHOLD = 2.0

# Larger road buffer
config.ROAD_BUFFER_DISTANCE = 3.0

# Strict boundary tolerance
config.BOUNDARY_TOLERANCE = 0.01

print("Custom configuration loaded for rural areas")
```

### Scenario 3: Cadastral/Legal Validation

**Challenge:** Legal property boundaries require extreme precision.

**Solution:** Maximum strictness on all checks.

```python
# cadastral_config.py
"""
Configuration for cadastral/legal validation
"""
from ovc.core import config

# Zero tolerance for overlaps
config.MIN_OVERLAP_AREA = 0.1
config.OVERLAP_PERCENTAGE_THRESHOLD = 1.0

# No buildings should touch roads
config.ROAD_BUFFER_DISTANCE = 5.0
config.ROAD_INTERSECTION_TOLERANCE = 0.1

# Strict boundary compliance
config.BOUNDARY_TOLERANCE = 0.01
config.CHECK_PARTIAL_BOUNDARY_OVERLAP = True

print("Cadastral validation configuration loaded")
```

### Scenario 4: Rapid Mapping / Humanitarian Response

**Challenge:** Speed is critical; focus on major issues only.

**Solution:** Relaxed thresholds to reduce review time.

```python
# humanitarian_config.py
"""
Configuration for rapid humanitarian mapping
"""
from ovc.core import config

# Only flag significant overlaps
config.MIN_OVERLAP_AREA = 10.0
config.OVERLAP_PERCENTAGE_THRESHOLD = 25.0

# Relaxed road buffers
config.ROAD_BUFFER_DISTANCE = 2.0

# Less strict boundary checking
config.BOUNDARY_TOLERANCE = 1.0

print("Humanitarian mapping configuration loaded")
```

### Using Configuration Files

**Method 1: Direct import**
```bash
python -c "import custom_config; exec(open('your_script.py').read())"
```

**Method 2: Modify before pipeline**
```python
from ovc.core import config
from ovc.core.pipeline import QualityControlPipeline

# Modify config
config.MIN_OVERLAP_AREA = 5.0
config.OVERLAP_PERCENTAGE_THRESHOLD = 10.0

# Run pipeline with modified config
pipeline = QualityControlPipeline(
    buildings_path="data/buildings.shp",
    output_dir="results/custom"
)
pipeline.run()
```

---

[Next: Building a QC Workflow →](04-building-qc-workflow.md)
