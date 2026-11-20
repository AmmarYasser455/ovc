"""Generate the tiny walkthrough dataset (public domain, CC0).

Writes three GeoJSON files (EPSG:4326) next to this script:

* buildings.geojson - 8 rectangular buildings. Two of them overlap on purpose
  (B5 and B6 share a 4 m x 10 m strip), and one (B8) is drawn across a road.
* roads.geojson     - 2 straight road centrelines.
* boundary.geojson  - the study-area polygon.

Only the Python standard library is used, so the data can be rebuilt anywhere:

    python make_data.py
"""

import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORIGIN_LON, ORIGIN_LAT = (
    0.0005,
    0.0005,
)  # "Null Island": open ocean, so nobody mistakes it for real buildings
M_PER_DEG_LAT = 110_574.0
M_PER_DEG_LON = 111_320.0 * math.cos(math.radians(ORIGIN_LAT))


def lonlat(x_m, y_m):
    """Local metres (east, north) from the origin -> [lon, lat]."""
    return [
        round(ORIGIN_LON + x_m / M_PER_DEG_LON, 7),
        round(ORIGIN_LAT + y_m / M_PER_DEG_LAT, 7),
    ]


def rect(x, y, w, h):
    ring = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
    return {"type": "Polygon", "coordinates": [[lonlat(*p) for p in ring]]}


def line(*pts):
    return {"type": "LineString", "coordinates": [lonlat(*p) for p in pts]}


def collection(features):
    return {"type": "FeatureCollection", "features": features}


def feature(geom, **props):
    return {"type": "Feature", "properties": props, "geometry": geom}


BUILDINGS = [
    # id, x, y, width, height (metres), note
    ("B1", 5, 25, 12, 10, "clean"),
    ("B2", 22, 25, 10, 10, "clean"),
    ("B3", 5, 42, 12, 12, "clean"),
    ("B4", 22, 42, 14, 12, "clean"),
    ("B5", 42, 25, 12, 10, "overlaps B6"),
    ("B6", 50, 25, 12, 10, "overlaps B5"),
    ("B7", 42, 42, 12, 12, "clean"),
    ("B8", 66, 6, 10, 12, "drawn across the road"),
]

ROADS = [
    ("R1", [(0, 12), (90, 12)], "main road, east-west"),
    ("R2", [(39, 12), (39, 60)], "side road, north-south"),
]


def main():
    buildings = [
        feature(rect(x, y, w, h), id=i, note=n) for i, x, y, w, h, n in BUILDINGS
    ]
    roads = [feature(line(*pts), id=i, note=n) for i, pts, n in ROADS]
    boundary = [feature(rect(0, 0, 90, 62), name="study area")]
    for name, feats in (
        ("buildings", buildings),
        ("roads", roads),
        ("boundary", boundary),
    ):
        path = HERE / f"{name}.geojson"
        path.write_text(
            json.dumps(collection(feats), indent=1) + "\n", encoding="utf-8"
        )
        print(f"wrote {path.name}: {len(feats)} features")


if __name__ == "__main__":
    main()
