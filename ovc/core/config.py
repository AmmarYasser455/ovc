from __future__ import annotations

from dataclasses import dataclass


# Runtime overlap configuration 

@dataclass(frozen=True)
class OverlapConfig:
    duplicate_ratio_min: float = 0.98
    partial_ratio_min: float = 0.30
    min_intersection_area_m2: float = 0.5


# Backward-compatible wrapper 

class OverlapThresholds(OverlapConfig):
    def __init__(
        self,
        duplicate_ratio_min: float | None = None,
        duplicate_min_ratio: float | None = None,
        partial_ratio_min: float | None = None,
        partial_min_ratio: float | None = None,
        sliver_max_ratio: float | None = None,  
        sliver_max_intersection_area_m2: float | None = None,  
        min_intersection_area_m2: float = 0.5,
    ):
        # duplicate ratio
        if duplicate_ratio_min is not None:
            dup = duplicate_ratio_min
        elif duplicate_min_ratio is not None:
            dup = duplicate_min_ratio
        else:
            dup = 0.98

        # partial ratio
        if partial_ratio_min is not None:
            part = partial_ratio_min
        elif partial_min_ratio is not None:
            part = partial_min_ratio
        else:
            part = 0.30

        
        super().__init__(
            duplicate_ratio_min=dup,
            partial_ratio_min=part,
            min_intersection_area_m2=min_intersection_area_m2,
        )


# Other configs 

@dataclass(frozen=True)
class RoadConflictThresholds:
    road_buffer_m: float = 1.0
    min_intersection_area_m2: float = 0.5


@dataclass(frozen=True)
class Tags:
    buildings: dict
    roads: dict


@dataclass(frozen=True)
class Config:
    overlap: OverlapConfig = OverlapConfig()
    road_conflict: RoadConflictThresholds = RoadConflictThresholds()
    tags: Tags = Tags(
        buildings={"building": True},
        roads={"highway": True},
    )


DEFAULT_CONFIG = Config()
