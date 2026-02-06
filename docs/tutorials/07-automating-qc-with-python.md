---
layout: default
title: Tutorial 7 - Python Automation
parent: Tutorials
nav_order: 7
---

# Tutorial 7: Automating QC with Python

**Goal:** Build a fully automated QC system using Python.

**Time:** 30 minutes

### Step 1: Create QC Automation Script

Create `automated_qc.py`:

```python
#!/usr/bin/env python3
"""
automated_qc.py - Fully automated QC system
"""
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime
import geopandas as gpd
import pandas as pd
import yaml

class AutomatedQC:
    def __init__(self, config_file='config.yaml'):
        """Initialize automated QC system"""
        self.config = self.load_config(config_file)
        self.pipeline_outputs = None

    def load_config(self, config_file):
        """Load configuration from YAML file"""
        with open(config_file) as f:
            return yaml.safe_load(f)

    def run_qc(self):
        """Execute quality control checks"""
        print("Running QC checks...")

        from ovc.export.pipeline import run_pipeline

        # Convert string paths to Path objects
        buildings_path = Path(self.config['buildings_path'])
        output_dir = Path(self.config['output_dir'])

        roads_path = self.config.get('roads_path')
        if roads_path:
            roads_path = Path(roads_path)

        boundary_path = self.config.get('boundary_path')
        if boundary_path:
            boundary_path = Path(boundary_path)

        # Run the pipeline
        self.pipeline_outputs = run_pipeline(
            boundary_path=boundary_path,
            buildings_path=buildings_path,
            roads_path=roads_path,
            out_dir=output_dir
        )

        print(f"Pipeline finished. Results at: {self.pipeline_outputs.gpkg_path}")
        return self.pipeline_outputs

    def analyze_results(self):
        """Analyze QC results from the generated GeoPackage"""
        print("Analyzing results...")

        if not self.pipeline_outputs:
            print("Error: Pipeline has not run yet.")
            return {}

        gpkg_path = self.pipeline_outputs.gpkg_path

        try:
            # Read errors layer from GeoPackage
            errors = gpd.read_file(gpkg_path, layer='errors')
        except Exception:
            # Layer might not exist if no errors found
            errors = gpd.GeoDataFrame()

        self.metrics = {
            'total_issues': len(errors),
            'building_overlaps': len(errors[errors['error_type'] == 'building_overlap']),
            'boundary_violations': len(errors[errors['error_type'] == 'outside_boundary']),
            'road_conflicts': len(errors[errors['error_type'] == 'building_on_road']),
            'critical_count': len(errors[errors['error_class'] == 'duplicate']) if not errors.empty else 0,
        }

        # Print summary
        for k, v in self.metrics.items():
            print(f"- {k}: {v}")

        return self.metrics

    def check_thresholds(self):
        """Check if results exceed acceptable thresholds"""
        thresholds = self.config.get('thresholds', {})

        issues = []

        if self.metrics['critical_count'] > thresholds.get('max_critical', 0):
            issues.append(
                f"Critical errors ({self.metrics['critical_count']}) exceed threshold"
            )

        if self.metrics['total_issues'] > thresholds.get('max_total', 100):
            issues.append(
                f"Total issues ({self.metrics['total_issues']}) exceed threshold"
            )

        return issues

    def generate_report(self):
        """Generate simple HTML report"""
        html = f"""
        <html>
        <head><title>QC Report - {datetime.now().strftime('%Y-%m-%d')}</title></head>
        <body>
            <h1>Quality Control Report</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

            <h2>Summary</h2>
            <table border="1">
                <tr><td>Total Issues</td><td>{self.metrics['total_issues']}</td></tr>
                <tr><td>Building Overlaps</td><td>{self.metrics['building_overlaps']}</td></tr>
                <tr><td>Boundary Violations</td><td>{self.metrics['boundary_violations']}</td></tr>
                <tr><td>Road Conflicts</td><td>{self.metrics['road_conflicts']}</td></tr>
            </table>

            <h2>Status</h2>
            <p>{'✅ PASSED' if len(self.check_thresholds()) == 0 else '❌ FAILED'}</p>
        </body>
        </html>
        """

        report_path = self.pipeline_outputs.webmap_html.parent / 'email_report.html'
        with open(report_path, 'w') as f:
            f.write(html)

        return report_path

    def send_notification(self, report_path):
        """Send email notification (Simulated)"""
        if 'email' not in self.config:
            print("Email configuration not found, skipping notification")
            return

        print(f"📧 Sending notification to {self.config['email']['to']}...")
        # (Email sending logic...)
        print("✅ Notification sent successfully")

    def run(self):
        """Run complete automated QC workflow"""
        print("="*60)
        print("Automated QC System")
        print("="*60)

        self.run_qc()
        self.analyze_results()
        report_path = self.generate_report()

        issues = self.check_thresholds()
        if issues:
            print("\n⚠️ Threshold violations:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("\n✅ All thresholds passed")

        self.send_notification(report_path)

        print("\n" + "="*60)
        print("QC complete!")
        return len(issues) == 0

if __name__ == "__main__":
    qc = AutomatedQC('config.yaml')
    success = qc.run()
    sys.exit(0 if success else 1)
```

### Step 2: Create Configuration File

Create `config.yaml`:

```yaml
# QC Configuration
buildings_path: "data/buildings.gpkg"
roads_path: "data/roads.gpkg"
# boundary_path: "data/boundary.geojson" # Optional
output_dir: "results/automated_qc"

# Thresholds
thresholds:
  max_critical: 5
  max_total: 100

# Email notification
email:
  from: "qc_system@example.com"
  to: "team@example.com"
```

### Step 3: Run Automated QC

```bash
# Install PyYAML if needed
pip install pyyaml

python automated_qc.py
```

---

[← Back to Tutorials](../tutorials.md) | [Back to Documentation](../index.md)
