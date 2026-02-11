from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd

logger = logging.getLogger("ovc.export.geopackage")


def _write_layer(gpkg_path: Path, layer: str, gdf: gpd.GeoDataFrame) -> None:
    if gdf is None:
        return
    gpkg_path.parent.mkdir(parents=True, exist_ok=True)
    if gdf.crs is None:
        logger.warning(
            "Layer '%s' has no CRS — writing with EPSG:4326 assumed. "
            "This may produce incorrect results if the data is not in WGS 84.",
            layer,
        )
        gdf = gdf.set_crs(4326)
    gdf.to_file(gpkg_path, layer=layer, driver="GPKG")


def write_geopackage(
    gpkg_path: Path,
    boundary_4326: gpd.GeoDataFrame,
    roads_4326: gpd.GeoDataFrame,
    buildings_clean_4326: gpd.GeoDataFrame,
    errors_4326: gpd.GeoDataFrame,
) -> None:
    _write_layer(gpkg_path, "boundary", boundary_4326)
    _write_layer(gpkg_path, "roads", roads_4326)
    _write_layer(gpkg_path, "buildings_clean", buildings_clean_4326)
    _write_layer(gpkg_path, "errors", errors_4326)
