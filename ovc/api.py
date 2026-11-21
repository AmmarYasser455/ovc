"""File-level entry point shared by the map app, the CLI and Python users."""

from __future__ import annotations

from ovc.engine import check_polygons
from ovc.engine.model import STATUS_FAILED, ScanResult
from ovc.io.layers import LayerReadError, read_layer


def check_file(
    path,
    layer: str | None = None,
    *,
    coverage_path=None,
    coverage_layer: str | None = None,
    exclusions_path=None,
    exclusions_layer: str | None = None,
    progress=None,
    reader=read_layer,
    **options,
) -> ScanResult:
    """Read a polygon layer and run :func:`ovc.engine.check_polygons` on it.

    ``options`` are passed to ``check_polygons`` (``check_overlaps``,
    ``check_gaps``, ``id_field``, ``min_overlap_area_m2``, ``min_gap_area_m2``,
    ``duplicate_ratio``, ``repair_invalid``, ``assume_crs``). ``reader`` is
    the function used to load a layer, ``reader(path, layer)``; the map app
    passes a caching reader.

    A file that cannot be read gives a result with ``status == "failed"`` and
    the reason in ``message``. It never looks like a clean run. The input
    files are opened read-only.
    """

    def failed(message):
        return ScanResult(status=STATUS_FAILED, message=message, error=message)

    try:
        if progress is not None:
            progress("Reading layer", 0.0)
        features = reader(path, layer)
        coverage = exclusions = None
        if options.get("check_gaps") and coverage_path:
            coverage = reader(coverage_path, coverage_layer)
            if exclusions_path:
                exclusions = reader(exclusions_path, exclusions_layer)
    except LayerReadError as exc:
        return failed(str(exc))

    try:
        return check_polygons(
            features,
            coverage=coverage,
            exclusions=exclusions,
            progress=progress,
            **options,
        )
    except Exception as exc:  # a crash must surface as a failed run
        return failed(f"The check stopped with an error: {type(exc).__name__}: {exc}")
