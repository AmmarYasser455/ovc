from __future__ import annotations
import geopandas as gpd

def overlap_metrics(overlaps_metric: gpd.GeoDataFrame) -> dict:
    if overlaps_metric is None or overlaps_metric.empty:
        return {
            "overlap_count": 0,
            "overlap_total_area_m2": 0.0,
            "overlap_avg_area_m2": 0.0,
            "overlap_duplicate_count": 0,
            "overlap_partial_count": 0,
            "overlap_sliver_count": 0,
        }

    total = float(overlaps_metric["inter_area_m2"].sum()) if "inter_area_m2" in overlaps_metric.columns else float(overlaps_metric.geometry.area.sum())
    count = int(len(overlaps_metric))
    avg = float(total / count) if count else 0.0

    vc = overlaps_metric["overlap_type"].value_counts().to_dict() if "overlap_type" in overlaps_metric.columns else {}
    return {
        "overlap_count": count,
        "overlap_total_area_m2": total,
        "overlap_avg_area_m2": avg,
        "overlap_duplicate_count": int(vc.get("duplicate", 0)),
        "overlap_partial_count": int(vc.get("partial", 0)),
        "overlap_sliver_count": int(vc.get("sliver", 0)),
    }
