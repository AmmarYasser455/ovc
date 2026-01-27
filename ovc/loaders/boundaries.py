from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import geopandas as gpd
from ovc.core.crs import ensure_wgs84
from ovc.core.geometry import drop_empty_and_fix


@dataclass(frozen=True)
class BoundaryResult:
    name: str
    gdf_4326: gpd.GeoDataFrame


def load_boundary_shapefile(path: Path) -> BoundaryResult:
    gdf = gpd.read_file(path)
    gdf = ensure_wgs84(gdf)
    gdf = drop_empty_and_fix(gdf)
    if gdf.empty:
        raise ValueError(f"Boundary is empty: {path}")
    gdf = gdf[["geometry"]].copy()
    gdf["aoi_name"] = path.stem
    return BoundaryResult(name=path.stem, gdf_4326=gdf)
