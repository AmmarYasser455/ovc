"""Download the showcase data once from the OpenStreetMap Overpass API.

This script is NOT needed to rebuild the showcase: its output is committed
under ``showcase/data/``. It is kept to document exactly how the data was
obtained.

Data (c) OpenStreetMap contributors, available under the Open Database
License (ODbL) 1.0, https://www.openstreetmap.org/copyright

Usage (from the repository root, needs internet)::

    python showcase/fetch_data.py
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)

# Downtown Cairo (Wust al-Balad), south, west, north, east in degrees (lat/lon
# order as required by the Overpass bbox filter).
BBOX = (30.0440, 31.2380, 30.0510, 31.2460)

ROAD_TYPES = (
    "motorway|trunk|primary|secondary|tertiary|unclassified|residential|"
    "service|living_street|motorway_link|trunk_link|primary_link|"
    "secondary_link|tertiary_link"
)

DATA_DIR = Path(__file__).resolve().parent / "data"


def _query() -> str:
    s, w, n, e = BBOX
    bb = f"{s},{w},{n},{e}"
    return (
        "[out:json][timeout:90];"
        f'(way["building"]({bb});'
        f'way["highway"~"^({ROAD_TYPES})$"]({bb}););'
        "out tags geom;"
    )


def _coords(way):
    # Overpass returns {"lat":..., "lon":...}; GeoJSON wants [lon, lat].
    return [[round(p["lon"], 7), round(p["lat"], 7)] for p in way["geometry"]]


def _ring_ccw(ring):
    area2 = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring[:-1], ring[1:]))
    return ring if area2 > 0 else ring[::-1]


def main() -> None:
    body = urllib.parse.urlencode({"data": _query()}).encode("utf-8")
    payload = None
    for url in OVERPASS_URLS:
        req = urllib.request.Request(
            url,
            data=body,
            headers={"User-Agent": "ovc-showcase/1.0", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            print(f"Fetched from {url}")
            break
        except OSError as exc:  # HTTPError/URLError are OSError subclasses
            print(f"{url}: {exc}")
    if payload is None:
        raise SystemExit("All Overpass endpoints failed")

    buildings, roads = [], []
    for el in payload.get("elements", []):
        if el.get("type") != "way" or "geometry" not in el:
            continue
        tags = el.get("tags", {})
        coords = _coords(el)
        if "building" in tags:
            if len(coords) < 4 or coords[0] != coords[-1]:
                continue
            buildings.append(
                {
                    "type": "Feature",
                    "properties": {
                        "osm_id": el["id"],
                        "building": tags.get("building"),
                        "name": tags.get("name"),
                    },
                    "geometry": {"type": "Polygon", "coordinates": [_ring_ccw(coords)]},
                }
            )
        elif "highway" in tags:
            roads.append(
                {
                    "type": "Feature",
                    "properties": {
                        "osm_id": el["id"],
                        "highway": tags.get("highway"),
                        "name": tags.get("name:en") or tags.get("name"),
                        "bridge": tags.get("bridge"),
                        "tunnel": tags.get("tunnel"),
                        "covered": tags.get("covered"),
                        "layer": tags.get("layer"),
                    },
                    "geometry": {"type": "LineString", "coordinates": coords},
                }
            )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name, feats in (("buildings", buildings), ("roads", roads)):
        out = DATA_DIR / f"cairo_downtown_{name}.geojson"
        with out.open("w", encoding="utf-8") as fh:
            json.dump(
                {"type": "FeatureCollection", "features": feats},
                fh,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        print(f"{out}: {len(feats)} features")


if __name__ == "__main__":
    main()
