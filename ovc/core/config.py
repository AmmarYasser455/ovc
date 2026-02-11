from __future__ import annotations

from dataclasses import dataclass

# Runtime overlap configuration


@dataclass(frozen=True)
class OverlapConfig:
    duplicate_ratio_min: float = 0.98
    partial_ratio_min: float = 0.30
    min_intersection_area_m2: float = 0.5


@dataclass(frozen=True)
class RoadConflictThresholds:
    road_buffer_m: float = 1.0
    min_intersection_area_m2: float = 0.5


@dataclass(frozen=True)
class Config:
    overlap: OverlapConfig = OverlapConfig()
    road_conflict: RoadConflictThresholds = RoadConflictThresholds()


DEFAULT_CONFIG = Config()
