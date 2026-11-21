from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from ovc.core.logging import get_logger
from ovc.engine.overlaps import classify_overlap, find_overlap_pairs, polygonal_part


@dataclass(frozen=True, init=False)
class OverlapThresholds:
    min_intersection_area_m2: float
    duplicate_ratio_min: float
    partial_ratio_min: float

    def __init__(
        self,
        min_intersection_area_m2: float = 1.0,
        duplicate_ratio_min: float | None = None,
        duplicate_min_ratio: float | None = None,
        partial_ratio_min: float = 0.5,
    ):
        object.__setattr__(self, "min_intersection_area_m2", min_intersection_area_m2)

        if duplicate_ratio_min is not None:
            object.__setattr__(self, "duplicate_ratio_min", duplicate_ratio_min)
        elif duplicate_min_ratio is not None:
            object.__setattr__(self, "duplicate_ratio_min", duplicate_min_ratio)
        else:
            object.__setattr__(self, "duplicate_ratio_min", 0.9)

        object.__setattr__(self, "partial_ratio_min", partial_ratio_min)


# Kept for callers that imported the old private helper.
_keep_polygonal = polygonal_part


def find_building_overlaps(
    buildings_metric: gpd.GeoDataFrame,
    thresholds: OverlapThresholds,
) -> gpd.GeoDataFrame:
    """Detect pairwise building overlaps.

    This is a thin wrapper around the shared topology engine
    (:mod:`ovc.engine.overlaps`): an STRtree selects candidate pairs and the
    exact polygonal intersection decides. Each unordered pair is reported
    once, with the area of *every* part of its intersection. Shared edges and
    shared vertices are not overlaps.

    Invalid polygons are repaired in memory (``make_valid``) with a logged
    warning, so they cannot silently drop out of the comparison.

    Parameters
    ----------
    buildings_metric : GeoDataFrame
        Buildings in a metric CRS with ``bldg_id`` column.
    thresholds : OverlapThresholds
        ``min_intersection_area_m2``: overlaps with at least this area are
        reported (an area equal to the threshold is reported).
        ``duplicate_ratio_min`` and ``partial_ratio_min`` set the classes.

    Returns
    -------
    GeoDataFrame
        Overlap geometries with ``bldg_a``, ``bldg_b``, ``inter_area_m2``,
        ``overlap_ratio`` (share of the smaller building), ``overlap_type``
        and ``error_type`` columns. ``overlap_type`` is one of

        * ``duplicate``: the overlap covers ``duplicate_ratio_min`` of both
          buildings;
        * ``contained``: it covers ``duplicate_ratio_min`` of the smaller
          building only (a building inside another);
        * ``partial``: it covers at least ``partial_ratio_min`` of the
          smaller building;
        * ``sliver``: anything smaller.
    """
    logger = get_logger("ovc.checks.overlap")

    if buildings_metric is None or buildings_metric.empty:
        return gpd.GeoDataFrame(geometry=[], crs=getattr(buildings_metric, "crs", None))

    gdf = buildings_metric[["bldg_id", "geometry"]].copy().reset_index(drop=True)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].reset_index(drop=True)
    crs = gdf.crs

    geoms = np.asarray(gdf.geometry.values, dtype=object)
    if len(geoms):
        invalid = ~shapely.is_valid(geoms)
        if invalid.any():
            logger.warning(
                f"{int(invalid.sum())} invalid building geometries were repaired "
                "in memory before overlap detection (bldg_id: "
                f"{gdf['bldg_id'].values[invalid][:10].tolist()})"
            )
            geoms[invalid] = shapely.make_valid(geoms[invalid])
    polys = [polygonal_part(g) for g in geoms]
    keep = np.array([p is not None and p.area > 0 for p in polys], dtype=bool)
    if (~keep).any():
        logger.warning(
            f"{int((~keep).sum())} buildings without polygon area were left "
            "out of overlap detection"
        )
    geoms = np.asarray([p for p, k in zip(polys, keep) if k], dtype=object)
    bldg_ids = gdf["bldg_id"].values[keep]

    if len(geoms) < 2:
        return gpd.GeoDataFrame(geometry=[], crs=crs)

    logger.info(f"Overlap detection: {len(geoms)} buildings")
    pairs, failures = find_overlap_pairs(geoms)
    if failures:
        i, j, err = failures[0]
        raise RuntimeError(
            f"Overlap detection failed for {len(failures)} building pair(s), "
            f"first: bldg_id {bldg_ids[i]} and {bldg_ids[j]} ({err})"
        )

    rows = []
    for p in pairs:
        if p.area < thresholds.min_intersection_area_m2:
            continue
        issue, ratio = classify_overlap(
            p.area, p.area_i, p.area_j, thresholds.duplicate_ratio_min
        )
        if issue == "duplicate":
            overlap_type = "duplicate"
        elif issue == "containment":
            overlap_type = "contained"
        elif ratio >= thresholds.partial_ratio_min:
            overlap_type = "partial"
        else:
            overlap_type = "sliver"
        rows.append(
            {
                "bldg_a": int(bldg_ids[p.i]),
                "bldg_b": int(bldg_ids[p.j]),
                "inter_area_m2": float(p.area),
                "overlap_ratio": float(ratio),
                "overlap_type": overlap_type,
                "error_type": "building_overlap",
                "geometry": p.geometry,
            }
        )

    if not rows:
        return gpd.GeoDataFrame(geometry=[], crs=crs)

    logger.info(f"Found {len(rows)} overlaps")
    return gpd.GeoDataFrame(pd.DataFrame(rows), geometry="geometry", crs=crs)
