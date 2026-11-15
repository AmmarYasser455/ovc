"""Build the OVC showcase on real OpenStreetMap data for downtown Cairo.

Question: do OpenStreetMap building footprints in downtown Cairo overlap each
other, or reach onto the centre-line of a mapped road?

Run from the repository root (offline)::

    python showcase/make_showcase.py

Reads ``showcase/data/`` and writes ``map.geojson``, ``map.png`` and
``index.html`` next to this script (or into ``out_dir`` when ``main`` is
called with one).

Data (c) OpenStreetMap contributors, ODbL 1.0.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping
from shapely.geometry.polygon import orient

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ovc.checks.overlap import OverlapThresholds, find_building_overlaps  # noqa: E402
from ovc.checks.road_conflict import find_buildings_on_roads  # noqa: E402
from ovc.core.crs import choose_utm_crs_from_gdf  # noqa: E402

DATA_DIR = HERE / "data"
BUILDINGS_FILE = DATA_DIR / "cairo_downtown_buildings.geojson"
ROADS_FILE = DATA_DIR / "cairo_downtown_roads.geojson"

# Parameters (metres / square metres, applied in the local UTM CRS).
ROAD_BUFFER_M = 1.0
MIN_ROAD_CONFLICT_AREA_M2 = 1.0
OVERLAP_THRESHOLDS = OverlapThresholds(min_intersection_area_m2=1.0)

CREDIT = "Data (c) OpenStreetMap contributors, ODbL"
REPO_URL = "https://github.com/AmmarYasser455/ovc"
COORD_DECIMALS = 7  # about 1 cm at this latitude


def load_data(data_dir: Path = DATA_DIR):
    """Load buildings and roads (EPSG:4326, lon/lat) with OVC id columns."""
    buildings = gpd.read_file(data_dir / BUILDINGS_FILE.name)
    roads = gpd.read_file(data_dir / ROADS_FILE.name)
    for gdf in (buildings, roads):
        if gdf.crs is None or gdf.crs.to_epsg() != 4326:
            raise ValueError("showcase data must be GeoJSON in EPSG:4326")
    buildings["bldg_id"] = buildings["osm_id"].astype("int64")
    roads["osmid"] = roads["osm_id"].astype("int64")
    return buildings, roads


def run_checks(buildings: gpd.GeoDataFrame, roads: gpd.GeoDataFrame):
    """Run OVC's overlap and road-conflict checks in the local UTM zone."""
    metric_crs = choose_utm_crs_from_gdf(buildings)
    b_m = buildings.to_crs(metric_crs)
    r_m = roads.to_crs(metric_crs)
    overlaps = find_building_overlaps(b_m, OVERLAP_THRESHOLDS)
    conflicts = find_buildings_on_roads(
        b_m, r_m, ROAD_BUFFER_M, MIN_ROAD_CONFLICT_AREA_M2
    )
    return metric_crs, b_m, r_m, overlaps, conflicts


def _round(obj):
    if isinstance(obj, float):
        return round(obj, COORD_DECIMALS)
    if isinstance(obj, (list, tuple)):
        return [_round(x) for x in obj]
    return obj


def _geom_json(geom):
    if geom.geom_type == "Polygon":
        geom = orient(geom, sign=1.0)  # RFC 7946: exterior CCW, holes CW
    elif geom.geom_type == "MultiPolygon":
        geom = type(geom)([orient(p, sign=1.0) for p in geom.geoms])
    m = mapping(geom)
    return {"type": m["type"], "coordinates": _round(m["coordinates"])}


