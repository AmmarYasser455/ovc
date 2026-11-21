"""Load building geometries from local files.

Supports any format readable by GeoPandas/Fiona: Shapefile, GeoJSON,
GeoPackage, etc.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd

from ovc.core.crs import ensure_wgs84
from ovc.core.geometry import drop_empty_and_fix
from ovc.core.logging import get_logger


def load_buildings(path: Path) -> gpd.GeoDataFrame:
    """Load buildings from a local vector file.

    Parameters
    ----------
    path : Path
        Path to the buildings dataset (Shapefile, GeoJSON, GeoPackage, etc.).

    Returns
    -------
    GeoDataFrame
        Buildings in WGS 84 with ``osmid`` column for compatibility.
    """
    logger = get_logger("ovc.loaders.buildings")
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Buildings file not found: {path}")

    # Warn about large files before loading
    file_size_mb = path.stat().st_size / 1e6
    if file_size_mb > 500:
        logger.warning(
            f"Large buildings file ({file_size_mb:.0f} MB) — "
            "loading may be slow and require significant memory"
        )

    logger.info(f"Loading buildings from {path}")
    gdf = gpd.read_file(path)

    if gdf.empty:
        logger.warning("Buildings file is empty")
        return gpd.GeoDataFrame(geometry=[], crs=4326)

    gdf = ensure_wgs84(gdf)

    # Ensure an ID column exists. It is assigned before any feature is
    # dropped so a generated ID is the feature's position in the source file.
    gdf = gdf.reset_index(drop=True)
    if "osmid" not in gdf.columns:
        gdf["osmid"] = gdf.index.astype(str)
    else:
        gdf["osmid"] = gdf["osmid"].astype(str)

    # Keep only polygon geometries
    n_read = len(gdf)
    gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()
    gdf = drop_empty_and_fix(gdf)
    if len(gdf) < n_read:
        logger.warning(
            f"{n_read - len(gdf)} of {n_read} features are empty or not "
            "polygons and were left out of the checks"
        )

    if gdf.empty:
        logger.warning("No polygon geometries found in buildings file")
        return gpd.GeoDataFrame(geometry=[], crs=4326)

    gdf = gdf.reset_index(drop=True)

    if len(gdf) > 100_000:
        logger.warning(
            f"Large dataset ({len(gdf):,} buildings) — "
            "QC checks may take several minutes"
        )

    logger.info(f"Loaded {len(gdf)} buildings")
    return gdf
