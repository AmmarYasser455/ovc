"""Editing a layer: an in-memory working copy with undo, saved on request.

While a layer is being edited, the map, Select and the OVC tools all read
the working copy, so a check runs on the edited shapes. Nothing is written
until Save Edits, which first copies the original file(s) to
``~/.ovc/backups/<time>/``, or Export, which writes a new file.

Geometries arrive from the map in WGS 84 and are stored in the layer's CRS.
Merge and split run here with Shapely so their results are exact.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely
from shapely.geometry import shape
from shapely.ops import split as shapely_split

from ovc.engine.overlaps import polygonal_part

UNDO_LIMIT = 30
SHAPEFILE_PARTS = (".shp", ".shx", ".dbf", ".prj", ".cpg", ".qix", ".sbn", ".sbx")
WRITE_DRIVERS = {
    ".gpkg": "GPKG",
    ".shp": "ESRI Shapefile",
    ".geojson": "GeoJSON",
    ".json": "GeoJSON",
    ".fgb": "FlatGeobuf",
    ".gml": "GML",
    ".kml": "KML",
}


class EditError(Exception):
    """An edit could not be made. The message is safe to show."""


def backup_root() -> Path:
    return Path.home() / ".ovc" / "backups"


def source_files(path: Path) -> list[Path]:
    """The file(s) that make up a layer's source on disk."""
    if path.suffix.lower() == ".shp":
        return [p for p in (path.with_suffix(s) for s in SHAPEFILE_PARTS) if p.exists()]
    return [path]


def write_layer(
    gdf: gpd.GeoDataFrame, target: Path, layer: str | None, replace: bool
) -> None:
    """Write ``gdf`` to ``target``, replacing only that layer in a GeoPackage."""
    driver = WRITE_DRIVERS.get(target.suffix.lower())
    if driver is None:
        raise EditError(
            "Choose a file name ending in .gpkg, .shp, .geojson, .fgb, .gml or .kml."
        )
    out = gdf.reset_index(drop=True)
    if driver == "GPKG":
        pyogrio.write_dataframe(
            out,
            target,
            layer=layer or target.stem,
            driver=driver,
            layer_options={"OVERWRITE": "YES"} if replace or target.exists() else None,
        )
        return
    # One-layer formats: write next to the target, then swap in, so a
    # failure half-way never leaves a broken file.
    stage = target.parent / f".ovc-saving-{target.stem}"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    try:
        staged = stage / target.name
        kwargs = {"encoding": "UTF-8"} if driver == "ESRI Shapefile" else {}
        pyogrio.write_dataframe(out, staged, driver=driver, **kwargs)
        if driver == "ESRI Shapefile":
            for old in source_files(target):
                old.unlink()
        for part in stage.iterdir():
            part.replace(target.parent / part.name)
    finally:
        shutil.rmtree(stage, ignore_errors=True)


