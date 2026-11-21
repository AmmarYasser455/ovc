"""Exact pairwise overlap detection on an array of polygon geometries.

Candidate pairs come from an STRtree; the decision is the area of the exact
polygonal intersection. Shared vertices and shared edges intersect in points
or lines, which have no area, so they are never overlaps.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import shapely
from shapely import STRtree
from shapely.geometry import MultiPolygon

_POLYGON, _MULTIPOLYGON, _COLLECTION = 3, 6, 7


def polygonal_part(geom):
    """All polygon parts of ``geom`` as a Polygon/MultiPolygon, or None."""
    if geom is None or geom.is_empty:
        return None
    type_id = shapely.get_type_id(geom)
    if type_id in (_POLYGON, _MULTIPOLYGON):
        return geom
    if type_id == _COLLECTION:
        polys = []
        for part in geom.geoms:
            p = polygonal_part(part)
            if p is None:
                continue
            polys.extend(p.geoms if p.geom_type == "MultiPolygon" else [p])
        if not polys:
            return None
        return polys[0] if len(polys) == 1 else MultiPolygon(polys)
    return None


@dataclass
class OverlapPair:
    i: int  # position of the first feature (i < j)
    j: int
    geometry: object  # polygonal intersection, every part kept
    area: float  # in CRS units squared
    area_i: float
    area_j: float


def candidate_pairs(geoms: np.ndarray):
    """Unordered pairs ``i < j`` whose geometries intersect (STRtree)."""
    tree = STRtree(geoms)
    left, right = tree.query(geoms, predicate="intersects")
    keep = left < right
    left, right = left[keep], right[keep]
    order = np.lexsort((right, left))
    return left[order], right[order]


def find_overlap_pairs(geoms, progress=None):
    """Positive-area intersections between distinct geometries.

    Parameters
    ----------
    geoms : sequence of valid, non-empty polygon geometries.

    Returns
    -------
    pairs : list[OverlapPair]
        One entry per unordered pair with a positive-area intersection.
    failures : list[tuple[int, int, str]]
        Pairs whose intersection could not be computed, with the error text.
        Callers must surface these: a failed pair is not a clean pair.
    """
    geoms = np.asarray(geoms, dtype=object)
    if len(geoms) < 2:
        return [], []

    left, right = candidate_pairs(geoms)
    if len(left) == 0:
        return [], []

    areas = shapely.area(geoms)
    failures: list[tuple[int, int, str]] = []
    try:
        inters = shapely.intersection(geoms[left], geoms[right])
    except shapely.errors.GEOSException:
        # One bad pair must not hide the others: retry pair by pair.
        inters = np.empty(len(left), dtype=object)
        for k in range(len(left)):
            try:
                inters[k] = shapely.intersection(geoms[left[k]], geoms[right[k]])
            except shapely.errors.GEOSException as exc:
                inters[k] = None
                failures.append((int(left[k]), int(right[k]), str(exc)))
            if progress is not None and k % 500 == 0:
                progress(k / len(left))

    pairs: list[OverlapPair] = []
    type_ids = shapely.get_type_id(inters)
    for k in np.flatnonzero(np.isin(type_ids, (_POLYGON, _MULTIPOLYGON, _COLLECTION))):
        inter = polygonal_part(inters[k])
        if inter is None:
            continue
        area = float(inter.area)
        if area <= 0:
            continue
        i, j = int(left[k]), int(right[k])
        pairs.append(OverlapPair(i, j, inter, area, float(areas[i]), float(areas[j])))
    return pairs, failures


def classify_overlap(area: float, area_a: float, area_b: float, duplicate_ratio: float):
    """Classify one overlap.

    Returns ``(issue_type, share_of_smaller)`` where issue_type is

    * ``duplicate``: the intersection covers at least ``duplicate_ratio`` of
      *both* features (identical or near-identical polygons);
    * ``containment``: it covers at least ``duplicate_ratio`` of the smaller
      feature only (one feature lies inside the other);
    * ``overlap``: anything else with positive area.
    """
    smaller, larger = min(area_a, area_b), max(area_a, area_b)
    share_small = area / smaller if smaller > 0 else 0.0
    share_large = area / larger if larger > 0 else 0.0
    if share_large >= duplicate_ratio:
        return "duplicate", share_small
    if share_small >= duplicate_ratio:
        return "containment", share_small
    return "overlap", share_small
