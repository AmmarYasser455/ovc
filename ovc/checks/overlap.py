from __future__ import annotations

from dataclasses import dataclass
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon, MultiPolygon

from ovc.core.spatial_index import ensure_sindex


@dataclass(frozen=True, init=False)
class OverlapThresholds:
    min_intersection_area_m2: float
    duplicate_ratio_min: float
    partial_ratio_min: float

    def __init__(
        self,
        min_intersection_area_m2: float = 1.0,
        duplicate_ratio_min: float | None = None,
        duplicate_min_ratio: float | None = None,
        partial_ratio_min: float = 0.5,
    ):
        object.__setattr__(self, "min_intersection_area_m2", min_intersection_area_m2)

        if duplicate_ratio_min is not None:
            object.__setattr__(self, "duplicate_ratio_min", duplicate_ratio_min)
        elif duplicate_min_ratio is not None:
            object.__setattr__(self, "duplicate_ratio_min", duplicate_min_ratio)
        else:
            object.__setattr__(self, "duplicate_ratio_min", 0.9)

        object.__setattr__(self, "partial_ratio_min", partial_ratio_min)


def _area(g):
    if g is None or g.is_empty:
        return 0.0
    return float(getattr(g, "area", 0.0))


def _keep_polygonal(g):
    if g is None or g.is_empty:
        return None
    if isinstance(g, Polygon):
        return g
    if isinstance(g, MultiPolygon):
        if len(g.geoms) == 0:
            return None
        return max(g.geoms, key=lambda x: x.area)
    return None


def find_building_overlaps(
    buildings_metric: gpd.GeoDataFrame,
    thresholds: OverlapThresholds,
) -> gpd.GeoDataFrame:
    if buildings_metric is None or buildings_metric.empty:
        return gpd.GeoDataFrame(geometry=[], crs=getattr(buildings_metric, "crs", None))

    gdf = buildings_metric.reset_index(drop=True)
    sindex = ensure_sindex(gdf)

    rows = []
    for i, a in gdf.iterrows():
        ga = a.geometry
        if ga is None or ga.is_empty:
            continue

        cand = list(sindex.intersection(ga.bounds))
        for j in cand:
            if j <= i:
                continue

            b = gdf.iloc[j]
            gb = b.geometry
            if gb is None or gb.is_empty:
                continue

            if not ga.intersects(gb):
                continue

            inter = _keep_polygonal(ga.intersection(gb))
            if inter is None or inter.is_empty:
                continue

            inter_area = _area(inter)
            if inter_area < thresholds.min_intersection_area_m2:
                continue

            area_a = _area(ga)
            area_b = _area(gb)
            denom = min(area_a, area_b) if min(area_a, area_b) > 0 else 0.0
            if denom <= 0:
                continue

            ratio = inter_area / denom

            if ratio >= thresholds.duplicate_ratio_min:
                overlap_type = "duplicate"
            elif ratio >= thresholds.partial_ratio_min:
                overlap_type = "partial"
            else:
                overlap_type = "sliver"

            rows.append(
                {
                    "bldg_a": int(a.bldg_id),
                    "bldg_b": int(b.bldg_id),
                    "inter_area_m2": float(inter_area),
                    "overlap_ratio": float(ratio),
                    "overlap_type": overlap_type,
                    "error_type": "building_overlap",
                    "geometry": inter,
                }
            )

    if not rows:
        return gpd.GeoDataFrame(geometry=[], crs=gdf.crs)

    df = pd.DataFrame(rows)
    return gpd.GeoDataFrame(df, geometry="geometry", crs=gdf.crs)