class EditSession:
    """A layer being edited: a working copy indexed by feature ID (FID)."""

    def __init__(self, path: str, layer: str | None, gdf: gpd.GeoDataFrame, crs):
        self.path = Path(path)
        self.layer = layer
        self.crs = crs
        self.gdf = gdf.copy()
        if self.gdf.crs is None:
            self.gdf = self.gdf.set_crs(crs)
        self.undo_stack: list[gpd.GeoDataFrame] = []
        self.redo_stack: list[gpd.GeoDataFrame] = []
        self.dirty = False
        self.geometry_type = self._layer_type()

    # ---- helpers -------------------------------------------------------
    def _layer_type(self) -> str:
        types = set(self.gdf.geometry.dropna().geom_type)
        for kind in ("Polygon", "LineString", "Point"):
            if types and all(t.endswith(kind) for t in types):
                return kind
        return "Polygon" if not types else "Mixed"

    def _from_map(self, geojson) -> object:
        try:
            geom = shape(geojson)
        except Exception as exc:
            raise EditError(f"That shape could not be read: {exc}") from exc
        geom = gpd.GeoSeries([geom], crs=4326).to_crs(self.crs).iloc[0]
        if self.geometry_type == "Polygon":
            geom = polygonal_part(shapely.make_valid(geom))
            if geom is None or geom.area <= 0:
                raise EditError("That shape has no area, so it cannot be a polygon.")
        return geom

    def _to_map(self, fids) -> list[dict]:
        sub = self.gdf.loc[list(fids)].geometry.to_crs(4326)
        return [
            {"fid": int(fid), "geometry": geom.__geo_interface__}
            for fid, geom in sub.items()
            if geom is not None and not geom.is_empty
        ]

    def _check(self, fids) -> list[int]:
        fids = [int(f) for f in fids]
        unknown = [f for f in fids if f not in self.gdf.index]
        if unknown:
            raise EditError(f"No feature with FID {unknown[0]} in this layer.")
        return fids

    def _checkpoint(self) -> None:
        self.undo_stack.append(self.gdf.copy())
        del self.undo_stack[:-UNDO_LIMIT]
        self.redo_stack.clear()
        self.dirty = True

    def _next_fid(self) -> int:
        return int(self.gdf.index.max()) + 1 if len(self.gdf) else 1

    def status(self) -> dict:
        return {
            "editing": True,
            "dirty": self.dirty,
            "can_undo": bool(self.undo_stack),
            "can_redo": bool(self.redo_stack),
            "geometry_type": self.geometry_type,
            "count": int(len(self.gdf)),
        }

    # ---- operations ----------------------------------------------------
    def apply(self, op: dict) -> dict:
        """Run one edit; returns what changed for the map to redraw."""
        kind = op.get("op")
        if kind == "update":
            # One feature ({fid, geometry}) or several ({features: [...]}),
            # undone together.
            items = op.get("features") or [
                {"fid": op.get("fid"), "geometry": op.get("geometry")}
            ]
            fids = self._check([item["fid"] for item in items])
            geoms = [self._from_map(item["geometry"]) for item in items]
            self._checkpoint()
            for fid, geom in zip(fids, geoms):
                self.gdf.loc[fid, self.gdf.geometry.name] = geom
            return self._result(changed=fids)
        if kind == "add":
            geom = self._from_map(op["geometry"])
            self._checkpoint()
            fid = self._next_fid()
            row = {c: None for c in self.gdf.columns}
            row[self.gdf.geometry.name] = geom
            for key, value in (op.get("attributes") or {}).items():
                if key in self.gdf.columns and key != self.gdf.geometry.name:
                    row[key] = value
            new = gpd.GeoDataFrame(
                [row], index=[fid], geometry=self.gdf.geometry.name, crs=self.gdf.crs
            )
            self.gdf = pd.concat([self.gdf, new])
            return self._result(changed=[fid])
        if kind == "delete":
            fids = self._check(op.get("fids") or [])
            if not fids:
                raise EditError("Select the features to delete first.")
            self._checkpoint()
            self.gdf = self.gdf.drop(index=fids)
            return self._result(removed=fids)
        if kind == "merge":
            fids = self._check(op.get("fids") or [])
            if len(fids) < 2:
                raise EditError("Select two or more features to merge.")
            merged = shapely.union_all(
                np.asarray(self.gdf.loc[fids].geometry.values, dtype=object)
            )
            if self.geometry_type == "Polygon":
                merged = polygonal_part(merged)
            self._checkpoint()
            keep, drop = fids[0], fids[1:]
            self.gdf.loc[keep, self.gdf.geometry.name] = merged
            self.gdf = self.gdf.drop(index=drop)
            return self._result(changed=[keep], removed=drop)
        if kind == "split":
            fids = self._check(op.get("fids") or [])
            if len(fids) != 1:
                raise EditError("Select one feature to split.")
            fid = fids[0]
            line = gpd.GeoSeries([shape(op["line"])], crs=4326).to_crs(self.crs).iloc[0]
            pieces = self._split(self.gdf.loc[fid].geometry, line)
            if len(pieces) < 2:
                raise EditError("Draw the split line all the way across the feature.")
            self._checkpoint()
            self.gdf.loc[fid, self.gdf.geometry.name] = pieces[0]
            new_fids = []
            for piece in pieces[1:]:
                new_fid = self._next_fid()
                row = self.gdf.loc[[fid]].copy()
                row.index = [new_fid]
                row[self.gdf.geometry.name] = [piece]
                self.gdf = pd.concat([self.gdf, row])
                new_fids.append(new_fid)
            return self._result(changed=[fid, *new_fids])
        if kind == "undo":
            if not self.undo_stack:
                raise EditError("Nothing to undo.")
            self.redo_stack.append(self.gdf)
            self.gdf = self.undo_stack.pop()
            self.dirty = True
            return self._result(reload=True)
        if kind == "redo":
            if not self.redo_stack:
                raise EditError("Nothing to redo.")
            self.undo_stack.append(self.gdf)
            self.gdf = self.redo_stack.pop()
            self.dirty = True
            return self._result(reload=True)
        raise EditError(f"Unknown edit: {kind}")

    @staticmethod
    def _split(geom, line) -> list:
        parts = []
        for part in getattr(geom, "geoms", [geom]):
            result = shapely_split(part, line)
            parts.extend(
                g
                for g in result.geoms
                if not g.is_empty and (g.area > 0 or g.length > 0)
            )
        return parts

    def _result(self, changed=(), removed=(), reload=False) -> dict:
        out = self.status()
        out.update(
            changed=self._to_map(changed) if changed else [],
            removed=[int(f) for f in removed],
            reload=reload,
        )
        return out

    # ---- saving --------------------------------------------------------
    def save(self) -> dict:
        """Write the working copy back to its source, after a backup."""
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        folder = backup_root() / f"{stamp}-{self.path.stem}"
        folder.mkdir(parents=True, exist_ok=True)
        for part in source_files(self.path):
            shutil.copy2(part, folder / part.name)
        write_layer(self.gdf, self.path, self.layer, replace=True)
        self.dirty = False
        self.undo_stack.clear()
        self.redo_stack.clear()
        return {"saved": str(self.path), "backup": str(folder / self.path.name)}

    def export(self, target) -> dict:
        target = Path(target)
        if target.resolve() == self.path.resolve():
            raise EditError("To write to the layer's own file, use Save Edits.")
        write_layer(self.gdf, target, target.stem, replace=False)
        return {"saved": str(target)}
