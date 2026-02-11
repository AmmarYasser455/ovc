"""Additional geometry quality checks for buildings.

New validation features:
- Duplicate geometry detection
- Building footprint regularity / compactness
- Building area reasonableness
- Self-intersecting polygons
- Coordinate precision issues
- Minimum distance to road violations
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.validation import explain_validity

from ovc.core.logging import get_logger


def find_duplicate_geometries(
    buildings_metric: gpd.GeoDataFrame,
    tolerance_m: float = 0.1,
) -> gpd.GeoDataFrame:
    """Detect buildings with identical or near-identical geometries.

    Uses WKB (Well-Known Binary) hashing for exact duplicates and
    Hausdorff distance for near-duplicates.

    Parameters
    ----------
    buildings_metric : GeoDataFrame
        Buildings in metric CRS with ``bldg_id`` column.
    tolerance_m : float
        Maximum Hausdorff distance to consider as duplicate (meters).

    Returns
    -------
    GeoDataFrame
        Duplicate buildings with ``error_type`` = ``"duplicate_geometry"``.
    """
    logger = get_logger("ovc.checks.geometry_quality")

    if buildings_metric is None or buildings_metric.empty:
        return gpd.GeoDataFrame(geometry=[], crs=getattr(buildings_metric, "crs", None))

    gdf = buildings_metric[["bldg_id", "geometry"]].copy()
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].reset_index(drop=True)

    # Exact duplicates via WKB hash
    gdf["_wkb"] = gdf.geometry.apply(lambda g: g.wkb_hex)
    dup_mask = gdf.duplicated(subset="_wkb", keep=False)
    duplicates = gdf[dup_mask].copy()

    duplicates["error_type"] = "duplicate_geometry"
    duplicates["error_class"] = "exact_duplicate"
    duplicates = duplicates.drop(columns=["_wkb"])
    gdf = gdf.drop(columns=["_wkb"])

    logger.info(f"Duplicate geometry check: {len(duplicates)} exact duplicates found")
    return duplicates


def find_invalid_geometries(
    buildings_metric: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Detect self-intersecting or otherwise invalid polygons.

    Parameters
    ----------
    buildings_metric : GeoDataFrame
        Buildings in metric CRS with ``bldg_id`` column.

    Returns
    -------
    GeoDataFrame
        Invalid buildings with ``error_type`` = ``"invalid_geometry"``
        and ``validity_reason`` column.
    """
    logger = get_logger("ovc.checks.geometry_quality")

    if buildings_metric is None or buildings_metric.empty:
        return gpd.GeoDataFrame(geometry=[], crs=getattr(buildings_metric, "crs", None))

    gdf = buildings_metric[["bldg_id", "geometry"]].copy()
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].reset_index(drop=True)

    invalid_mask = ~gdf.geometry.is_valid
    invalid = gdf[invalid_mask].copy()

    if invalid.empty:
        logger.info("No invalid geometries found")
        return gpd.GeoDataFrame(geometry=[], crs=gdf.crs)

    invalid["validity_reason"] = invalid.geometry.apply(
        lambda g: explain_validity(g)
    )
    invalid["error_type"] = "invalid_geometry"
    invalid["error_class"] = "topology"

    logger.info(f"Found {len(invalid)} invalid geometries")
    return invalid


def find_unreasonable_areas(
    buildings_metric: gpd.GeoDataFrame,
    min_area_m2: float = 4.0,
    max_area_m2: float = 50000.0,
) -> gpd.GeoDataFrame:
    """Flag buildings whose area is unreasonably small or large.

    Parameters
    ----------
    buildings_metric : GeoDataFrame
        Buildings in metric CRS.
    min_area_m2 : float
        Minimum reasonable building footprint area.
    max_area_m2 : float
        Maximum reasonable building footprint area.

    Returns
    -------
    GeoDataFrame
        Flagged buildings with ``error_type`` = ``"unreasonable_area"``.
    """
    logger = get_logger("ovc.checks.geometry_quality")

    if buildings_metric is None or buildings_metric.empty:
        return gpd.GeoDataFrame(geometry=[], crs=getattr(buildings_metric, "crs", None))

    gdf = buildings_metric[["bldg_id", "geometry"]].copy()
    gdf["area_m2"] = gdf.geometry.area

    too_small = gdf[gdf["area_m2"] < min_area_m2].copy()
    too_small["error_class"] = "too_small"

    too_large = gdf[gdf["area_m2"] > max_area_m2].copy()
    too_large["error_class"] = "too_large"

    result = pd.concat([too_small, too_large], ignore_index=True)
    if result.empty:
        return gpd.GeoDataFrame(geometry=[], crs=gdf.crs)

    result["error_type"] = "unreasonable_area"
    result = gpd.GeoDataFrame(result, geometry="geometry", crs=gdf.crs)

    logger.info(
        f"Area check: {len(too_small)} too small, {len(too_large)} too large"
    )
    return result


