"""Gap detection against an explicit coverage area.

A gap is a connected part of the expected coverage area that no input
polygon covers. The expected coverage area always comes from a polygon layer
supplied by the analyst. It is never inferred from a bounding box or hull.
"""

from __future__ import annotations

import numpy as np
import shapely
from shapely import STRtree

from ovc.engine.overlaps import polygonal_part


def expected_coverage(coverage_geoms, exclusion_geoms=None):
    """Union of the coverage polygons minus any exclusion polygons.

    Holes in the coverage polygons stay holes: they are not expected to be
    covered.
    """
    area = polygonal_part(shapely.union_all(np.asarray(coverage_geoms, dtype=object)))
    if area is None:
        return None
    if exclusion_geoms is not None and len(exclusion_geoms):
        excluded = shapely.union_all(np.asarray(exclusion_geoms, dtype=object))
        area = polygonal_part(shapely.difference(area, excluded))
    return area


def find_gaps(feature_geoms, coverage_area):
    """Connected uncovered parts of ``coverage_area``.

    Returns a list of ``(polygon, touches_boundary, neighbour_positions)``.
    ``touches_boundary`` is True when the gap reaches the edge of the
    coverage area. ``neighbour_positions`` are positions in ``feature_geoms``
    of the features bordering the gap.
    """
    feature_geoms = np.asarray(feature_geoms, dtype=object)
    if coverage_area is None or coverage_area.is_empty:
        return []

    tree = STRtree(feature_geoms) if len(feature_geoms) else None
    if tree is not None:
        near = tree.query(coverage_area, predicate="intersects")
        covered = shapely.union_all(feature_geoms[np.sort(near)])
        uncovered = polygonal_part(shapely.difference(coverage_area, covered))
    else:
        uncovered = coverage_area
    if uncovered is None:
        return []

    edge = coverage_area.boundary
    parts = uncovered.geoms if uncovered.geom_type == "MultiPolygon" else [uncovered]
    out = []
    for part in parts:
        if part.is_empty or part.area <= 0:
            continue
        neighbours = []
        if tree is not None:
            neighbours = sorted(
                int(k) for k in tree.query(part, predicate="intersects")
            )
        out.append((part, bool(part.intersects(edge)), neighbours))
    return out
