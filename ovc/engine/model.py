"""Result model shared by every OVC interface (map app, CLI, Python API)."""

from __future__ import annotations

from dataclasses import dataclass, field

import geopandas as gpd
import pandas as pd

# Run status ------------------------------------------------------------
STATUS_CLEAN = "clean"  # every requested check ran on every feature, 0 findings
STATUS_ISSUES = "issues"  # every requested check ran on every feature, findings
STATUS_PARTIAL = "partial"  # ran, but features were skipped or a check is incomplete
STATUS_FAILED = "failed"  # could not run; there is no result to trust

# Check status ----------------------------------------------------------
CHECK_COMPLETE = "complete"
CHECK_INCOMPLETE = "incomplete"  # ran, but the result does not cover everything
CHECK_NOT_RUN = "not_run"  # requested, but an input it needs is missing or unusable

# issue_type -> (check it belongs to, label shown to the analyst, map colour).
# This is the one place an issue type is declared: the app's legend, filter
# chips and symbology, and the export, all read it from here.
ISSUE_TYPES = {
    "overlap": ("overlap", "Overlap", "#d32f2f"),
    "containment": ("overlap", "Feature inside another", "#ef6c00"),
    "duplicate": ("overlap", "Duplicate feature", "#7b1fa2"),
    "gap": ("gap", "Gap", "#00838f"),
    "invalid_geometry": ("input", "Invalid geometry", "#5d4037"),
    "empty_geometry": ("input", "Empty geometry", "#757575"),
    "not_polygon": ("input", "Not a polygon", "#757575"),
}

FINDING_COLUMNS = [
    "finding_id",
    "check",
    "issue_type",
    "fid_a",
    "fid_b",
    "id_a",
    "id_b",
    "area_m2",
    "overlap_ratio",
    "related_fids",
    "reason",
]


@dataclass
class CheckOutcome:
    """What happened to one requested check."""

    name: str
    requested: bool
    status: str = CHECK_NOT_RUN
    count: int = 0
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "requested": self.requested,
            "status": self.status,
            "count": self.count,
            "message": self.message,
        }


@dataclass
class Measurement:
    """How areas were measured for a run."""

    source_crs: object | None  # pyproj.CRS of the input layer
    working_crs: object | None  # pyproj.CRS geometry operations ran in
    unit_to_m: float = 1.0  # metres per working-CRS unit
    method: str = ""  # plain-language description shown with every area
    reprojected: bool = False

    def area_m2(self, area_in_crs_units):
        """Convert a planar area in working-CRS units to square metres."""
        return area_in_crs_units * self.unit_to_m**2


def empty_findings(crs=None) -> gpd.GeoDataFrame:
    df = pd.DataFrame({c: pd.Series(dtype="object") for c in FINDING_COLUMNS})
    return gpd.GeoDataFrame(df, geometry=gpd.GeoSeries([], crs=crs), crs=crs)


@dataclass
class ScanResult:
    """Outcome of one validation run.

    ``findings`` is a GeoDataFrame in the working CRS (see ``measurement``).
    Use :meth:`findings_in` to get them in another CRS, for example the
    source layer's CRS for export or EPSG:4326 for a web map.
    """

    status: str
    message: str
    findings: gpd.GeoDataFrame = field(default_factory=empty_findings)
    checks: dict = field(default_factory=dict)
    feature_count: int = 0
    checked_count: int = 0
    skipped: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    measurement: Measurement | None = None
    options: dict = field(default_factory=dict)
    error: str | None = None

    @property
    def ok(self) -> bool:
        """True only for a complete run without findings."""
        return self.status == STATUS_CLEAN

    def counts_by_type(self) -> dict:
        if self.findings is None or self.findings.empty:
            return {}
        return {
            str(k): int(v)
            for k, v in self.findings["issue_type"].value_counts().items()
        }

    def findings_in(self, crs) -> gpd.GeoDataFrame:
        """Findings reprojected to ``crs`` (areas stay as measured, in m²)."""
        f = self.findings
        if f is None or f.crs is None or crs is None:
            return f
        return f.to_crs(crs)

    def summary(self) -> dict:
        m = self.measurement
        return {
            "status": self.status,
            "message": self.message,
            "error": self.error,
            "feature_count": self.feature_count,
            "checked_count": self.checked_count,
            "skipped_count": len(self.skipped),
            "skipped": self.skipped,
            "finding_count": 0 if self.findings is None else int(len(self.findings)),
            "counts_by_type": self.counts_by_type(),
            "checks": {k: v.to_dict() for k, v in self.checks.items()},
            "warnings": list(self.warnings),
            "area_method": m.method if m else "",
            "working_crs": crs_label(m.working_crs) if m else "",
            "source_crs": crs_label(m.source_crs) if m else "",
            "options": dict(self.options),
        }


def crs_label(crs) -> str:
    """Short human label such as ``EPSG:32636 - WGS 84 / UTM zone 36N``."""
    if crs is None:
        return "missing"
    try:
        epsg = crs.to_epsg()
    except Exception:  # pragma: no cover - defensive, label only
        epsg = None
    name = getattr(crs, "name", "") or ""
    if epsg:
        return f"EPSG:{epsg} - {name}" if name else f"EPSG:{epsg}"
    return name or "custom CRS"
