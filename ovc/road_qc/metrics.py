from __future__ import annotations

import geopandas as gpd
import pandas as pd
from collections import Counter


def compute_road_qc_metrics(errors: gpd.GeoDataFrame) -> dict:
    """
    Compute error frequency metrics and identify top 3 most common errors.

    Parameters:
        errors: GeoDataFrame with error_type column

    Returns:
        dict with:
            - total_errors: total count of all errors
            - error_counts: dict mapping error_type to count
            - top_3_errors: list of (error_type, count) tuples, sorted by frequency
    """
    if errors is None or errors.empty or "error_type" not in errors.columns:
        return {
            "total_errors": 0,
            "error_counts": {},
            "top_3_errors": [],
        }

    error_counts = errors["error_type"].value_counts().to_dict()
    total_errors = int(sum(error_counts.values()))

    # Sort by count descending, take top 3
    sorted_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)
    top_3 = sorted_errors[:3]

    return {
        "total_errors": total_errors,
        "error_counts": {k: int(v) for k, v in error_counts.items()},
        "top_3_errors": [(str(k), int(v)) for k, v in top_3],
    }


def merge_errors(*error_gdfs: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Merge multiple error GeoDataFrames into one.

    Parameters:
        *error_gdfs: Variable number of error GeoDataFrames

    Returns:
        Combined GeoDataFrame with all errors
    """
    valid_gdfs = [g for g in error_gdfs if g is not None and not g.empty]

    if not valid_gdfs:
        return gpd.GeoDataFrame(
            {"road_id": [], "error_type": [], "geometry": []},
            geometry="geometry",
            crs=4326,
        )

    crs = valid_gdfs[0].crs
    combined = pd.concat(valid_gdfs, ignore_index=True)

    return gpd.GeoDataFrame(combined, geometry="geometry", crs=crs)
