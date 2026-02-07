from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import folium
from folium.plugins import Fullscreen

# Color scheme for road QC errors
ROAD_QC_COLORS = {
    "disconnected_segment": "#e74c3c",  # Red
    "self_intersection": "#9b59b6",  # Purple
    "dangle": "#f39c12",  # Orange
    "road": "#3498db",  # Blue (for reference roads layer)
    "boundary": "#1e1e1e",  # Dark gray
}

COPYRIGHT = "© OVC — Overlap Violation Checker"


def _style_error(feature, error_type: str):
    """Return style dict for error features."""
    return {
        "color": ROAD_QC_COLORS.get(error_type, "#666666"),
        "weight": 4 if error_type != "road" else 2,
        "opacity": 0.8,
    }


def _point_style(error_type: str):
    """Return marker options for point errors."""
    return {
        "radius": 6,
        "fill": True,
        "fillColor": ROAD_QC_COLORS.get(error_type, "#666666"),
        "fillOpacity": 0.8,
        "color": "#ffffff",
        "weight": 2,
    }


def generate_road_qc_webmap(
    roads_gdf: gpd.GeoDataFrame,
    errors_gdf: gpd.GeoDataFrame,
    out_path: Path,
    boundary_gdf: gpd.GeoDataFrame | None = None,
    title: str = "Road QC Results",
) -> Path:
    """
    Generate an interactive web map showing road QC results.

    Parameters:
        roads_gdf: Roads GeoDataFrame (for reference layer)
        errors_gdf: Errors GeoDataFrame with error_type column
        out_path: Output path for HTML file
        boundary_gdf: Optional boundary GeoDataFrame
        title: Map title

    Returns:
        Path to generated HTML file
    """
    # Ensure WGS84
    if roads_gdf is not None and not roads_gdf.empty:
        roads_4326 = (
            roads_gdf.to_crs(4326)
            if (roads_gdf.crs is not None and roads_gdf.crs.to_epsg() != 4326)
            else roads_gdf
        )
        center = [
            roads_4326.geometry.centroid.y.mean(),
            roads_4326.geometry.centroid.x.mean(),
        ]
    else:
        center = [30.0, 31.0]  # Default: Egypt

    if errors_gdf is not None and not errors_gdf.empty:
        errors_4326 = (
            errors_gdf.to_crs(4326)
            if (errors_gdf.crs is not None and errors_gdf.crs.to_epsg() != 4326)
            else errors_gdf
        )
    else:
        errors_4326 = gpd.GeoDataFrame(
            {"road_id": [], "error_type": [], "geometry": []},
            geometry="geometry",
            crs=4326,
        )

    # Create map
    m = folium.Map(location=center, zoom_start=14, tiles="cartodbpositron")
    Fullscreen().add_to(m)

    # Add boundary layer if provided
    if boundary_gdf is not None and not boundary_gdf.empty:
        boundary_4326 = (
            boundary_gdf.to_crs(4326)
            if (boundary_gdf.crs is not None and boundary_gdf.crs.to_epsg() != 4326)
            else boundary_gdf
        )
        folium.GeoJson(
            boundary_4326,
            name="Boundary",
            style_function=lambda x: {
                "color": ROAD_QC_COLORS["boundary"],
                "weight": 2.5,
                "fillOpacity": 0.02,
            },
        ).add_to(m)

    # Add roads layer (reference)
    if roads_gdf is not None and not roads_gdf.empty:
        roads_layer = folium.FeatureGroup(name="Roads (reference)", show=True)
        folium.GeoJson(
            (
                roads_4326[["road_id", "geometry"]]
                if "road_id" in roads_4326.columns
                else roads_4326[["geometry"]]
            ),
            style_function=lambda x: {
                "color": ROAD_QC_COLORS["road"],
                "weight": 2,
                "opacity": 0.6,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=["road_id"] if "road_id" in roads_4326.columns else [],
                aliases=["Road ID"] if "road_id" in roads_4326.columns else [],
            ),
        ).add_to(roads_layer)
        roads_layer.add_to(m)

    # Add error layers by type
    if not errors_4326.empty and "error_type" in errors_4326.columns:
        error_types = errors_4326["error_type"].unique()

        for error_type in error_types:
            error_subset = errors_4326[errors_4326["error_type"] == error_type]
            layer = folium.FeatureGroup(
                name=f"{error_type.replace('_', ' ').title()} ({len(error_subset)})"
            )

            # Check if points or lines
            geom_types = error_subset.geometry.type.unique()

            if "Point" in geom_types or "MultiPoint" in geom_types:
                # Add as circle markers
                for _, row in error_subset.iterrows():
                    geom = row.geometry
                    if geom.geom_type == "Point":
                        folium.CircleMarker(
                            location=[geom.y, geom.x],
                            popup=f"Road: {row.get('road_id', 'N/A')}<br>Error: {error_type}",
                            **_point_style(error_type),
                        ).add_to(layer)
            else:
                # Add as GeoJson lines
                folium.GeoJson(
                    error_subset[["road_id", "error_type", "geometry"]],
                    style_function=lambda x, et=error_type: _style_error(x, et),
                    tooltip=folium.GeoJsonTooltip(
                        fields=["road_id", "error_type"],
                        aliases=["Road ID", "Error Type"],
                    ),
                ).add_to(layer)

            layer.add_to(m)

    # Add legend with copyright
    legend_html = f"""
    <div style="
        position: fixed;
        bottom: 30px;
        left: 30px;
        z-index: 1000;
        background-color: white;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        font-family: Arial, sans-serif;
        font-size: 13px;
        max-width: 220px;
    ">
        <div style="font-weight: bold; margin-bottom: 10px; font-size: 14px;">{title}</div>
        <div style="margin-bottom: 6px;">
            <span style="display: inline-block; width: 18px; height: 18px; background: {ROAD_QC_COLORS['road']}; margin-right: 8px; vertical-align: middle; border-radius: 2px;"></span>
            Roads (reference)
        </div>
        <div style="margin-bottom: 6px;">
            <span style="display: inline-block; width: 18px; height: 18px; background: {ROAD_QC_COLORS['disconnected_segment']}; margin-right: 8px; vertical-align: middle; border-radius: 2px;"></span>
            Disconnected Segment
        </div>
        <div style="margin-bottom: 6px;">
            <span style="display: inline-block; width: 18px; height: 18px; background: {ROAD_QC_COLORS['self_intersection']}; margin-right: 8px; vertical-align: middle; border-radius: 2px;"></span>
            Self Intersection
        </div>
        <div style="margin-bottom: 6px;">
            <span style="display: inline-block; width: 18px; height: 18px; background: {ROAD_QC_COLORS['dangle']}; margin-right: 8px; vertical-align: middle; border-radius: 2px;"></span>
            Dangle (dead end)
        </div>
        <hr style="margin: 10px 0; border: none; border-top: 1px solid #e5e7eb;">
        <div style="font-size: 11px; color: #6b7280;">{COPYRIGHT}</div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    # Add layer control
    folium.LayerControl(collapsed=False).add_to(m)

    # Save
    out_path.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(out_path))

    return out_path
