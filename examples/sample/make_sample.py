"""Rebuild the tiny dataset bundled with OVC (``ovc/sample_data/ovc_sample.gpkg``).

Synthetic, public-domain geometry in EPSG:32636 (WGS 84 / UTM zone 36N), so
every planted problem has an exact area in square metres.

    python examples/sample/make_sample.py
"""

from pathlib import Path

import geopandas as gpd
from shapely.geometry import Polygon, box

OUT = Path(__file__).resolve().parents[2] / "ovc" / "sample_data" / "ovc_sample.gpkg"
CRS = "EPSG:32636"
X0, Y0 = 330_000, 3_320_000  # metres; south-west corner of the block


def rect(x0, y0, x1, y1):
    return box(X0 + x0, Y0 + y0, X0 + x1, Y0 + y1)


def ring(x0, y0, x1, y1):
    return list(rect(x0, y0, x1, y1).exterior.coords)


def buildings():
    courtyard = Polygon(ring(2, 18, 22, 34), holes=[ring(7, 22, 17, 30)])
    rows = [
        ("B1", "house", rect(2, 2, 12, 12)),
        ("B2", "house, drawn 2 m into B1", rect(10, 4, 20, 12)),
        ("B3", "house", rect(24, 2, 34, 12)),
        ("B4", "copy of B3", rect(24, 2, 34, 12)),
        ("B5", "warehouse", rect(38, 2, 52, 14)),
        ("B6", "shed drawn inside B5", rect(40, 4, 43, 7)),
        ("B7", "courtyard building", courtyard),
        ("B8", "shares a wall with B7", rect(22, 18, 32, 30)),
        ("B9", "house", rect(38, 18, 52, 32)),
    ]
    return gpd.GeoDataFrame(
        {"bldg_ref": [r[0] for r in rows], "note": [r[1] for r in rows]},
        geometry=[r[2] for r in rows],
        crs=CRS,
    )


def parcels():
    rows = [
        ("P1", rect(0, 0, 20, 15)),
        ("P2", rect(20, 0, 40, 15)),
        ("P3", rect(38, 0, 60, 15)),  # 2 m x 15 m into P2
        ("P4", rect(0, 15, 25, 30)),
        ("P5", rect(35, 15, 60, 30)),
        ("P6", rect(0, 30, 20, 40)),
        ("P7", rect(20, 30, 40, 40)),
        ("P8", rect(41, 30, 60, 40)),  # leaves a 1 m x 10 m strip uncovered
    ]
    return gpd.GeoDataFrame(
        {"parcel_ref": [r[0] for r in rows]}, geometry=[r[1] for r in rows], crs=CRS
    )


def block():
    """The area the parcels must cover: a 60 m x 40 m block minus a pond."""
    geom = Polygon(ring(0, 0, 60, 40), holes=[ring(25, 15, 35, 30)])
    return gpd.GeoDataFrame({"name": ["Block 12"]}, geometry=[geom], crs=CRS)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    buildings().to_file(OUT, layer="buildings", driver="GPKG")
    parcels().to_file(OUT, layer="parcels", driver="GPKG")
    block().to_file(OUT, layer="block", driver="GPKG")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
