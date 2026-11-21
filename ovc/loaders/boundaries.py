from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import geopandas as gpd
from shapely.geometry import MultiPolygon
from shapely.geometry.base import BaseGeometry
from ovc.core.crs import ensure_wgs84
from ovc.core.geometry import drop_empty_and_fix


@dataclass(frozen=True)
class BoundaryResult:
    name: str
    gdf_4326: gpd.GeoDataFrame


def _polygon_part(geom: BaseGeometry):
    """Return the polygonal part of ``geom`` or None if it has none."""
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    if geom.geom_type == "GeometryCollection":
        polys = []
        for g in geom.geoms:
            part = _polygon_part(g)
            if part is not None:
                polys.extend(part.geoms if part.geom_type == "MultiPolygon" else [part])
        return MultiPolygon(polys) if polys else None
    return None


def load_boundary_shapefile(path: Path) -> BoundaryResult:
    """Load an AOI boundary and return its polygons in WGS 84.

    Non-polygon features (points, lines) are ignored: they have no area, so
    using them as a boundary would silently clip every feature away.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Boundary file not found: {path}")
    gdf = gpd.read_file(path)
    gdf = ensure_wgs84(gdf)
    gdf = drop_empty_and_fix(gdf)
    if not gdf.empty:
        gdf["geometry"] = gdf.geometry.apply(_polygon_part)
        gdf = gdf[gdf.geometry.notna()].copy()
    if gdf.empty:
        raise ValueError(f"Boundary is empty or has no polygon geometry: {path}")
    gdf = gdf[["geometry"]].copy()
    gdf["aoi_name"] = path.stem
    return BoundaryResult(name=path.stem, gdf_4326=gdf)
