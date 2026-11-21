"""Run the topology checks on a polygon layer and build a :class:`ScanResult`.

This module is the single validation engine behind the map app, the
``ovc check`` command and :func:`ovc.check_file`. It does no file I/O and
never modifies its inputs.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import MultiPolygon
from shapely.validation import explain_validity

from ovc.engine.gaps import expected_coverage, find_gaps
from ovc.engine.measure import choose_measurement
from ovc.engine.model import (
    CHECK_COMPLETE,
    CHECK_INCOMPLETE,
    CHECK_NOT_RUN,
    FINDING_COLUMNS,
    STATUS_CLEAN,
    STATUS_FAILED,
    STATUS_ISSUES,
    STATUS_PARTIAL,
    CheckOutcome,
    ScanResult,
    crs_label,
    empty_findings,
)
from ovc.engine.overlaps import classify_overlap, find_overlap_pairs, polygonal_part

DEFAULT_MIN_AREA_M2 = 0.01
DEFAULT_DUPLICATE_RATIO = 0.98

GAP_NEEDS_COVERAGE = (
    "Gap check not run: it needs a polygon layer of the area that should be "
    "fully covered (for example a parcel block). OVC never guesses that area "
    "from a bounding box or hull."
)


def _failed(message: str, feature_count: int = 0, options=None) -> ScanResult:
    return ScanResult(
        status=STATUS_FAILED,
        message=message,
        error=message,
        feature_count=feature_count,
        options=options or {},
    )


def _as_multi(geom):
    if geom is None:
        return None
    return MultiPolygon([geom]) if geom.geom_type == "Polygon" else geom


def _label(fid, id_value) -> str:
    return f"FID {fid}" if id_value is None else f"FID {fid} (ID {id_value})"


def _fmt_area(area_m2: float) -> str:
    if area_m2 >= 100:
        return f"{area_m2:,.1f} m²"
    if area_m2 >= 0.01:
        return f"{area_m2:,.2f} m²"
    return f"{area_m2:.3g} m²"


def _feature_ids(features: gpd.GeoDataFrame, id_field):
    """Return (fids, id values or None per feature, warnings)."""
    warnings = []
    index = features.index
    if pd.api.types.is_integer_dtype(index) and index.is_unique:
        fids = index.to_numpy()
    else:
        fids = np.arange(len(features))
        warnings.append(
            "Feature index is not a unique integer; features are identified "
            "by their row position (0-based)."
        )
    ids = [None] * len(features)
    if id_field:
        raw = features[id_field]
        missing = raw.isna() | (raw.astype(str).str.strip() == "")
        ids = [None if m else str(v) for v, m in zip(raw.tolist(), missing.tolist())]
        n_missing = int(missing.sum())
        present = pd.Series([v for v in ids if v is not None], dtype="object")
        n_repeated = int(present.duplicated(keep=False).sum())
        if n_missing:
            warnings.append(
                f"ID field '{id_field}': {n_missing} feature(s) have no value. "
                "They are identified by FID only."
            )
        if n_repeated:
            warnings.append(
                f"ID field '{id_field}': {n_repeated} feature(s) share a value "
                "with another feature. Use the FID to tell them apart."
            )
    return fids, ids, warnings


def _polygons_in_working_crs(layer, working_crs, repair, what):
    """Polygon geometries of an auxiliary layer, or (None, reason)."""
    if layer is None:
        return None, None
    if layer.crs is None:
        return None, (
            f"the {what} layer has no CRS. Define its CRS in the file, then run again"
        )
    geoms = [polygonal_part(g) for g in layer.geometry.values]
    geoms = [g for g in geoms if g is not None]
    if not geoms:
        return None, f"the {what} layer contains no polygons"
    arr = np.asarray(geoms, dtype=object)
    invalid = ~shapely.is_valid(arr)
    if invalid.any():
        if not repair:
            return None, (
                f"the {what} layer has {int(invalid.sum())} invalid polygon(s). "
                "Fix them, or turn on 'Repair invalid geometries in memory'"
            )
        fixed = [polygonal_part(shapely.make_valid(g)) for g in arr[invalid]]
        arr = np.asarray(
            list(arr[~invalid]) + [g for g in fixed if g is not None], dtype=object
        )
    series = gpd.GeoSeries(arr, crs=layer.crs)
    if series.crs != working_crs:
        series = series.to_crs(working_crs)
    return np.asarray(series.values, dtype=object), None


def check_polygons(
    features: gpd.GeoDataFrame,
    *,
    check_overlaps: bool = True,
    check_gaps: bool = False,
    coverage: gpd.GeoDataFrame | None = None,
    exclusions: gpd.GeoDataFrame | None = None,
    id_field: str | None = None,
    min_overlap_area_m2: float = DEFAULT_MIN_AREA_M2,
    min_gap_area_m2: float = DEFAULT_MIN_AREA_M2,
    duplicate_ratio: float = DEFAULT_DUPLICATE_RATIO,
    repair_invalid: bool = False,
    assume_crs=None,
    progress=None,
) -> ScanResult:
    """Check a polygon layer for overlaps and, optionally, gaps.

    Parameters
    ----------
    features : GeoDataFrame
        The polygon layer. Its index is used as the feature ID (FID) when it
        is a unique integer index, otherwise the row position is used.
    check_overlaps : bool
        Report every unordered pair of distinct features whose intersection
        has positive area. Needs no other input.
    check_gaps : bool
        Report every connected part of ``coverage`` that no feature covers.
        Off by default: building footprints normally have open space between
        them. Needs ``coverage``.
    coverage : GeoDataFrame, optional
        Polygons of the area that should be fully covered. Holes in these
        polygons are not expected to be covered.
    exclusions : GeoDataFrame, optional
        Polygons to subtract from the coverage area (courtyards, streets).
    id_field : str, optional
        Attribute holding the analyst's own feature ID, reported with the FID.
    min_overlap_area_m2, min_gap_area_m2 : float
        Smallest area, in square metres, that is reported. A finding whose
        area equals the threshold is reported. ``0`` reports every
        positive-area finding.
    duplicate_ratio : float
        Share (0-1) of a feature that must be covered for the pair to be
        classed as ``containment`` (smaller feature) or ``duplicate`` (both).
    repair_invalid : bool
        If True, invalid polygons are repaired with ``make_valid`` in memory
        and then checked. If False they are reported and skipped. The source
        data is never modified either way.
    assume_crs : optional
        CRS to use when ``features`` has none. Without it, a layer with no
        CRS fails: OVC never guesses a CRS.
    progress : callable, optional
        ``progress(stage: str, fraction: float)``.

    Returns
    -------
    ScanResult
        ``status`` is ``clean``, ``issues``, ``partial`` or ``failed``.
        Data problems never raise and never produce a false ``clean``.
    """

    def tick(stage, fraction):
        if progress is not None:
            progress(stage, float(fraction))

    options = {
        "check_overlaps": bool(check_overlaps),
        "check_gaps": bool(check_gaps),
        "id_field": id_field,
        "min_overlap_area_m2": float(min_overlap_area_m2),
        "min_gap_area_m2": float(min_gap_area_m2),
        "duplicate_ratio": float(duplicate_ratio),
        "repair_invalid": bool(repair_invalid),
    }

    # ---- input validation ------------------------------------------------
    if not isinstance(features, gpd.GeoDataFrame):
        return _failed("The input is not a spatial layer.", options=options)
    n_total = len(features)
    if not check_overlaps and not check_gaps:
        return _failed(
            "No check selected. Choose overlaps, gaps or both.", n_total, options
        )
    if min_overlap_area_m2 < 0 or min_gap_area_m2 < 0:
        return _failed("Area thresholds cannot be negative.", n_total, options)
    if not 0 < duplicate_ratio <= 1:
        return _failed(
            "The duplicate ratio must be above 0 and at most 1.", n_total, options
        )
    if n_total == 0:
        return _failed(
            "The layer has no features, so there is nothing to check.", 0, options
        )
    if id_field and id_field not in features.columns:
        return _failed(
            f"ID field '{id_field}' does not exist in the layer.", n_total, options
        )

    warnings: list[str] = []
    source_crs = features.crs
    if source_crs is None:
        if assume_crs is None:
            return _failed(
                "The layer has no CRS, so areas cannot be measured. Define the "
                "CRS in the source file, or declare the CRS the coordinates "
                "are in. OVC never guesses a CRS.",
                n_total,
                options,
            )
        try:
            source_crs = gpd.GeoSeries([], crs=assume_crs).crs
        except Exception as exc:
            return _failed(f"The declared CRS is not valid: {exc}", n_total, options)
        warnings.append(
            f"The layer has no CRS. {crs_label(source_crs)} was declared for "
            "this run; the source file is unchanged."
        )
        options["assume_crs"] = crs_label(source_crs)

    tick("Checking input features", 0.02)
    fids, ids, id_warnings = _feature_ids(features, id_field)
    warnings.extend(id_warnings)

    # ---- classify every feature (in source coordinates) -----------------
    raw = np.asarray(features.geometry.values, dtype=object)
    rows: list[dict] = []
    skipped: list[dict] = []
    usable_pos: list[int] = []
    usable_geoms: list = []
    invalid_skipped = 0

    def finding(issue_type, check, geometry, reason, **kw):
        row = dict.fromkeys(FINDING_COLUMNS)
        row.update(check=check, issue_type=issue_type, reason=reason, **kw)
        row["geometry"] = geometry
        rows.append(row)

    def skip(pos, problem, effect):
        skipped.append(
            {
                "fid": int(fids[pos]),
                "id": ids[pos],
                "problem": problem,
                "effect": effect,
            }
        )

    input_rows_source_crs: list[int] = []  # rows whose geometry is in source CRS
    for pos, geom in enumerate(raw):
        label = _label(fids[pos], ids[pos])
        if geom is None or geom.is_empty:
            reason = f"{label} has no geometry. It covers nothing and was not checked."
            finding(
                "empty_geometry", "input", None, reason, fid_a=fids[pos], id_a=ids[pos]
            )
            skip(pos, "empty geometry", "Not checked. It covers no area.")
            continue
        poly = polygonal_part(geom)
        if poly is None:
            reason = (
                f"{label} is a {geom.geom_type}, not a polygon. It covers no "
                "area and was not checked."
            )
            finding(
                "not_polygon", "input", None, reason, fid_a=fids[pos], id_a=ids[pos]
            )
            skip(
                pos,
                f"not a polygon ({geom.geom_type})",
                "Not checked. It covers no area.",
            )
            continue
        if not poly.is_valid:
            why = explain_validity(poly)
            repaired = (
                polygonal_part(shapely.make_valid(poly)) if repair_invalid else None
            )
            if repaired is not None and repaired.area > 0:
                reason = (
                    f"{label} is invalid: {why}. Repaired in memory for this "
                    "run and checked; the source file is unchanged."
                )
                usable_pos.append(pos)
                usable_geoms.append(repaired)
            else:
                invalid_skipped += 1
                reason = (
                    f"{label} is invalid: {why}. Skipped: it was not checked "
                    "for overlaps, and the area it covers is unknown."
                )
                skip(
                    pos,
                    f"invalid geometry ({why})",
                    "Not checked for overlaps. Gap results near it are unreliable.",
                )
            input_rows_source_crs.append(len(rows))
            finding(
                "invalid_geometry",
                "input",
                _as_multi(poly),
                reason,
                fid_a=fids[pos],
                id_a=ids[pos],
            )
            continue
        if poly.area <= 0:
            reason = f"{label} has zero area. It covers nothing and was not checked."
            finding(
                "empty_geometry", "input", None, reason, fid_a=fids[pos], id_a=ids[pos]
            )
            skip(pos, "zero-area polygon", "Not checked. It covers no area.")
            continue
        usable_pos.append(pos)
        usable_geoms.append(poly)

    # ---- working CRS -----------------------------------------------------
    located = [g for g in raw if g is not None and not g.is_empty]
    if not located:
        result = _failed(
            "No feature in the layer has a geometry, so there is nothing to check.",
            n_total,
            options,
        )
        result.skipped = skipped
        return result
    bounds = shapely.total_bounds(np.asarray(located, dtype=object))
    try:
        measurement = choose_measurement(source_crs, bounds)
    except Exception as exc:
        return _failed(f"Could not set up area measurement: {exc}", n_total, options)
    working_crs = measurement.working_crs
    if (
        measurement.reprojected
        and (bounds[2] - bounds[0]) > 6
        and source_crs.is_geographic
    ):
        warnings.append(
            "The layer spans more than one UTM zone (over 6° of longitude). "
            "Areas far from its centre are less accurate; check smaller regions "
            "for precise areas."
        )

    def to_working(geoms):
        if not len(geoms):
            return np.asarray([], dtype=object)
        series = gpd.GeoSeries(np.asarray(geoms, dtype=object), crs=source_crs)
        if measurement.reprojected:
            series = series.to_crs(working_crs)
        return np.asarray(series.values, dtype=object)

    geoms = to_working(usable_geoms)
    if measurement.reprojected and len(geoms):
        bad = ~shapely.is_valid(geoms)
        if bad.any():
            geoms[bad] = [polygonal_part(shapely.make_valid(g)) for g in geoms[bad]]
            warnings.append(
                f"{int(bad.sum())} feature(s) became invalid when reprojected "
                "and were repaired in memory."
            )
    if input_rows_source_crs and measurement.reprojected:
        moved = to_working([rows[k]["geometry"] for k in input_rows_source_crs])
        for k, g in zip(input_rows_source_crs, moved):
            rows[k]["geometry"] = g

    usable_fids = fids[usable_pos] if usable_pos else np.asarray([], dtype=fids.dtype)
    usable_ids = [ids[p] for p in usable_pos]
    checks = {
        "overlap": CheckOutcome("overlap", requested=bool(check_overlaps)),
        "gap": CheckOutcome("gap", requested=bool(check_gaps)),
    }
    if not check_overlaps:
        checks["overlap"].message = "Not requested."
    if not check_gaps:
        checks["gap"].message = (
            "Not requested. Open space between features is not reported."
        )

    # ---- overlaps ----------------------------------------------------------
    if check_overlaps:
        tick("Finding overlaps", 0.15)
        try:
            pairs, failures = find_overlap_pairs(
                geoms, progress=lambda f: tick("Finding overlaps", 0.15 + 0.45 * f)
            )
        except Exception as exc:
            result = _failed(f"The overlap check failed: {exc}", n_total, options)
            result.skipped = skipped
            return result
        n_over = 0
        for p in pairs:
            area_m2 = measurement.area_m2(p.area)
            if area_m2 < min_overlap_area_m2:
                continue
            issue, share = classify_overlap(p.area, p.area_i, p.area_j, duplicate_ratio)
            la = _label(usable_fids[p.i], usable_ids[p.i])
            lb = _label(usable_fids[p.j], usable_ids[p.j])
            if issue == "duplicate":
                reason = (
                    f"{la} and {lb} cover the same area ({_fmt_area(area_m2)} "
                    "in common): identical or near-identical polygons."
                )
            elif issue == "containment":
                inner, outer = (la, lb) if p.area_i <= p.area_j else (lb, la)
                reason = (
                    f"{inner} lies inside {outer}: {share * 100:.0f}% of it "
                    f"({_fmt_area(area_m2)}) is covered."
                )
            else:
                reason = (
                    f"{la} and {lb} overlap by {_fmt_area(area_m2)}, "
                    f"{share * 100:.1f}% of the smaller feature."
                )
            finding(
                issue,
                "overlap",
                _as_multi(p.geometry),
                reason,
                fid_a=usable_fids[p.i],
                fid_b=usable_fids[p.j],
                id_a=usable_ids[p.i],
                id_b=usable_ids[p.j],
                area_m2=area_m2,
                overlap_ratio=share,
            )
            n_over += 1
        out = checks["overlap"]
        out.count = n_over
        out.status = CHECK_COMPLETE
        out.message = f"{len(geoms)} of {n_total} features compared."
        problems = []
        if failures:
            for i, j, err in failures:
                la = _label(usable_fids[i], usable_ids[i])
                lb = _label(usable_fids[j], usable_ids[j])
                skipped.append(
                    {
                        "fid": int(usable_fids[i]),
                        "id": usable_ids[i],
                        "problem": f"intersection with {lb} failed ({err})",
                        "effect": f"{la} and {lb} were not compared.",
                    }
                )
            problems.append(f"{len(failures)} pair(s) could not be compared")
        if invalid_skipped:
            problems.append(f"{invalid_skipped} invalid feature(s) were skipped")
        if problems:
            out.status = CHECK_INCOMPLETE
            out.message = (
                f"Incomplete: {' and '.join(problems)}. "
                f"{len(geoms)} of {n_total} features compared."
            )

    # ---- gaps ---------------------------------------------------------------
    if check_gaps:
        tick("Finding gaps", 0.65)
        out = checks["gap"]
        if coverage is None:
            out.message = GAP_NEEDS_COVERAGE
        else:
            try:
                cov, why_not = _polygons_in_working_crs(
                    coverage, working_crs, repair_invalid, "coverage"
                )
                exc_geoms, why_not_exc = _polygons_in_working_crs(
                    exclusions, working_crs, repair_invalid, "exclusion"
                )
                why_not = why_not or why_not_exc
                if why_not:
                    out.message = f"Gap check not run: {why_not}."
                else:
                    area = expected_coverage(cov, exc_geoms)
                    if area is None:
                        out.message = (
                            "Gap check not run: the exclusions remove the whole "
                            "coverage area."
                        )
                    else:
                        gaps = find_gaps(geoms, area)
                        tick("Finding gaps", 0.9)
                        n_gap = 0
                        for part, touches, neighbours in gaps:
                            area_m2 = measurement.area_m2(part.area)
                            if area_m2 < min_gap_area_m2:
                                continue
                            where = (
                                "It touches the edge of the coverage area."
                                if touches
                                else "It is enclosed by features."
                            )
                            near = [int(usable_fids[k]) for k in neighbours]
                            finding(
                                "gap",
                                "gap",
                                _as_multi(part),
                                f"{_fmt_area(area_m2)} of the coverage area is "
                                f"not covered by any feature. {where}",
                                area_m2=area_m2,
                                related_fids=", ".join(str(f) for f in near[:25]),
                            )
                            n_gap += 1
                        out.count = n_gap
                        out.status = CHECK_COMPLETE
                        out.message = "Coverage area fully compared."
                        if len(geoms) and not shapely.intersects(
                            area, shapely.union_all(shapely.envelope(geoms))
                        ):
                            warnings.append(
                                "No feature lies in the coverage area. Check that "
                                "both layers are in the right place and CRS."
                            )
                        if invalid_skipped:
                            out.status = CHECK_INCOMPLETE
                            out.message = (
                                f"Incomplete: {invalid_skipped} invalid feature(s) "
                                "were skipped and the area they cover is unknown, "
                                "so gaps near them may be false. Fix them or turn "
                                "on 'Repair invalid geometries in memory'."
                            )
            except Exception as exc:
                out.status = CHECK_NOT_RUN
                out.count = 0
                out.message = f"Gap check failed: {exc}"
                rows[:] = [r for r in rows if r["check"] != "gap"]

    # ---- assemble -----------------------------------------------------------
    tick("Preparing results", 0.95)
    order = {"overlap": 0, "gap": 1, "input": 2}
    rows.sort(key=lambda r: (order[r["check"]], -(r["area_m2"] or 0.0)))
    for n, r in enumerate(rows, start=1):
        r["finding_id"] = n
    if rows:
        df = pd.DataFrame(rows)
        findings = gpd.GeoDataFrame(
            df[FINDING_COLUMNS],
            geometry=gpd.GeoSeries(df["geometry"].tolist(), crs=working_crs),
            crs=working_crs,
        )
        for col in ("fid_a", "fid_b"):
            findings[col] = pd.array(findings[col].tolist(), dtype="Int64")
        for col in ("area_m2", "overlap_ratio"):
            findings[col] = pd.to_numeric(findings[col], errors="coerce")
    else:
        findings = empty_findings(working_crs)

    requested = [c for c in checks.values() if c.requested]
    incomplete = [c for c in requested if c.status != CHECK_COMPLETE]
    n_find = len(findings)
    if incomplete or skipped:
        status = STATUS_PARTIAL
        parts = []
        if skipped:
            parts.append(f"{len(skipped)} feature(s) skipped")
        parts.extend(
            f"{c.name} check {'not run' if c.status == CHECK_NOT_RUN else 'incomplete'}"
            for c in incomplete
        )
        message = (
            f"Partial run: {', '.join(parts)}. {n_find} finding(s) so far; "
            "this is not a clean result."
        )
    elif n_find:
        status = STATUS_ISSUES
        message = f"Complete: {n_find} finding(s) in {n_total} features."
    else:
        status = STATUS_CLEAN
        names = " and ".join(c.name for c in requested)
        message = f"Clean: no {names} issues in {n_total} features."

    tick("Done", 1.0)
    return ScanResult(
        status=status,
        message=message,
        findings=findings,
        checks=checks,
        feature_count=n_total,
        checked_count=len(geoms),
        skipped=skipped,
        warnings=warnings,
        measurement=measurement,
        options=options,
    )
