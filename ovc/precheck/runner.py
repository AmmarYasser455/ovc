"""
Pre-check runner: runs GeoQA profiling as a data-readiness gate for OVC.

Produces structured quality reports for each input dataset (buildings,
roads, boundary) *before* the main QC pipeline runs. This catches
fundamental data issues (missing CRS, invalid geometries, empty features,
encoding problems) early, saving compute time and giving clear diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import geopandas as gpd

from ovc.core.logging import get_logger

log = get_logger("ovc.precheck")


# ── Result dataclass ────────────────────────────────────────────────────


@dataclass
class PrecheckResult:
    """Structured result from a single dataset pre-check."""

    dataset_name: str
    source_path: Optional[Path] = None
    feature_count: int = 0
    column_count: int = 0
    geometry_type: str = "Unknown"
    crs: Optional[str] = None
    quality_score: float = 0.0
    is_ready: bool = False

    # Geometry issues
    invalid_count: int = 0
    empty_count: int = 0
    null_geom_count: int = 0
    duplicate_count: int = 0

    # Topology issues
    sliver_count: int = 0
    bad_ring_count: int = 0
    overlap_count: int = 0

    # Attribute issues
    total_nulls: int = 0
    null_pct: float = 0.0

    # Report path (if HTML report generated)
    report_path: Optional[Path] = None

    # Warnings / blockers
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    @property
    def has_blockers(self) -> bool:
        """Return True if any blocking issues were found."""
        return len(self.blockers) > 0


@dataclass
class PrecheckSummary:
    """Summary of pre-checks across all input datasets."""

    buildings: Optional[PrecheckResult] = None
    roads: Optional[PrecheckResult] = None
    boundary: Optional[PrecheckResult] = None
    overall_ready: bool = False

    @property
    def all_results(self) -> list[PrecheckResult]:
        return [r for r in [self.buildings, self.roads, self.boundary] if r is not None]


# ── Core functions ──────────────────────────────────────────────────────


def _run_geoqa_profile(
    data_path: Path,
    dataset_name: str,
    out_dir: Optional[Path] = None,
    generate_report: bool = True,
) -> PrecheckResult:
    """Run GeoQA profiling on a single dataset and return structured results.

    Args:
        data_path: Path to the geospatial file.
        dataset_name: Human-readable name for this dataset.
        out_dir: Output directory for the HTML report. If None, no report is generated.
        generate_report: Whether to generate an HTML quality report.

    Returns:
        PrecheckResult with all quality metrics.
    """
    import geoqa
    from geoqa.geometry import TopologyChecker

    result = PrecheckResult(
        dataset_name=dataset_name,
        source_path=data_path,
    )

    # Profile with GeoQA
    try:
        profile = geoqa.profile(str(data_path), name=dataset_name)
    except Exception as e:
        result.blockers.append(f"Failed to load dataset: {e}")
        log.error(f"[precheck] {dataset_name}: Failed to load — {e}")
        return result

    # Basic info
    result.feature_count = profile.feature_count
    result.column_count = profile.column_count
    result.geometry_type = profile.geometry_type
    result.crs = profile.crs
    result.quality_score = round(profile.quality_score, 1)

    # Geometry issues
    geom = profile.geometry_results
    result.invalid_count = geom.get("invalid_count", 0)
    result.empty_count = geom.get("empty_count", 0)
    result.null_geom_count = geom.get("null_count", 0)
    result.duplicate_count = geom.get("duplicate_count", 0)

    # Attribute issues
    attr = profile.attribute_results
    result.total_nulls = attr.get("total_nulls", 0)
    total_cells = result.feature_count * result.column_count
    result.null_pct = round(
        (result.total_nulls / total_cells * 100) if total_cells > 0 else 0, 1
    )

    # Topology checks (only for polygons and small-ish datasets)
    try:
        topo = TopologyChecker(profile.gdf)
        topo_results = topo.check_all(max_features=15000)
        result.sliver_count = topo_results.get("sliver_count", 0)
        result.bad_ring_count = topo_results.get("bad_ring_count", 0)
        overlap_count = topo_results.get("self_overlap_count", 0)
        result.overlap_count = max(0, overlap_count)  # -1 means skipped
    except Exception:
        pass

    # Determine blockers and warnings
    if result.crs is None:
        result.blockers.append("No CRS defined — OVC requires georeferenced data")

    if result.feature_count == 0:
        result.blockers.append("Dataset is empty (0 features)")

    if result.invalid_count > 0:
        pct = result.invalid_count / max(result.feature_count, 1) * 100
        if pct > 10:
            result.blockers.append(
                f"{result.invalid_count} invalid geometries ({pct:.1f}%) — "
                "fix with geoqa before running OVC"
            )
        else:
            result.warnings.append(
                f"{result.invalid_count} invalid geometries ({pct:.1f}%)"
            )

    if result.empty_count > 0:
        result.warnings.append(f"{result.empty_count} empty geometries")

    if result.null_geom_count > 0:
        result.warnings.append(f"{result.null_geom_count} null geometries")

    if result.duplicate_count > 0:
        result.warnings.append(f"{result.duplicate_count} duplicate geometries")

    if result.sliver_count > 0:
        result.warnings.append(f"{result.sliver_count} sliver polygons")

    if result.quality_score < 50:
        result.blockers.append(
            f"Quality score very low ({result.quality_score}/100) — data needs cleaning"
        )

    result.is_ready = not result.has_blockers

    # Generate report
    if generate_report and out_dir is not None:
        try:
            out_dir = Path(out_dir)
            report_path = out_dir / "precheck" / f"{dataset_name}_quality_report.html"
            profile.to_html(report_path)
            result.report_path = report_path
            log.info(f"[precheck] {dataset_name}: Quality report → {report_path}")
        except Exception as e:
            log.warning(f"[precheck] {dataset_name}: Report generation failed — {e}")

    return result


def precheck_buildings(
    buildings_path: Path,
    out_dir: Optional[Path] = None,
) -> PrecheckResult:
    """Pre-check a buildings dataset.

    Args:
        buildings_path: Path to the buildings file.
        out_dir: Output directory for HTML report.

    Returns:
        PrecheckResult for the buildings dataset.
    """
    log.info(f"[precheck] Checking buildings: {buildings_path}")
    result = _run_geoqa_profile(buildings_path, "buildings", out_dir)

    # Buildings-specific validation
    if result.geometry_type and "polygon" not in result.geometry_type.lower():
        result.blockers.append(
            f"Expected Polygon geometries for buildings, got {result.geometry_type}"
        )
        result.is_ready = not result.has_blockers

    _log_result(result)
    return result


def precheck_roads(
    roads_path: Path,
    out_dir: Optional[Path] = None,
) -> PrecheckResult:
    """Pre-check a roads dataset.

    Args:
        roads_path: Path to the roads file.
        out_dir: Output directory for HTML report.

    Returns:
        PrecheckResult for the roads dataset.
    """
    log.info(f"[precheck] Checking roads: {roads_path}")
    result = _run_geoqa_profile(roads_path, "roads", out_dir)

    # Roads-specific validation
    if result.geometry_type and "line" not in result.geometry_type.lower():
        result.blockers.append(
            f"Expected LineString geometries for roads, got {result.geometry_type}"
        )
        result.is_ready = not result.has_blockers

    _log_result(result)
    return result


def precheck_boundary(
    boundary_path: Path,
    out_dir: Optional[Path] = None,
) -> PrecheckResult:
    """Pre-check a boundary dataset.

    Args:
        boundary_path: Path to the boundary file.
        out_dir: Output directory for HTML report.

    Returns:
        PrecheckResult for the boundary dataset.
    """
    log.info(f"[precheck] Checking boundary: {boundary_path}")
    result = _run_geoqa_profile(boundary_path, "boundary", out_dir)

    if result.feature_count > 10:
        result.warnings.append(
            f"Boundary has {result.feature_count} features — expected 1 or few"
        )

    _log_result(result)
    return result


def precheck_all(
    buildings_path: Optional[Path] = None,
    roads_path: Optional[Path] = None,
    boundary_path: Optional[Path] = None,
    out_dir: Optional[Path] = None,
) -> PrecheckSummary:
    """Run pre-checks on all available input datasets.

    Args:
        buildings_path: Path to buildings file (optional).
        roads_path: Path to roads file (optional).
        boundary_path: Path to boundary file (optional).
        out_dir: Output directory for HTML reports.

    Returns:
        PrecheckSummary with results for each dataset.
    """
    summary = PrecheckSummary()

    if buildings_path is not None:
        summary.buildings = precheck_buildings(buildings_path, out_dir)

    if roads_path is not None:
        summary.roads = precheck_roads(roads_path, out_dir)

    if boundary_path is not None:
        summary.boundary = precheck_boundary(boundary_path, out_dir)

    # Overall readiness: no blockers across any checked dataset
    summary.overall_ready = all(r.is_ready for r in summary.all_results)

    # Print summary
    log.info("=" * 60)
    log.info("  OVC Pre-Check Summary")
    log.info("=" * 60)
    for r in summary.all_results:
        status = "✅ READY" if r.is_ready else "❌ NOT READY"
        log.info(
            f"  {r.dataset_name:12s} | {status} | "
            f"Score: {r.quality_score}/100 | "
            f"Features: {r.feature_count:,}"
        )
        for b in r.blockers:
            log.error(f"    BLOCKER: {b}")
        for w in r.warnings:
            log.warning(f"    WARNING: {w}")

    overall = "✅ ALL CLEAR" if summary.overall_ready else "❌ ISSUES FOUND"
    log.info(f"\n  Overall: {overall}")
    log.info("=" * 60)

    return summary


def _log_result(result: PrecheckResult) -> None:
    """Log a single precheck result."""
    status = "READY" if result.is_ready else "NOT READY"
    log.info(
        f"[precheck] {result.dataset_name}: {status} — "
        f"Score={result.quality_score}/100, "
        f"Features={result.feature_count:,}, "
        f"Invalid={result.invalid_count}, "
        f"Empty={result.empty_count}"
    )
