"""List and read vector layers, keeping each feature's ID (FID).

The FID is the feature ID stored in the file, the same number QGIS shows as
``$id``. It is kept as the GeoDataFrame index so every finding can be traced
back to its source feature even when the layer has no usable ID attribute.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import geopandas as gpd
import pyogrio

from ovc.engine.model import crs_label

# Extensions offered by the file picker. Anything GDAL can read still works
# from the Python API and the CLI.
SUPPORTED_EXTENSIONS = (
    ".gpkg",
    ".shp",
    ".geojson",
    ".json",
    ".fgb",
    ".gml",
    ".kml",
    ".gdb",
)


class LayerReadError(Exception):
    """A file or layer could not be read. The message is safe to show."""


@dataclass
class LayerInfo:
    path: str
    name: str
    geometry_type: str
    feature_count: int
    crs: str  # human label, "missing" when the layer has no CRS
    has_crs: bool
    is_polygon: bool
    fields: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def _check_path(path) -> Path:
    path = Path(path)
    if not path.exists():
        raise LayerReadError(f"File not found: {path}")
    return path


def list_layers(path) -> list[LayerInfo]:
    """Describe every layer in a vector file without loading its features."""
    path = _check_path(path)
    try:
        names = [str(row[0]) for row in pyogrio.list_layers(path)]
    except Exception as exc:
        raise LayerReadError(f"Cannot read {path.name}: {exc}") from exc
    if not names:
        raise LayerReadError(f"{path.name} contains no layers.")

    infos = []
    for name in names:
        try:
            meta = pyogrio.read_info(path, layer=name, force_feature_count=True)
        except Exception as exc:
            raise LayerReadError(
                f"Cannot read layer '{name}' in {path.name}: {exc}"
            ) from exc
        geometry_type = meta.get("geometry_type") or "none"
        crs = None
        if meta.get("crs"):
            try:
                crs = gpd.GeoSeries([], crs=meta["crs"]).crs
            except Exception:
                crs = None
        infos.append(
            LayerInfo(
                path=str(path),
                name=name,
                geometry_type=geometry_type,
                feature_count=int(meta.get("features") or 0),
                crs=crs_label(crs),
                has_crs=crs is not None,
                # "Unknown" layers can hold polygons; the engine reports
                # every non-polygon feature it meets.
                is_polygon="polygon" in geometry_type.lower()
                or geometry_type.lower() in ("unknown", "geometry collection"),
                fields=[str(f) for f in meta.get("fields", [])],
            )
        )
    return infos


def read_layer(path, layer: str | None = None) -> gpd.GeoDataFrame:
    """Read one layer with the file's feature IDs as the index (named ``fid``).

    The file is opened read-only. Geometries are returned exactly as stored:
    nothing is repaired, dropped or reprojected here.
    """
    path = _check_path(path)
    try:
        gdf = pyogrio.read_dataframe(path, layer=layer, fid_as_index=True)
    except Exception as exc:
        target = f"layer '{layer}' in {path.name}" if layer else path.name
        raise LayerReadError(f"Cannot read {target}: {exc}") from exc
    if not isinstance(gdf, gpd.GeoDataFrame):
        target = f"Layer '{layer}'" if layer else path.name
        raise LayerReadError(f"{target} has no geometry column.")
    gdf.index.name = "fid"
    return gdf
