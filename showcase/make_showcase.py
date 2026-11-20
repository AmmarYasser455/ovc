"""Build the OVC showcase from the OpenStreetMap extract in showcase/data/.

Run from the repository root, offline::

    python showcase/make_showcase.py

Question: in a small part of Zamalek (Cairo), which OpenStreetMap building
footprints overlap another footprint, and which sit on a road?

Outputs (written next to this script unless an output directory is given):
``map.geojson`` (EPSG:4326, lon/lat), ``map.png`` and ``index.html``.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping
from shapely.geometry.polygon import orient

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ovc.checks.overlap import find_building_overlaps  # noqa: E402
from ovc.checks.road_conflict import find_buildings_on_roads  # noqa: E402
from ovc.core.config import DEFAULT_CONFIG  # noqa: E402
from ovc.core.crs import get_crs_pair  # noqa: E402
from ovc.loaders.buildings import load_buildings  # noqa: E402
from ovc.loaders.roads import load_roads  # noqa: E402

TITLE = "OVC on OpenStreetMap data: Zamalek, Cairo"
CREDIT = "Data: (c) OpenStreetMap contributors, ODbL"
REPO_URL = "https://github.com/AmmarYasser455/ovc"
STATUS_COLORS = {
    "ok": "#9aa5b1",
    "overlap": "#e08a00",
    "on_road": "#d1344a",
    "overlap_and_road": "#7a1fa2",
}
STATUS_LABELS = {
    "ok": "No issue found",
    "overlap": "Overlaps another building",
    "on_road": "Within 1 m of a road centreline",
    "overlap_and_road": "Both",
}


def run_checks(data_dir: Path) -> dict:
    """Run the OVC loaders and checks; return layers (EPSG:4326) and tables."""
    buildings = load_buildings(data_dir / "buildings.geojson")
    roads = load_roads(data_dir / "roads.geojson")

    crs_metric = get_crs_pair(buildings).crs_metric  # local UTM zone, metres
    b_m = buildings.to_crs(crs_metric)
    b_m["bldg_id"] = b_m.index.astype(int)
    r_m = roads.to_crs(crs_metric)

    overlaps = find_building_overlaps(b_m, DEFAULT_CONFIG.overlap)
    conflicts = find_buildings_on_roads(
        buildings_metric=b_m[["bldg_id", "geometry"]],
        roads_metric=r_m[["osmid", "geometry"]],
        road_buffer_m=DEFAULT_CONFIG.road_conflict.road_buffer_m,
        min_intersection_area_m2=DEFAULT_CONFIG.road_conflict.min_intersection_area_m2,
    )

    out = buildings.copy()
    out["bldg_id"] = b_m["bldg_id"].values
    out["area_m2"] = b_m.geometry.area.values
    out["overlap_type"] = ""
    out["overlap_area_m2"] = 0.0
    out["road_conflict_area_m2"] = 0.0
    out["road_osmid"] = ""

    rank = {"sliver": 1, "partial": 2, "duplicate": 3}
    if not overlaps.empty:
        for _, row in overlaps.iterrows():
            for key in ("bldg_a", "bldg_b"):
                i = int(row[key])
                cur = out.at[i, "overlap_type"]
                if rank.get(row["overlap_type"], 0) > rank.get(cur, 0):
                    out.at[i, "overlap_type"] = row["overlap_type"]
                out.at[i, "overlap_area_m2"] += float(row["inter_area_m2"])
    if not conflicts.empty:
        for bid, grp in conflicts.groupby("bldg_id"):
            out.at[int(bid), "road_conflict_area_m2"] = float(
                grp["inter_area_m2"].sum()
            )
            out.at[int(bid), "road_osmid"] = ",".join(sorted(set(grp["osmid"])))

    has_o = out["overlap_type"] != ""
    has_r = out["road_conflict_area_m2"] > 0
    out["status"] = "ok"
    out.loc[has_o & ~has_r, "status"] = "overlap"
    out.loc[~has_o & has_r, "status"] = "on_road"
    out.loc[has_o & has_r, "status"] = "overlap_and_road"

    return {
        "buildings": out,
        "roads": roads,
        "overlaps": overlaps,
        "conflicts": conflicts,
        "crs_metric": crs_metric,
    }


def summarize(res: dict) -> dict:
    b = res["buildings"]
    ov = res["overlaps"]
    return {
        "buildings": int(len(b)),
        "roads": int(len(res["roads"])),
        "overlap_pairs": int(len(ov)),
        "overlap_by_type": (
            {k: int(v) for k, v in ov["overlap_type"].value_counts().items()}
            if not ov.empty
            else {}
        ),
        "buildings_with_overlap": int((b["overlap_type"] != "").sum()),
        "buildings_on_road": int((b["road_conflict_area_m2"] > 0).sum()),
        "buildings_clean": int((b["status"] == "ok").sum()),
        "total_overlap_area_m2": (
            round(float(ov["inter_area_m2"].sum()), 1) if not ov.empty else 0.0
        ),
        "median_building_area_m2": round(float(b["area_m2"].median()), 1),
        "crs_metric": res["crs_metric"].to_string(),
    }


def _round_coords(obj, nd=7):
    if isinstance(obj, (list, tuple)):
        return [_round_coords(o, nd) for o in obj]
    return round(float(obj), nd)


def _feature(geom, props: dict) -> dict:
    if geom.geom_type == "Polygon":
        geom = orient(geom, 1.0)  # RFC 7946: exterior CCW, holes CW
    g = mapping(geom)
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {
            "type": g["type"],
            "coordinates": _round_coords(g["coordinates"]),
        },
    }


def _clean(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, float):
        return round(v, 2)
    return v


def to_geojson(res: dict) -> dict:
    """Result as an RFC 7946 FeatureCollection in lon/lat (EPSG:4326)."""
    feats = []
    b = res["buildings"]
    for _, r in b.iterrows():
        props = {
            "layer": "building",
            "osmid": r["osmid"],
            "building": _clean(r.get("building")),
            "name": _clean(r.get("name")),
            "status": r["status"],
            "area_m2": _clean(float(r["area_m2"])),
            "overlap_type": r["overlap_type"] or None,
            "overlap_area_m2": _clean(float(r["overlap_area_m2"])),
            "road_conflict_area_m2": _clean(float(r["road_conflict_area_m2"])),
            "road_osmid": r["road_osmid"] or None,
        }
        feats.append(_feature(r.geometry, props))
    for _, r in res["roads"].iterrows():
        props = {
            "layer": "road",
            "osmid": r["osmid"],
            "highway": _clean(r.get("highway")),
            "name": _clean(r.get("name")),
        }
        feats.append(_feature(r.geometry, props))
    return {"type": "FeatureCollection", "features": feats}


def write_png(res: dict, path: Path, summary: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    b = res["buildings"]
    roads = res["roads"]
    fig, ax = plt.subplots(figsize=(9.33, 8.4), dpi=150)
    roads.plot(ax=ax, color="#33414f", linewidth=1.0, zorder=1)
    for status, color in STATUS_COLORS.items():
        sub = b[b["status"] == status]
        if not sub.empty:
            sub.plot(
                ax=ax,
                facecolor=color,
                edgecolor="#2b2b2b",
                linewidth=0.3,
                zorder=2 if status == "ok" else 3,
            )
    handles = [
        Patch(
            facecolor=STATUS_COLORS[s],
            edgecolor="#2b2b2b",
            label=f"{STATUS_LABELS[s]} ({int((b['status'] == s).sum())})",
        )
        for s in STATUS_COLORS
        if (b["status"] == s).any()
    ]
    handles.append(plt.Line2D([0], [0], color="#33414f", lw=1.5, label="Road (OSM)"))
    ax.legend(handles=handles, loc="lower left", fontsize=8, framealpha=0.95)
    lat0 = float(b.geometry.union_all().centroid.y)
    ax.set_aspect(1.0 / math.cos(math.radians(lat0)))
    ax.set_xlabel("Longitude (degrees E, EPSG:4326)")
    ax.set_ylabel("Latitude (degrees N)")
    ax.tick_params(labelsize=7)
    ax.set_title(
        f"{TITLE}\n{summary['buildings']} buildings, {summary['buildings_with_overlap']} "
        f"overlapping, {summary['buildings_on_road']} within 1 m of a road",
        fontsize=11,
    )
    ax.annotate(
        "N ↑ (north up)",
        xy=(0.97, 0.97),
        xycoords="axes fraction",
        ha="right",
        va="top",
        fontsize=9,
        bbox={"boxstyle": "round", "fc": "white", "ec": "#999999"},
    )
    fig.text(0.99, 0.005, CREDIT, ha="right", va="bottom", fontsize=7, color="#444")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
 body { margin: 0; font-family: system-ui, sans-serif; }
 header { padding: 10px 16px; background: #f4f6f8; border-bottom: 1px solid #d0d7de; }
 h1 { margin: 0 0 4px; font-size: 1.15rem; }
 p { margin: 2px 0; font-size: 0.9rem; }
 #map { height: calc(100vh - 110px); }
</style>
</head>
<body>
<header>
 <h1>__TITLE__</h1>
 <p>Orange: overlaps another building. Red: within 1 m of a road centreline. Purple: both. Grey: no issue found.</p>
 <p>Produced by <a href="__REPO__">OVC</a> from OpenStreetMap data. Serve this folder over HTTP (for example <code>python -m http.server</code>) so the page can load map.geojson.</p>
</header>
<div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
 var colors = __COLORS__;
 var map = L.map('map');
 L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
   maxZoom: 19,
   attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
 }).addTo(map);
 function popup(p) {
   var rows = Object.keys(p).filter(function (k) { return p[k] !== null; })
     .map(function (k) { return '<b>' + k + '</b>: ' + p[k]; });
   return rows.join('<br>');
 }
 fetch('map.geojson').then(function (r) { return r.json(); }).then(function (data) {
   var layer = L.geoJSON(data, {
     style: function (f) {
       if (f.properties.layer === 'road') return { color: '#33414f', weight: 2 };
       return { color: '#2b2b2b', weight: 1, fillOpacity: 0.7,
                fillColor: colors[f.properties.status] };
     },
     onEachFeature: function (f, l) { l.bindPopup(popup(f.properties)); }
   }).addTo(map);
   map.fitBounds(layer.getBounds());
 });
</script>
</body>
</html>
"""


def write_html(path: Path) -> None:
    html = (
        HTML.replace("__TITLE__", TITLE)
        .replace("__REPO__", REPO_URL)
        .replace("__COLORS__", json.dumps(STATUS_COLORS))
    )
    path.write_text(html, encoding="utf-8")


def main(out_dir: Path | None = None, data_dir: Path | None = None) -> dict:
    out_dir = Path(out_dir) if out_dir is not None else HERE
    data_dir = Path(data_dir) if data_dir is not None else HERE / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    res = run_checks(data_dir)
    summary = summarize(res)

    with open(out_dir / "map.geojson", "w", encoding="utf-8") as f:
        json.dump(to_geojson(res), f, ensure_ascii=False, indent=0)
        f.write("\n")
    write_html(out_dir / "index.html")
    try:
        write_png(res, out_dir / "map.png", summary)
    except ImportError:
        print("matplotlib not installed: map.png skipped")
    return summary


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
