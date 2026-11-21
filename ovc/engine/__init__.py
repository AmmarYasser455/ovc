"""OVC topology engine: overlaps, gaps, input quality and area measurement.

Every interface (map app, ``ovc check``, :func:`ovc.check_file` and the
building QC pipeline) calls this package. It has no file I/O.
"""

from ovc.engine.model import (
    CHECK_COMPLETE,
    CHECK_INCOMPLETE,
    CHECK_NOT_RUN,
    ISSUE_TYPES,
    STATUS_CLEAN,
    STATUS_FAILED,
    STATUS_ISSUES,
    STATUS_PARTIAL,
    CheckOutcome,
    Measurement,
    ScanResult,
    crs_label,
)
from ovc.engine.scan import (
    DEFAULT_DUPLICATE_RATIO,
    DEFAULT_MIN_AREA_M2,
    check_polygons,
)

__all__ = [
    "check_polygons",
    "ScanResult",
    "CheckOutcome",
    "Measurement",
    "ISSUE_TYPES",
    "STATUS_CLEAN",
    "STATUS_ISSUES",
    "STATUS_PARTIAL",
    "STATUS_FAILED",
    "CHECK_COMPLETE",
    "CHECK_INCOMPLETE",
    "CHECK_NOT_RUN",
    "DEFAULT_MIN_AREA_M2",
    "DEFAULT_DUPLICATE_RATIO",
    "crs_label",
]
