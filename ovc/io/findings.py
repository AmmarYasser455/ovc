"""Export findings to a GIS-readable file with a declared CRS."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio

from ovc.engine.model import FINDING_COLUMNS, ScanResult, crs_label

logging.getLogger("pyogrio").setLevel(logging.WARNING)

FINDINGS_LAYER = "ovc_findings"
SUMMARY_LAYER = "ovc_run_summary"
EXPORT_DRIVERS = {".gpkg": "GPKG", ".geojson": "GeoJSON"}


class ExportError(Exception):
    """The export was refused or failed. The message is safe to show."""


def _same_file(a, b) -> bool:
    try:
        a, b = Path(a), Path(b)
        if a.exists() and b.exists():
            return a.samefile(b)
        return a.resolve() == b.resolve()
    except OSError:
        return False


def export_findings(
    result: ScanResult,
    path,
    *,
    issue_types=None,
    crs=None,
    overwrite: bool = False,
    protect=(),
    source: str = "",
) -> dict:
    """Write findings to ``path`` (``.gpkg`` or ``.geojson``).

    Parameters
    ----------
    result : ScanResult
    path : output file. GeoPackage gets an ``ovc_findings`` layer plus an
        ``ovc_run_summary`` table. GeoJSON is written in EPSG:4326.
    issue_types : iterable of str, optional
        Export only these issue types. Default: all findings.
    crs : optional
        CRS of the exported geometries. Default: the source layer's CRS, so
        the findings line up with the data in a GIS. ``area_m2`` is always
        the area measured during the run, in square metres.
    overwrite : bool
        Replace ``path`` if it exists. Without it an existing file is refused.
    protect : iterable of paths
        Input files that must never be written to.
    source : str
        Description of the checked layer, stored in the run summary.

    Returns
    -------
    dict with ``path``, ``layer``, ``count`` and ``crs``.
    """
    if result is None or result.status == "failed" or result.findings is None:
        raise ExportError("There is no completed run to export.")
    path = Path(path)
    driver = EXPORT_DRIVERS.get(path.suffix.lower())
    if driver is None:
        raise ExportError("Choose a file name ending in .gpkg or .geojson.")
    for src in protect:
        if src and _same_file(path, src):
            raise ExportError(
                "That is one of the input files. OVC never writes to its "
                "inputs; choose another file name."
            )
    if path.exists() and not overwrite:
        raise ExportError(f"{path.name} already exists.")
    if not path.parent.is_dir():
        raise ExportError(f"Folder not found: {path.parent}")

    measurement = result.measurement
    if driver == "GeoJSON":
        out_crs = "EPSG:4326"
    else:
        out_crs = crs or (measurement.source_crs if measurement else None)
    findings = result.findings_in(out_crs)
    if issue_types is not None:
        findings = findings[findings["issue_type"].isin(list(issue_types))]
    findings = findings[FINDING_COLUMNS + ["geometry"]].copy()
    findings["area_crs"] = crs_label(measurement.working_crs) if measurement else ""
    for col in ("id_a", "id_b", "related_fids", "reason", "check", "issue_type"):
        findings[col] = findings[col].astype("string")
    findings["finding_id"] = findings["finding_id"].astype("int64")

    tmp = path.with_name(f".{path.stem}.ovc-tmp{path.suffix}")
    try:
        if tmp.exists():
            tmp.unlink()
        pyogrio.write_dataframe(
            findings,
            tmp,
            layer=FINDINGS_LAYER,
            driver=driver,
            geometry_type="MultiPolygon",
        )
        if driver == "GPKG":
            pyogrio.write_dataframe(
                _run_summary(result, source, issue_types, findings),
                tmp,
                layer=SUMMARY_LAYER,
                driver=driver,
                append=True,
            )
        tmp.replace(path)
    except Exception as exc:
        if tmp.exists():
            tmp.unlink()
        raise ExportError(f"Could not write {path.name}: {exc}") from exc

    return {
        "path": str(path),
        "layer": FINDINGS_LAYER,
        "count": int(len(findings)),
        "crs": crs_label(findings.crs),
    }


def _run_summary(result, source, issue_types, findings) -> pd.DataFrame:
    from ovc import __version__

    s = result.summary()
    rows = [
        ("ovc_version", __version__),
        ("exported_utc", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")),
        ("source", source),
        ("status", s["status"]),
        ("message", s["message"]),
        ("features_in_layer", s["feature_count"]),
        ("features_checked", s["checked_count"]),
        ("features_skipped", s["skipped_count"]),
        ("findings_in_run", s["finding_count"]),
        ("findings_exported", len(findings)),
        ("issue_type_filter", "all" if issue_types is None else ", ".join(issue_types)),
        ("area_unit", "square metres"),
        ("area_method", s["area_method"]),
        ("export_crs", crs_label(findings.crs)),
    ]
    rows += [
        (f"check_{k}", f"{v['status']}: {v['message']}") for k, v in s["checks"].items()
    ]
    rows += [(f"option_{k}", v) for k, v in s["options"].items()]
    rows += [(f"warning_{n}", w) for n, w in enumerate(s["warnings"], 1)]
    rows += [
        (f"skipped_{n}", f"FID {k['fid']}: {k['problem']}. {k['effect']}")
        for n, k in enumerate(s["skipped"], 1)
    ]
    return pd.DataFrame(
        {"item": [r[0] for r in rows], "value": [str(r[1]) for r in rows]}
    )
