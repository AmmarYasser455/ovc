from __future__ import annotations

from pathlib import Path
import folium
import geopandas as gpd


def _style_boundary(_):
    return {"color": "#1e1e1e", "weight": 2.5, "fillOpacity": 0.02}


def _style_roads(_):
    return {"color": "#8b4513", "weight": 1.4, "fillOpacity": 0.0}


def _style_buildings_clean(_):
    return {"color": "#90ee90", "weight": 1, "fillOpacity": 0.4}


def _style_overlap_errors(_):
    return {"color": "#ff0000", "weight": 2, "fillOpacity": 0.6}


def _style_error_buildings(feature):
    et = (feature.get("properties") or {}).get("error_type", "")
    color = "#ff0000"
    if et == "building_on_road":
        color = "#ffff00"
    elif et == "outside_boundary":
        color = "#ff8c00"
    return {"color": color, "weight": 2, "fillOpacity": 0.6}


def _add_layer_control(m: folium.Map):
    folium.LayerControl(collapsed=False).add_to(m)
    css = """
    <style>
      .leaflet-control-layers {
        position: fixed !important;
        top: 12px !important;
        right: 12px !important;
        left: auto !important;
        z-index: 99999 !important;
      }
      .leaflet-control-layers-expanded {
        max-height: 70vh;
        overflow: auto;
      }
    </style>
    """
    m.get_root().header.add_child(folium.Element(css))


def write_webmap(
    html_path: Path,
    boundary_4326: gpd.GeoDataFrame,
    roads_4326: gpd.GeoDataFrame,
    buildings_clean_4326: gpd.GeoDataFrame,
    overlap_buildings_4326: gpd.GeoDataFrame,
    errors_4326: gpd.GeoDataFrame,
    attribution_text: str,
):
    html_path.parent.mkdir(parents=True, exist_ok=True)

    b = boundary_4326.to_crs(4326)
    c = b.unary_union.centroid

    m = folium.Map(
        location=[float(c.y), float(c.x)],
        zoom_start=12,
        tiles="cartodbpositron",
        attr=attribution_text,
        prefer_canvas=True,
    )

    folium.GeoJson(
        b,
        name="Boundary",
        style_function=_style_boundary,
    ).add_to(m)

    if roads_4326 is not None and not roads_4326.empty:
        folium.GeoJson(
            roads_4326.to_crs(4326),
            name="Roads",
            style_function=_style_roads,
        ).add_to(m)

    if buildings_clean_4326 is not None and not buildings_clean_4326.empty:
        folium.GeoJson(
            buildings_clean_4326.to_crs(4326),
            name="Buildings clean",
            style_function=_style_buildings_clean,
        ).add_to(m)

    if overlap_buildings_4326 is not None and not overlap_buildings_4326.empty:
        folium.GeoJson(
            overlap_buildings_4326.to_crs(4326),
            name="Overlap errors",
            style_function=_style_overlap_errors,
            tooltip=folium.GeoJsonTooltip(
                fields=["osmid", "bldg_id", "error_class"],
                aliases=["osmid:", "bldg_id:", "type:"],
                sticky=True,
            ),
        ).add_to(m)

    if errors_4326 is not None and not errors_4326.empty:
        buildings_on_road = errors_4326[
            errors_4326["error_type"] == "building_on_road"
        ].copy()
        if not buildings_on_road.empty:
            folium.GeoJson(
                buildings_on_road.to_crs(4326),
                name="Buildings on road",
                style_function=_style_error_buildings,
                tooltip=folium.GeoJsonTooltip(
                    fields=["osmid", "bldg_id", "error_type", "error_class"],
                    aliases=["osmid:", "bldg_id:", "error_type:", "error_class:"],
                    sticky=True,
                ),
            ).add_to(m)

        outside_boundary = errors_4326[
            errors_4326["error_type"] == "outside_boundary"
        ].copy()
        if not outside_boundary.empty:
            folium.GeoJson(
                outside_boundary.to_crs(4326),
                name="Outside boundary",
                style_function=_style_error_buildings,
                tooltip=folium.GeoJsonTooltip(
                    fields=["osmid", "bldg_id", "error_type", "error_class"],
                    aliases=["osmid:", "bldg_id:", "error_type:", "error_class:"],
                    sticky=True,
                ),
            ).add_to(m)

    legend = f"""
    <div style="position:fixed;bottom:22px;left:22px;z-index:9999;
    background:white;padding:12px;border-radius:8px;
    box-shadow:0 0 15px rgba(0,0,0,0.2);font-size:13px;max-width:360px;">
      <b>OVC – Classic view</b><br><br>
      <div><span style="background:#ff0000;width:12px;height:12px;display:inline-block;"></span> overlap errors</div>
      <div><span style="background:#ffff00;width:12px;height:12px;display:inline-block;"></span> building on road</div>
      <div><span style="background:#ff8c00;width:12px;height:12px;display:inline-block;"></span> outside boundary</div>
      <div><span style="background:#90ee90;width:12px;height:12px;display:inline-block;"></span> clean buildings</div>
      <hr style="margin:10px 0;">
      <div style="font-size:11px;color:#374151;">{attribution_text}</div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend))
    _add_layer_control(m)
    m.save(html_path)
