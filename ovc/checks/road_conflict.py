from __future__ import annotations
import geopandas as gpd

def find_buildings_on_roads(buildings_metric: gpd.GeoDataFrame, roads_metric: gpd.GeoDataFrame, road_buffer_m: float, min_intersection_area_m2: float) -> gpd.GeoDataFrame:
    if buildings_metric is None or roads_metric is None:
        return gpd.GeoDataFrame(geometry=[], crs=buildings_metric.crs if buildings_metric is not None else 3857)
    if buildings_metric.empty or roads_metric.empty:
        return gpd.GeoDataFrame(geometry=[], crs=buildings_metric.crs)

    rb = roads_metric.copy()
    rb["geometry"] = rb.geometry.buffer(float(road_buffer_m))

    inter = gpd.overlay(buildings_metric[["bldg_id", "geometry"]], rb[["osmid", "geometry"]], how="intersection")
    if inter is None or inter.empty:
        return gpd.GeoDataFrame(geometry=[], crs=buildings_metric.crs)

    inter["inter_area_m2"] = inter.geometry.area.astype(float)
    inter = inter[inter["inter_area_m2"] >= float(min_intersection_area_m2)].copy()
    if inter.empty:
        return gpd.GeoDataFrame(geometry=[], crs=buildings_metric.crs)

    inter["error_type"] = "building_on_road"
    return inter

def build_road_conflict_buildings_layer(buildings_metric: gpd.GeoDataFrame, conflicts: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if conflicts is None or conflicts.empty:
        return gpd.GeoDataFrame(geometry=[], crs=buildings_metric.crs)
    ids = set(conflicts["bldg_id"].astype(int).tolist())
    sub = buildings_metric[buildings_metric["bldg_id"].astype(int).isin(ids)].copy()
    sub["error_type"] = "building_on_road"
    sub["overlap_class"] = "n/a"
    return sub
