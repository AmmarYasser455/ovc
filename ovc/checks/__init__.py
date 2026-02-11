# Quality control checks
from ovc.checks.overlap import find_building_overlaps, OverlapThresholds
from ovc.checks.road_conflict import find_buildings_on_roads
from ovc.checks.boundary_overlap import find_buildings_touching_boundary
from ovc.checks.geometry_quality import (
    find_duplicate_geometries,
    find_invalid_geometries,
    find_unreasonable_areas,
    compute_compactness,
    find_min_road_distance_violations,
)

__all__ = [
    "find_building_overlaps",
    "OverlapThresholds",
    "find_buildings_on_roads",
    "find_buildings_touching_boundary",
    "find_duplicate_geometries",
    "find_invalid_geometries",
    "find_unreasonable_areas",
    "compute_compactness",
    "find_min_road_distance_violations",
]
