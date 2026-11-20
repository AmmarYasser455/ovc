"""Write and execute showcase/showcase.ipynb (outputs are saved in the file).

Usage, from the repository root::

    python showcase/build_notebook.py

Needs nbformat, nbclient and ipykernel.
"""

import os
import tempfile
from pathlib import Path

import nbformat
from nbclient import NotebookClient

HERE = Path(__file__).resolve().parent

CELLS = [
    (
        "md",
        "# OVC showcase: downtown Cairo buildings on roads\n\n"
        "**Question:** do OpenStreetMap building footprints in downtown Cairo "
        "overlap each other, or reach onto the centre-line of a mapped road?\n\n"
        "Data: (c) OpenStreetMap contributors, ODbL 1.0, fetched with the Overpass API "
        "(see `README.md` in this folder).",
    ),
    (
        "code",
        "import sys\n"
        "from pathlib import Path\n\n"
        "ROOT = Path.cwd().parent if Path.cwd().name == 'showcase' else Path.cwd()\n"
        "sys.path.insert(0, str(ROOT))\n\n"
        "import geopandas as gpd\n"
        "import matplotlib.pyplot as plt\n"
        "from ovc.checks.overlap import OverlapThresholds, find_building_overlaps\n"
        "from ovc.checks.road_conflict import find_buildings_on_roads\n"
        "from ovc.core.crs import choose_utm_crs_from_gdf",
    ),
    ("md", "## 1. Load the data (GeoJSON, EPSG:4326, lon/lat)"),
    (
        "code",
        "data = ROOT / 'showcase' / 'data'\n"
        "buildings = gpd.read_file(data / 'cairo_downtown_buildings.geojson')\n"
        "roads = gpd.read_file(data / 'cairo_downtown_roads.geojson')\n"
        "buildings['bldg_id'] = buildings['osm_id'].astype('int64')\n"
        "roads['osmid'] = roads['osm_id'].astype('int64')\n"
        "print(buildings.crs, len(buildings), 'buildings,', len(roads), 'roads')\n"
        "roads['highway'].value_counts()",
    ),
    (
        "md",
        "## 2. Project to the local UTM zone (metres) and run the OVC checks",
    ),
    (
        "code",
        "metric = choose_utm_crs_from_gdf(buildings)\n"
        "b_m, r_m = buildings.to_crs(metric), roads.to_crs(metric)\n"
        "print('Metric CRS:', metric)\n\n"
        "overlaps = find_building_overlaps(b_m, OverlapThresholds(min_intersection_area_m2=1.0))\n"
        "conflicts = find_buildings_on_roads(b_m, r_m, road_buffer_m=1.0, "
        "min_intersection_area_m2=1.0)\n"
        "print('Invalid footprints:', int((~b_m.is_valid).sum()))\n"
        "print('Building-building overlaps:', len(overlaps))\n"
        "print('Buildings within 1 m of a road centre-line:', conflicts['bldg_id'].nunique())",
    ),
    ("md", "## 3. Inspect the flagged buildings"),
    (
        "code",
        "names = roads.set_index('osmid')[['name', 'highway']]\n"
        "table = conflicts.drop(columns='geometry').join(names, on='osmid')\n"
        "table = table.sort_values('bldg_id').reset_index(drop=True)\n"
        "table.index = table.index + 1\n"
        "table['inter_area_m2'] = table['inter_area_m2'].round(1)\n"
        "table[['bldg_id', 'osmid', 'name', 'highway', 'inter_area_m2']]",
    ),
    ("md", "## 4. Map (UTM zone 36N, north up)"),
    (
        "code",
        "fig, ax = plt.subplots(figsize=(8, 8))\n"
        "r_m.plot(ax=ax, color='#9e9e9e', linewidth=1)\n"
        "b_m.plot(ax=ax, facecolor='#cfd8dc', edgecolor='#607d8b', linewidth=0.4)\n"
        "b_m[b_m['bldg_id'].isin(conflicts['bldg_id'])].plot(\n"
        "    ax=ax, facecolor='#ffcc80', edgecolor='#e65100')\n"
        "conflicts.plot(ax=ax, color='#c62828')\n"
        "ax.set_title('Downtown Cairo: OSM buildings reaching a road centre-line')\n"
        "ax.set_xlabel(f'Easting (m), {metric}'); ax.set_ylabel('Northing (m)')\n"
        "ax.text(0.99, 0.01, 'Data (c) OpenStreetMap contributors, ODbL',\n"
        "        transform=ax.transAxes, ha='right', fontsize=7)\n"
        "plt.show()",
    ),
]


def main() -> None:
    # Keep matplotlib cache warnings (with local paths) out of saved outputs.
    os.environ.setdefault("MPLCONFIGDIR", tempfile.mkdtemp(prefix="mpl-"))
    nb = nbformat.v4.new_notebook()
    nb.metadata["kernelspec"] = {
        "name": "python3",
        "display_name": "Python 3",
        "language": "python",
    }
    for kind, src in CELLS:
        make = (
            nbformat.v4.new_markdown_cell if kind == "md" else nbformat.v4.new_code_cell
        )
        nb.cells.append(make(src))
    NotebookClient(
        nb,
        timeout=300,
        kernel_name="python3",
        resources={"metadata": {"path": str(HERE)}},
    ).execute()
    nbformat.write(nb, HERE / "showcase.ipynb")


if __name__ == "__main__":
    main()
