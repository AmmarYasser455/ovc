from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pandas as pd

from ovc.core.logging import get_logger
from ovc.core.config import DEFAULT_CONFIG
from ovc.core.crs import get_crs_pair
from ovc.loaders.boundaries import load_boundary_shapefile
from ovc.loaders.buildings import load_buildings
from ovc.loaders.roads import load_roads

from ovc.checks.overlap import find_building_overlaps
from ovc.checks.road_conflict import find_buildings_on_roads
from ovc.checks.boundary_overlap import find_buildings_touching_boundary

from ovc.metrics.summary import build_summary_metrics
from ovc.export.tables import write_metrics_csv
from ovc.export.geopackage import write_geopackage
from ovc.export.webmap import write_webmap


@dataclass(frozen=True)
class PipelineOutputs:
    gpkg_path: Path
    metrics_csv: Path
    webmap_html: Path


def _ensure_osmid(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Ensure a stable string osmid column exists.
    Falls back to index-based IDs if missing.
    """
    if "osmid" not in gdf.columns:
        gdf = gdf.copy()
        gdf["osmid"] = gdf.index.astype(str)
    else:
        gdf["osmid"] = gdf["osmid"].astype(str)
    return gdf


def _merge_errors(*layers: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    layers = [g for g in layers if g is not None and not g.empty]
    if not layers:
        return gpd.GeoDataFrame(
            {
                "osmid": [],
                "bldg_id": [],
                "error_type": [],
                "error_class": [],
                "geometry": [],
            },
            geometry="geometry",
            crs=4326,
        )

    crs = layers[0].crs
    df = pd.concat(layers, ignore_index=True)
    out = gpd.GeoDataFrame(df, crs=crs)

    out = _ensure_osmid(out)
    out = out[["osmid", "bldg_id", "error_type", "error_class", "geometry"]]
    out = out.drop_duplicates(subset=["bldg_id", "error_type"])

    return out


def run_pipeline(
    boundary_path: Path,
    out_dir: Path,
    buildings_path: Path | None = None,
    roads_path: Path | None = None,
    config=DEFAULT_CONFIG,
) -> PipelineOutputs:
    log = get_logger()
    out_dir = Path(out_dir)

    attribution_text = "© OpenStreetMap contributors | OVC by Ammar"

    boundary = load_boundary_shapefile(boundary_path)
    crs_pair = get_crs_pair(boundary.gdf_4326)
    boundary_union_4326 = boundary.gdf_4326.unary_union

    # Buildings
    if buildings_path is not None:
        buildings_4326 = gpd.read_file(buildings_path).to_crs(4326)
    else:
        buildings_4326 = load_buildings(
            boundary.gdf_4326,
            config.tags.buildings,
            parts=9,
        )

    buildings_4326 = buildings_4326.reset_index(drop=True)
    buildings_4326 = _ensure_osmid(buildings_4326)

    buildings_metric = buildings_4326.to_crs(crs_pair.crs_metric).copy()
    buildings_metric["bldg_id"] = buildings_metric.index.astype(int)
    buildings_metric["osmid"] = buildings_4326["osmid"].values

    # Roads
    if roads_path is not None:
        roads_4326 = gpd.read_file(roads_path).to_crs(4326)
    else:
        roads_4326 = load_roads(
            boundary.gdf_4326,
            config.tags.roads,
        )

    roads_4326 = _ensure_osmid(roads_4326)
    roads_metric = roads_4326.to_crs(crs_pair.crs_metric)

    # Checks
    overlaps_metric = find_building_overlaps(buildings_metric, config.overlap)

    overlap_buildings_metric = gpd.GeoDataFrame(geometry=[], crs=buildings_metric.crs)
    if overlaps_metric is not None and not overlaps_metric.empty:
        sev = {"sliver": 1, "partial": 2, "duplicate": 3}
        inv = {1: "sliver", 2: "partial", 3: "duplicate"}

        a = overlaps_metric[["bldg_a", "overlap_type"]].rename(
            columns={"bldg_a": "bldg_id"}
        )
        b = overlaps_metric[["bldg_b", "overlap_type"]].rename(
            columns={"bldg_b": "bldg_id"}
        )
        per_bldg = pd.concat([a, b], ignore_index=True)

        per_bldg["sev"] = per_bldg["overlap_type"].map(sev).fillna(1).astype(int)
        per_bldg = per_bldg.groupby("bldg_id", as_index=False)["sev"].max()
        per_bldg["error_class"] = per_bldg["sev"].map(inv)

        ids = set(per_bldg["bldg_id"].astype(int))
        overlap_buildings_metric = buildings_metric[
            buildings_metric["bldg_id"].isin(ids)
        ].copy()
        overlap_buildings_metric["error_type"] = "building_overlap"
        overlap_buildings_metric = overlap_buildings_metric.merge(
            per_bldg[["bldg_id", "error_class"]],
            on="bldg_id",
            how="left",
        )
        overlap_buildings_metric["error_class"] = overlap_buildings_metric[
            "error_class"
        ].fillna("sliver")

    road_conflicts_metric = find_buildings_on_roads(
        buildings_metric=buildings_metric[["bldg_id", "geometry"]],
        roads_metric=roads_metric[["osmid", "geometry"]],
        road_buffer_m=config.road_conflict.road_buffer_m,
        min_intersection_area_m2=config.road_conflict.min_intersection_area_m2,
    )

    road_conflict_buildings_metric = gpd.GeoDataFrame(
        geometry=[], crs=buildings_metric.crs
    )
    if road_conflicts_metric is not None and not road_conflicts_metric.empty:
        ids = set(road_conflicts_metric["bldg_id"])
        road_conflict_buildings_metric = buildings_metric[
            buildings_metric["bldg_id"].isin(ids)
        ].copy()
        road_conflict_buildings_metric["error_type"] = "building_on_road"
        road_conflict_buildings_metric["error_class"] = "road_buffer"

    boundary_metric = boundary.gdf_4326.to_crs(crs_pair.crs_metric)

    boundary_overlap_metric = find_buildings_touching_boundary(
        buildings_metric=buildings_metric[["bldg_id", "osmid", "geometry"]],
        boundary_metric=boundary_metric[["geometry"]],
        boundary_buffer_m=0.5,
    )

    outside_boundary_metric = buildings_4326[
        ~buildings_4326.within(boundary_union_4326)
    ].copy()
    outside_boundary_metric = outside_boundary_metric.to_crs(crs_pair.crs_metric)
    outside_boundary_metric["bldg_id"] = outside_boundary_metric.index.astype(int)
    outside_boundary_metric = _ensure_osmid(outside_boundary_metric)
    outside_boundary_metric["error_type"] = "outside_boundary"
    outside_boundary_metric["error_class"] = "outside"

    errors_metric = _merge_errors(
        overlap_buildings_metric,
        road_conflict_buildings_metric,
        outside_boundary_metric[
            ["osmid", "bldg_id", "error_type", "error_class", "geometry"]
        ],
    )

    error_ids = set(errors_metric["bldg_id"])
    buildings_clean_metric = buildings_metric[
        ~buildings_metric["bldg_id"].isin(error_ids)
    ]

    buildings_clean_4326 = buildings_clean_metric.to_crs(4326)
    overlap_buildings_4326 = overlap_buildings_metric.to_crs(4326)
    errors_4326 = errors_metric.to_crs(4326)

    metrics = build_summary_metrics(
        buildings_4326=buildings_4326,
        overlaps_metric=overlaps_metric,
        road_conflicts_buildings_metric=road_conflicts_metric,
        boundary_overlap_buildings_metric=boundary_overlap_metric,
        outside_boundary_buildings_metric=outside_boundary_metric,
    )

    gpkg_path = out_dir / "building_qc" / "building_qc.gpkg"
    metrics_csv = out_dir / "building_qc" / "building_qc_metrics.csv"
    webmap_html = out_dir / "building_qc" / "building_qc_map.html"

    write_geopackage(
        gpkg_path=gpkg_path,
        boundary_4326=boundary.gdf_4326,
        roads_4326=roads_4326,
        buildings_clean_4326=buildings_clean_4326,
        errors_4326=errors_4326,
    )

    write_metrics_csv(metrics_csv, metrics)

    write_webmap(
        html_path=webmap_html,
        boundary_4326=boundary.gdf_4326,
        roads_4326=roads_4326,
        buildings_clean_4326=buildings_clean_4326,
        overlap_buildings_4326=overlap_buildings_4326,
        errors_4326=errors_4326,
        attribution_text=attribution_text,
    )

    return PipelineOutputs(
        gpkg_path=gpkg_path,
        metrics_csv=metrics_csv,
        webmap_html=webmap_html,
    )