def _clean(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        return round(value, 2)
    return value


def build_result(buildings, roads, b_m, overlaps, conflicts):
    """Assemble the result FeatureCollection (EPSG:4326, lon/lat)."""
    road_names = roads.set_index("osmid")["name"].to_dict()
    road_types = roads.set_index("osmid")["highway"].to_dict()
    area_m2 = dict(zip(b_m["bldg_id"], b_m.geometry.area))

    by_bldg = {}
    for row in conflicts.itertuples():
        by_bldg.setdefault(int(row.bldg_id), []).append(row)
    overlap_ids = set()
    if not overlaps.empty:
        overlap_ids = set(overlaps["bldg_a"]) | set(overlaps["bldg_b"])

    # Same numbering as the labels on map.png (flagged buildings by OSM id).
    labels = {bid: i for i, bid in enumerate(sorted(by_bldg), start=1)}

    features = []
    for row in buildings.sort_values("bldg_id").itertuples():
        bid = int(row.bldg_id)
        hits = by_bldg.get(bid, [])
        status = "ok"
        if hits:
            status = "on_road"
        if bid in overlap_ids:
            status = "overlap"
        props = {
            "layer": "building",
            "osm_id": bid,
            "osm_url": f"https://www.openstreetmap.org/way/{bid}",
            "building": _clean(row.building),
            "name": _clean(row.name),
            "area_m2": _clean(area_m2[bid]),
            "qc_status": status,
            "map_label": labels.get(bid),
            "road_conflict_m2": _clean(sum(h.inter_area_m2 for h in hits)) or None,
            "road_osm_ids": ",".join(str(int(h.osmid)) for h in hits) or None,
        }
        features.append(
            {
                "type": "Feature",
                "properties": props,
                "geometry": _geom_json(row.geometry),
            }
        )

    if not conflicts.empty:
        c4326 = conflicts.to_crs(4326).sort_values(["bldg_id", "osmid"])
        for row in c4326.itertuples():
            rid = int(row.osmid)
            props = {
                "layer": "road_conflict",
                "building_osm_id": int(row.bldg_id),
                "road_osm_id": rid,
                "road_name": _clean(road_names.get(rid)),
                "road_type": _clean(road_types.get(rid)),
                "inter_area_m2": _clean(row.inter_area_m2),
                "road_buffer_m": ROAD_BUFFER_M,
            }
            features.append(
                {
                    "type": "Feature",
                    "properties": props,
                    "geometry": _geom_json(row.geometry),
                }
            )

    for row in roads.sort_values("osmid").itertuples():
        props = {
            "layer": "road",
            "osm_id": int(row.osmid),
            "highway": _clean(row.highway),
            "name": _clean(row.name),
        }
        features.append(
            {
                "type": "Feature",
                "properties": props,
                "geometry": _geom_json(row.geometry),
            }
        )

    return {"type": "FeatureCollection", "features": features}


def summarize(buildings, roads, b_m, overlaps, conflicts) -> dict:
    return {
        "buildings": int(len(buildings)),
        "roads": int(len(roads)),
        "invalid_buildings": int((~b_m.geometry.is_valid).sum()),
        "building_overlaps": int(len(overlaps)),
        "buildings_on_roads": (
            int(conflicts["bldg_id"].nunique()) if len(conflicts) else 0
        ),
        "road_conflict_area_m2": (
            round(float(conflicts["inter_area_m2"].sum()), 1) if len(conflicts) else 0.0
        ),
        "max_conflict_area_m2": (
            round(float(conflicts["inter_area_m2"].max()), 1) if len(conflicts) else 0.0
        ),
    }


def write_png(path: Path, b_m, r_m, conflicts, metric_crs, summary) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    flagged = set(conflicts["bldg_id"]) if len(conflicts) else set()
    fig, ax = plt.subplots(figsize=(9.6, 9.6), dpi=150)
    r_m.plot(ax=ax, color="#9e9e9e", linewidth=1.2, zorder=1)
    ok = b_m[~b_m["bldg_id"].isin(flagged)]
    bad = b_m[b_m["bldg_id"].isin(flagged)]
    ok.plot(ax=ax, facecolor="#cfd8dc", edgecolor="#607d8b", linewidth=0.4, zorder=2)
    if len(bad):
        bad.plot(
            ax=ax, facecolor="#ffcc80", edgecolor="#e65100", linewidth=1.0, zorder=3
        )
        conflicts.plot(ax=ax, facecolor="#c62828", edgecolor="#c62828", zorder=4)
        for i, (_, row) in enumerate(bad.sort_values("bldg_id").iterrows(), start=1):
            p = row.geometry.representative_point()
            ax.annotate(
                str(i),
                (p.x, p.y),
                xytext=(6, 6),
                textcoords="offset points",
                fontsize=8,
                color="#b71c1c",
                weight="bold",
                zorder=5,
            )

    ax.set_aspect("equal")
    ax.set_title(
        "Downtown Cairo: OpenStreetMap buildings that reach onto a road centre-line\n"
        f"{summary['buildings_on_roads']} of {summary['buildings']} buildings flagged "
        f"(road buffer {ROAD_BUFFER_M:g} m); building-building overlaps: "
        f"{summary['building_overlaps']}",
        fontsize=11,
    )
    zone = metric_crs.to_string() if hasattr(metric_crs, "to_string") else metric_crs
    ax.set_xlabel(f"Easting (m), {zone} (UTM zone 36N), north up")
    ax.set_ylabel("Northing (m)")
    ax.ticklabel_format(style="plain", useOffset=False)
    ax.tick_params(labelsize=7)
    legend = [
        Patch(facecolor="#cfd8dc", edgecolor="#607d8b", label="Building, no issue"),
        Patch(facecolor="#ffcc80", edgecolor="#e65100", label="Building on a road"),
        Patch(facecolor="#c62828", label="Part inside 1 m road buffer"),
        Line2D([0], [0], color="#9e9e9e", lw=1.2, label="Road centre-line (OSM)"),
    ]
    ax.legend(handles=legend, loc="upper left", fontsize=8, framealpha=0.9)
    ax.text(
        0.99,
        0.01,
        CREDIT + "\nProcessed with OVC, " + REPO_URL,
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=7,
        color="#424242",
        bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none"},
    )
    ax.annotate(
        "N",
        xy=(0.96, 0.93),
        xytext=(0.96, 0.85),
        xycoords="axes fraction",
        ha="center",
        fontsize=10,
        weight="bold",
        arrowprops={"arrowstyle": "-|>", "color": "black"},
    )
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OVC showcase: downtown Cairo building and road QC</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
  body { margin: 0; font-family: sans-serif; }
  header { padding: 8px 14px; background: #263238; color: #eceff1; }
  header h1 { font-size: 18px; margin: 0 0 4px 0; }
  header p { margin: 2px 0; font-size: 13px; }
  header a { color: #80cbc4; }
  #map { position: absolute; top: 92px; bottom: 0; left: 0; right: 0; }
  .legend { background: white; padding: 6px 8px; font-size: 12px; line-height: 18px; }
  .legend i { width: 14px; height: 14px; display: inline-block; margin-right: 6px; vertical-align: middle; }
</style>
</head>
<body>
<header>
  <h1>OVC showcase: downtown Cairo buildings on roads</h1>
  <p>OpenStreetMap building footprints checked with OVC for building-building overlaps
     and for parts lying within 1 m of a mapped road centre-line (computed in UTM zone 36N).</p>
  <p>Orange buildings are flagged, red patches show where they reach the road. Click a feature for details.
     Code: <a href="https://github.com/AmmarYasser455/ovc">github.com/AmmarYasser455/ovc</a></p>
</header>
<div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
  var map = L.map('map');
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map);

  function style(f) {
    var p = f.properties;
    if (p.layer === 'road') return { color: '#616161', weight: 2, opacity: 0.8 };
    if (p.layer === 'road_conflict') return { color: '#c62828', weight: 1, fillColor: '#c62828', fillOpacity: 0.9 };
    if (p.qc_status === 'ok') return { color: '#607d8b', weight: 1, fillColor: '#cfd8dc', fillOpacity: 0.5 };
    return { color: '#e65100', weight: 2, fillColor: '#ffcc80', fillOpacity: 0.8 };
  }
  function esc(v) {
    return String(v).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  function popup(f, layer) {
    var rows = Object.keys(f.properties).filter(function (k) {
      return f.properties[k] !== null;
    }).map(function (k) {
      return '<tr><th style="text-align:left">' + esc(k) + '</th><td>' + esc(f.properties[k]) + '</td></tr>';
    });
    layer.bindPopup('<table>' + rows.join('') + '</table>');
  }

  fetch('map.geojson').then(function (r) { return r.json(); }).then(function (data) {
    var order = { road: 0, building: 1, road_conflict: 2 };
    data.features.sort(function (a, b) { return order[a.properties.layer] - order[b.properties.layer]; });
    var layer = L.geoJSON(data, { style: style, onEachFeature: popup }).addTo(map);
    map.fitBounds(layer.getBounds());
  });

  var legend = L.control({ position: 'bottomleft' });
  legend.onAdd = function () {
    var d = L.DomUtil.create('div', 'legend');
    d.innerHTML = '<i style="background:#cfd8dc;border:1px solid #607d8b"></i>Building, no issue<br>' +
      '<i style="background:#ffcc80;border:1px solid #e65100"></i>Building on a road<br>' +
      '<i style="background:#c62828"></i>Part inside 1 m road buffer<br>' +
      '<i style="background:#616161;height:3px"></i>Road centre-line';
    return d;
  };
  legend.addTo(map);
</script>
</body>
</html>
"""


def main(out_dir: Path | str | None = None, data_dir: Path | str | None = None) -> dict:
    """Run the showcase and write its outputs; returns the summary numbers."""
    out = Path(out_dir) if out_dir is not None else HERE
    out.mkdir(parents=True, exist_ok=True)
    buildings, roads = load_data(Path(data_dir) if data_dir is not None else DATA_DIR)
    metric_crs, b_m, r_m, overlaps, conflicts = run_checks(buildings, roads)
    summary = summarize(buildings, roads, b_m, overlaps, conflicts)

    result = build_result(buildings, roads, b_m, overlaps, conflicts)
    with (out / "map.geojson").open("w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=None, separators=(",", ":"))
        fh.write("\n")

    (out / "index.html").write_text(INDEX_HTML, encoding="utf-8")

    try:
        import matplotlib  # noqa: F401
    except ImportError:
        print("matplotlib not installed; map.png skipped")
    else:
        write_png(out / "map.png", b_m, r_m, conflicts, metric_crs, summary)

    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    main()
