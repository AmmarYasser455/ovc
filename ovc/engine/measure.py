"""Choose the CRS that geometry operations and areas are computed in.

Areas are always reported in square metres. They are planar areas in a
projected CRS whose local area distortion is small:

* If the layer is in a projected CRS that distorts area by at most
  ``MAX_AREAL_DISTORTION`` over the layer's extent (UTM zones and national
  grids used where they are meant to be used), OVC works in that CRS, so the
  numbers match what the analyst measures in their GIS.
* If the layer is geographic (degrees), or in a projection that distorts area
  more than that (Web Mercator away from the equator), OVC reprojects in
  memory to the WGS 84 / UTM zone of the layer's centre, or to polar
  stereographic beyond 84N / 80S.

Square degrees are never reported as square metres.
"""

from __future__ import annotations

import math

from pyproj import CRS, Proj, Transformer

from ovc.engine.model import Measurement, crs_label

MAX_AREAL_DISTORTION = 0.01  # 1 %


def utm_crs_for(lon: float, lat: float) -> CRS:
    """WGS 84 / UTM zone containing ``lon``/``lat`` (UPS near the poles)."""
    if lat > 84:
        return CRS.from_epsg(32661)
    if lat < -80:
        return CRS.from_epsg(32761)
    zone = int((lon + 180) // 6) + 1
    zone = max(1, min(zone, 60))
    return CRS.from_epsg((32600 if lat >= 0 else 32700) + zone)


def _sample_points(bounds):
    minx, miny, maxx, maxy = bounds
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    return [(cx, cy), (minx, miny), (minx, maxy), (maxx, miny), (maxx, maxy)]


def areal_distortion(crs: CRS, bounds) -> float | None:
    """Largest ``|areal scale - 1|`` of a projected CRS over ``bounds``.

    Returns None when it cannot be evaluated (for example engineering CRSs).
    """
    try:
        geodetic = crs.geodetic_crs
        to_geo = Transformer.from_crs(crs, geodetic, always_xy=True)
        proj = Proj(crs)
        worst = 0.0
        for x, y in _sample_points(bounds):
            lon, lat = to_geo.transform(x, y)
            scale = proj.get_factors(lon, lat).areal_scale
            if not math.isfinite(scale):
                return None
            worst = max(worst, abs(scale - 1.0))
        return worst
    except Exception:
        return None


def choose_measurement(source_crs, bounds) -> Measurement:
    """Pick the working CRS for a layer with ``source_crs`` and ``bounds``.

    ``bounds`` is ``(minx, miny, maxx, maxy)`` in ``source_crs``.
    """
    crs = CRS.from_user_input(source_crs)

    if crs.is_projected:
        unit_to_m = float(crs.axis_info[0].unit_conversion_factor or 1.0)
        distortion = areal_distortion(crs, bounds)
        if distortion is None or distortion <= MAX_AREAL_DISTORTION:
            detail = (
                "area distortion not evaluated"
                if distortion is None
                else f"local area distortion {distortion * 100:.2f}%"
            )
            unit = crs.axis_info[0].unit_name
            convert = "" if unit_to_m == 1.0 else f", converted from {unit} to metres"
            return Measurement(
                source_crs=crs,
                working_crs=crs,
                unit_to_m=unit_to_m,
                method=(
                    f"Planar area in the layer's CRS, {crs_label(crs)} "
                    f"({detail}{convert})."
                ),
                reprojected=False,
            )
        why = (
            f"{crs_label(crs)} distorts area by {distortion * 100:.1f}% "
            "over this layer"
        )
    elif crs.is_geographic:
        why = f"{crs_label(crs)} is in degrees"
    else:
        # Engineering / local CRS: no link to the Earth, trust its units.
        unit_to_m = 1.0
        try:
            unit_to_m = float(crs.axis_info[0].unit_conversion_factor or 1.0)
        except Exception:
            pass
        return Measurement(
            source_crs=crs,
            working_crs=crs,
            unit_to_m=unit_to_m,
            method=f"Planar area in the layer's local CRS, {crs_label(crs)}.",
            reprojected=False,
        )

    to_wgs84 = Transformer.from_crs(crs, CRS.from_epsg(4326), always_xy=True)
    minx, miny, maxx, maxy = bounds
    lon, lat = to_wgs84.transform((minx + maxx) / 2, (miny + maxy) / 2)
    if not (math.isfinite(lon) and math.isfinite(lat)):
        raise ValueError(
            f"Coordinates do not fit {crs_label(crs)}; check the layer's CRS."
        )
    working = utm_crs_for(lon, lat)
    return Measurement(
        source_crs=crs,
        working_crs=working,
        unit_to_m=1.0,
        method=(
            f"Planar area in {crs_label(working)}, chosen from the layer's "
            f"centre because {why}. Reprojected in memory only."
        ),
        reprojected=True,
    )
