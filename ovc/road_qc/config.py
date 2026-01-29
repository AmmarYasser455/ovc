from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RoadQCConfig:
    """Configuration for road quality control checks."""

    # Dangle detection: max gap (meters) to consider endpoints connected
    dangle_tolerance_m: float = 1.0

    # Self-intersection: buffer for detecting intersection points
    self_intersection_buffer_m: float = 0.1

    # Minimum segment length to consider (meters)
    min_segment_length_m: float = 0.5

    # Disconnected: max distance to nearest road endpoint (meters)
    disconnect_tolerance_m: float = 2.0
