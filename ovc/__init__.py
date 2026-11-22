"""OVC - Overlap Violation Checker."""

# The single source of the version: packaging reads it from here.
__version__ = "3.8.0"
__author__ = "Ammar Yasser Abdalazim"

# Public names are imported on first use, so the map app and ``ovc check``
# start without loading the building/road pipeline and its web-map stack.
_EXPORTS = {
    "check_file": "ovc.api",
    "check_polygons": "ovc.engine",
    "ScanResult": "ovc.engine",
    "export_findings": "ovc.io",
    "run_pipeline": "ovc.export.pipeline",
    "find_duplicate_geometries": "ovc.checks.geometry_quality",
    "find_invalid_geometries": "ovc.checks.geometry_quality",
    "find_unreasonable_areas": "ovc.checks.geometry_quality",
    "compute_compactness": "ovc.checks.geometry_quality",
    "find_min_road_distance_violations": "ovc.checks.geometry_quality",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name):
    if name in _EXPORTS:
        from importlib import import_module

        value = getattr(import_module(_EXPORTS[name]), name)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'ovc' has no attribute {name!r}")


def __dir__():
    return sorted(list(globals()) + list(_EXPORTS))