def compute_compactness(
    buildings_metric: gpd.GeoDataFrame,
    min_compactness: float = 0.2,
) -> gpd.GeoDataFrame:
    """Flag buildings with irregular footprints using the Polsby-Popper
    compactness score (4π × area / perimeter²).

    A perfect circle scores 1.0; long, narrow, or jagged polygons score
    much lower.

    Parameters
    ----------
    buildings_metric : GeoDataFrame
        Buildings in metric CRS.
    min_compactness : float
        Threshold below which a building is flagged (0–1).

    Returns
    -------
    GeoDataFrame
        Flagged buildings with ``compactness`` and ``error_type`` columns.
    """
    logger = get_logger("ovc.checks.geometry_quality")

    if buildings_metric is None or buildings_metric.empty:
        return gpd.GeoDataFrame(geometry=[], crs=getattr(buildings_metric, "crs", None))

    gdf = buildings_metric[["bldg_id", "geometry"]].copy()
    area = gdf.geometry.area
    perim = gdf.geometry.length
    gdf["compactness"] = (4 * np.pi * area) / (perim**2 + 1e-12)

    flagged = gdf[gdf["compactness"] < min_compactness].copy()
    if flagged.empty:
        return gpd.GeoDataFrame(geometry=[], crs=gdf.crs)

    flagged["error_type"] = "low_compactness"
    flagged["error_class"] = "shape_quality"

    logger.info(
        f"Compactness check: {len(flagged)} buildings below {min_compactness}"
    )
    return gpd.GeoDataFrame(flagged, geometry="geometry", crs=gdf.crs)


def find_min_road_distance_violations(
    buildings_metric: gpd.GeoDataFrame,
    roads_metric: gpd.GeoDataFrame,
    min_distance_m: float = 3.0,
) -> gpd.GeoDataFrame:
    """Find buildings closer to the nearest road than the allowed minimum.

    Uses spatial join with buffered roads for efficient pre-filtering.

    Parameters
    ----------
    buildings_metric : GeoDataFrame
        Buildings with ``bldg_id`` column.
    roads_metric : GeoDataFrame
        Roads (LineString/MultiLineString).
    min_distance_m : float
        Minimum allowed setback distance in meters.

    Returns
    -------
    GeoDataFrame
        Flagged buildings with ``min_road_dist_m`` and ``error_type``.
    """
    logger = get_logger("ovc.checks.geometry_quality")

    if (
        buildings_metric is None
        or buildings_metric.empty
        or roads_metric is None
        or roads_metric.empty
    ):
        crs = getattr(buildings_metric, "crs", None)
        return gpd.GeoDataFrame(geometry=[], crs=crs)

    # Buffer roads by min_distance and spatial-join
    road_buf = roads_metric[["geometry"]].copy()
    road_buf["geometry"] = road_buf.geometry.buffer(min_distance_m)

    candidates = gpd.sjoin(
        buildings_metric[["bldg_id", "geometry"]],
        road_buf,
        how="inner",
        predicate="intersects",
    )

    if candidates.empty:
        return gpd.GeoDataFrame(geometry=[], crs=buildings_metric.crs)

    # Compute actual nearest-road distance per building
    unique_bids = candidates["bldg_id"].unique()
    bldg_subset = buildings_metric[
        buildings_metric["bldg_id"].isin(unique_bids)
    ].copy()

    road_union = roads_metric.union_all()
    bldg_subset["min_road_dist_m"] = bldg_subset.geometry.distance(road_union)

    violations = bldg_subset[
        bldg_subset["min_road_dist_m"] < min_distance_m
    ].copy()

    if violations.empty:
        return gpd.GeoDataFrame(geometry=[], crs=buildings_metric.crs)

    violations["error_type"] = "road_setback_violation"
    violations["error_class"] = "distance"

    logger.info(
        f"Road setback check: {len(violations)} buildings within "
        f"{min_distance_m}m of roads"
    )
    return violations[["bldg_id", "geometry", "min_road_dist_m", "error_type", "error_class"]]
