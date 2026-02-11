"""Load road geometries from local files.

Supports any format readable by GeoPandas/Fiona: Shapefile, GeoJSON,
GeoPackage, etc.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd

from ovc.core.crs import ensure_wgs84
from ovc.core.geometry import drop_empty_and_fix, clip_to_boundary
from ovc.core.logging import get_logger


def load_roads(
    path: Path,
    boundary_4326: gpd.GeoDataFrame | None = None,
) -> gpd.GeoDataFrame:
    """Load roads from a local vector file.

    Parameters
    ----------
    path : Path
        Path to the roads dataset (Shapefile, GeoJSON, GeoPackage, etc.).
    boundary_4326 : GeoDataFrame, optional
        If provided, clips roads to the boundary.

    Returns
    -------
    GeoDataFrame
        Roads in WGS 84 with ``osmid`` and ``feature_type`` columns.
    """
    logger = get_logger("ovc.loaders.roads")
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Roads file not found: {path}")

    # Warn about large files before loading
    file_size_mb = path.stat().st_size / 1e6
    if file_size_mb > 500:
        logger.warning(
            f"Large roads file ({file_size_mb:.0f} MB) — "
            "loading may be slow and require significant memory"
        )

    logger.info(f"Loading roads from {path}")
    gdf = gpd.read_file(path)

    if gdf.empty:
        logger.warning("Roads file is empty")
        return gpd.GeoDataFrame(geometry=[], crs=4326)

    gdf = ensure_wgs84(gdf)

    # Keep only line geometries
    gdf = gdf[gdf.geometry.type.isin(["LineString", "MultiLineString"])].copy()
    gdf = drop_empty_and_fix(gdf)

    if gdf.empty:
        logger.warning("No line geometries found in roads file")
        return gpd.GeoDataFrame(geometry=[], crs=4326)

    # Clip to boundary if provided
    if boundary_4326 is not None and not boundary_4326.empty:
        boundary_4326 = ensure_wgs84(boundary_4326)
        gdf = clip_to_boundary(gdf, boundary_4326)
        if gdf.empty:
            logger.warning("No roads within boundary after clipping")
            return gpd.GeoDataFrame(geometry=[], crs=4326)

    gdf = gdf.reset_index(drop=True)

    # Ensure an ID column exists for downstream compatibility
    if "osmid" not in gdf.columns:
        gdf["osmid"] = gdf.index.astype(str)
    else:
        gdf["osmid"] = gdf["osmid"].astype(str)

    if len(gdf) > 100_000:
        logger.warning(
            f"Large dataset ({len(gdf):,} road features) — "
            "QC checks may take several minutes"
        )

    gdf["feature_type"] = "road"
    logger.info(f"Loaded {len(gdf)} road features")
    return gdf
