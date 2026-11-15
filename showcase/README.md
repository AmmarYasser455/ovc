# OVC showcase: downtown Cairo buildings on roads

## Question

Do OpenStreetMap building footprints in downtown Cairo (Wust al-Balad, around
Talaat Harb and Kasr El Nil streets) overlap each other, or reach onto the
centre-line of a mapped road?

## Data

- **Source:** OpenStreetMap, downloaded once through the Overpass API
  (`https://overpass-api.de/api/interpreter`) with `showcase/fetch_data.py`.
  Query: all `building=*` ways and all vehicle `highway=*` ways (motorway to
  residential, service, living_street and links) that touch the bounding box
  30.0440 N to 30.0510 N, 31.2380 E to 31.2460 E. Roads are returned in full,
  so some extend past the box.
- **License:** Open Database License (ODbL) 1.0,
  "(c) OpenStreetMap contributors", <https://www.openstreetmap.org/copyright>.
- **Date fetched:** 2026-11-15.
- **Files:** `data/cairo_downtown_buildings.geojson` (262 building polygons) and
  `data/cairo_downtown_roads.geojson` (163 road lines), GeoJSON in EPSG:4326
  (lon/lat), about 140 KB together. Only simple closed ways are kept as
  buildings; OSM multipolygon relations are not included.

## Method

1. Load both layers with GeoPandas (EPSG:4326).
2. Pick the local UTM zone with `ovc.core.crs.choose_utm_crs_from_gdf`
   (EPSG:32636, UTM zone 36N) and reproject both layers, so all lengths are in
   metres and areas in square metres.
3. `ovc.checks.overlap.find_building_overlaps` with
   `OverlapThresholds(min_intersection_area_m2=1.0)` (default ratios 0.9 for
   duplicates and 0.5 for partial overlaps).
4. `ovc.checks.road_conflict.find_buildings_on_roads` with
   `road_buffer_m=1.0` and `min_intersection_area_m2=1.0`: each road
   centre-line is buffered by 1 m and any building that covers at least 1 m² of
   that buffer is flagged. A 1 m buffer is deliberately narrow: a building that
   reaches it sits on, or right next to, the middle of the street.
5. Results are converted back to EPSG:4326 for `map.geojson`.

## Results

- 262 building footprints were checked; all 262 are valid geometries.
- **0** building-building overlaps of 1 m² or more were found.
- **9** buildings (3.4 %) reach a road centre-line, with a total of 41.5 m²
  inside the 1 m road buffers. The largest single case is 10.6 m², a building
  (OSM way 1501760134, label 9 on the map) on Kasr El Nil Street.
- 7 of the 9 cases involve residential-class streets and side alleys
  (for example Al Bostan Al Saedi Street, two buildings). These are likely
  places where either the footprint or the road line was traced a few metres
  off and are worth checking against imagery; some may also be passages under
  buildings that are not tagged as such in OSM.

| Map label | Building (OSM way) | Road (OSM way) | Road name | Area in buffer (m²) |
|---|---|---|---|---|
| 1 | 98246968 | 908353889 | Atafet Moustafa Abou Hif | 7.3 |
| 2 | 98246970 | 28718535 | Al Bostan Al Saedi Street | 5.6 |
| 3 | 98383698 | 1428264943 | Youssef Al Gendy Street | 1.1 |
| 4 | 768636301 | 28718535 | Al Bostan Al Saedi Street | 5.2 |
| 5 | 768638897 | 28718354 | Mohamed Mazloum Pasha Street | 1.6 |
| 6 | 768977209 | 28718394 | Mohamed Sedki Pasha Street | 1.3 |
| 7 | 768977225 | 908020234 | Atafet Al Daramly | 7.3 |
| 8 | 1116281358 | 1292673411 | (unnamed service road) | 1.6 |
| 9 | 1501760134 | 24749268 | Kasr El Nil Street | 10.6 |

These are flags for review, not confirmed errors in OpenStreetMap.

![map](map.png)

## Outputs

- [Web map (index.html)](index.html): open it through a local web server, for
  example `python -m http.server` in this folder, then
  <http://localhost:8000/index.html> (browsers block `fetch` of local files).
- [Notebook (showcase.ipynb)](showcase.ipynb): the same steps with the Python
  API, with saved outputs.
- [Result (map.geojson)](map.geojson): EPSG:4326 (RFC 7946). Features have a
  `layer` property: `building` (with `qc_status`, `area_m2`,
  `road_conflict_m2`, `map_label`), `road_conflict` (the part of a building
  inside a road buffer) and `road`.

## Rebuild

From the repository root, offline:

```bash
python showcase/make_showcase.py      # map.geojson, map.png, index.html
python showcase/build_notebook.py     # re-executes showcase.ipynb (needs nbclient, ipykernel)
```

`tests/test_showcase.py` checks that a fresh run reproduces the committed
`map.geojson`. To download the data again (needs internet; the data in OSM
changes over time, so the numbers above may change):

```bash
python showcase/fetch_data.py
```
