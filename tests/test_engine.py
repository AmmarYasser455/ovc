"""Deterministic fixtures for the topology engine (ovc.engine).

All fixtures use EPSG:32636 (metres) with a real-world offset, so every
expected area is exact.
"""

import geopandas as gpd
import pytest
import shapely
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box

from ovc.engine import check_polygons

X0, Y0 = 330_000, 3_320_000
CRS = "EPSG:32636"


def rect(x0, y0, x1, y1):
    return box(X0 + x0, Y0 + y0, X0 + x1, Y0 + y1)


def layer(geoms, crs=CRS, **cols):
    return gpd.GeoDataFrame(cols, geometry=list(geoms), crs=crs)


def rows(result, issue_type=None):
    f = result.findings
    if issue_type:
        f = f[f["issue_type"] == issue_type]
    return f.reset_index(drop=True)


BLOCK = layer([rect(0, 0, 10, 10)])


# --- the 10 m x 10 m block ---------------------------------------------


def test_gap_of_10_m2_touching_the_boundary():
    feats = layer([rect(0, 0, 4, 10), rect(5, 0, 10, 10)])
    r = check_polygons(feats, check_gaps=True, coverage=BLOCK)
    assert r.status == "issues"
    assert r.counts_by_type() == {"gap": 1}
    gap = rows(r).iloc[0]
    assert gap["area_m2"] == 10.0
    assert gap.geometry.equals(rect(4, 0, 5, 10))
    assert "touches the edge" in gap["reason"]
    assert gap["related_fids"] == "0, 1"
    assert r.checks["gap"].status == "complete"


def test_overlap_of_10_m2_and_no_gap():
    feats = layer([rect(0, 0, 4, 10), rect(3, 0, 10, 10)])
    r = check_polygons(feats, check_gaps=True, coverage=BLOCK)
    assert r.counts_by_type() == {"overlap": 1}
    ov = rows(r).iloc[0]
    assert (ov["fid_a"], ov["fid_b"]) == (0, 1)
    assert ov["area_m2"] == 10.0
    assert ov.geometry.equals(rect(3, 0, 4, 10))
    assert r.checks["gap"].count == 0


def test_shared_edge_is_neither_overlap_nor_gap():
    feats = layer([rect(0, 0, 4, 10), rect(4, 0, 10, 10)])
    r = check_polygons(feats, check_gaps=True, coverage=BLOCK)
    assert r.status == "clean"
    assert r.ok
    assert len(r.findings) == 0


def test_shared_vertex_is_not_an_overlap():
    r = check_polygons(layer([rect(0, 0, 4, 4), rect(4, 4, 8, 8)]))
    assert r.status == "clean"


# --- gaps are opt-in and need an explicit coverage area -------------------


def test_courtyard_is_not_reported_when_gap_check_is_off():
    courtyard = Polygon(
        rect(0, 0, 10, 10).exterior.coords, holes=[rect(3, 3, 7, 7).exterior.coords]
    )
    r = check_polygons(layer([courtyard, rect(12, 0, 20, 10)]))
    assert r.status == "clean"
    assert r.checks["gap"].requested is False


def test_hole_in_the_coverage_boundary_is_not_a_gap():
    block_with_pond = Polygon(
        rect(0, 0, 10, 10).exterior.coords, holes=[rect(4, 4, 6, 6).exterior.coords]
    )
    ring_building = Polygon(
        rect(0, 0, 10, 10).exterior.coords, holes=[rect(4, 4, 6, 6).exterior.coords]
    )
    r = check_polygons(
        layer([ring_building]), check_gaps=True, coverage=layer([block_with_pond])
    )
    assert r.status == "clean"
    # the same building against a solid block leaves the 4 m² hole uncovered
    r = check_polygons(layer([ring_building]), check_gaps=True, coverage=BLOCK)
    gap = rows(r, "gap").iloc[0]
    assert gap["area_m2"] == 4.0
    assert "enclosed" in gap["reason"]


def test_exclusion_layer_removes_area_from_the_coverage():
    feats = layer([rect(0, 0, 4, 10), rect(5, 0, 10, 10)])
    street = layer([rect(4, 0, 5, 6)])
    r = check_polygons(feats, check_gaps=True, coverage=BLOCK, exclusions=street)
    gap = rows(r, "gap")
    assert len(gap) == 1
    assert gap.iloc[0]["area_m2"] == 4.0  # only y 6-10 is left


def test_each_connected_gap_is_reported_separately():
    feats = layer([rect(1, 0, 9, 10)])
    r = check_polygons(feats, check_gaps=True, coverage=BLOCK)
    assert sorted(rows(r, "gap")["area_m2"]) == [10.0, 10.0]


def test_gap_check_without_coverage_explains_and_keeps_overlaps():
    feats = layer([rect(0, 0, 4, 10), rect(3, 0, 10, 10)])
    r = check_polygons(feats, check_gaps=True)
    assert r.status == "partial"
    assert r.checks["gap"].status == "not_run"
    assert "area that should be fully covered" in r.checks["gap"].message
    assert "bounding box" in r.checks["gap"].message
    assert r.checks["overlap"].status == "complete"
    assert r.counts_by_type() == {"overlap": 1}


def test_coverage_in_another_crs_is_reprojected():
    feats = layer([rect(0, 0, 4, 10), rect(5, 0, 10, 10)])
    r = check_polygons(feats, check_gaps=True, coverage=BLOCK.to_crs(4326))
    assert rows(r, "gap").iloc[0]["area_m2"] == pytest.approx(10.0, abs=1e-4)


def test_coverage_without_crs_or_polygons_is_not_run():
    feats = layer([rect(0, 0, 10, 10)])
    no_crs = gpd.GeoDataFrame(geometry=[rect(0, 0, 10, 10)])
    r = check_polygons(feats, check_gaps=True, coverage=no_crs)
    assert r.status == "partial"
    assert "no CRS" in r.checks["gap"].message
    lines = layer([LineString([(X0, Y0), (X0 + 5, Y0)])])
    r = check_polygons(feats, check_gaps=True, coverage=lines)
    assert "no polygons" in r.checks["gap"].message


def test_features_far_from_the_coverage_raise_a_warning():
    feats = layer([rect(500, 500, 510, 510)])
    r = check_polygons(feats, check_gaps=True, coverage=BLOCK)
    assert rows(r, "gap").iloc[0]["area_m2"] == 100.0
    assert any("No feature lies in the coverage area" in w for w in r.warnings)


# --- overlap classes -------------------------------------------------------


def test_identical_polygons_are_duplicates_and_each_pair_is_reported_once():
    a = rect(0, 0, 10, 10)
    same_other_start = Polygon(
        list(a.exterior.coords)[2:-1] + list(a.exterior.coords)[:2]
    )
    r = check_polygons(layer([a, a, same_other_start]))
    dup = rows(r, "duplicate")
    assert sorted(zip(dup["fid_a"], dup["fid_b"])) == [(0, 1), (0, 2), (1, 2)]
    assert set(dup["area_m2"]) == {100.0}
    assert r.checks["overlap"].count == 3  # duplicates count as overlap findings


def test_feature_inside_another_is_containment():
    r = check_polygons(layer([rect(0, 0, 20, 20), rect(5, 5, 7, 7)]))
    assert r.counts_by_type() == {"containment": 1}
    c = rows(r).iloc[0]
    assert c["area_m2"] == 4.0
    assert c["overlap_ratio"] == 1.0
    assert "FID 1 lies inside FID 0" in c["reason"]


def test_multipart_feature_overlap_is_one_finding_with_the_total_area():
    multi = MultiPolygon([rect(0, 0, 4, 4), rect(10, 0, 14, 4)])
    bar = rect(3, 1, 11, 3)  # 1 m x 2 m into each part
    r = check_polygons(layer([multi, bar]))
    ov = rows(r, "overlap")
    assert len(ov) == 1
    assert ov.iloc[0]["area_m2"] == 4.0
    assert len(ov.iloc[0].geometry.geoms) == 2


def test_overlap_threshold_includes_equality_and_zero_means_any_area():
    feats = layer([rect(0, 0, 4, 1), rect(3.5, 0, 8, 1)])  # 0.5 m² overlap
    assert len(check_polygons(feats, min_overlap_area_m2=0.5).findings) == 1
    assert check_polygons(feats, min_overlap_area_m2=0.51).status == "clean"
    tiny = layer([rect(0, 0, 4, 1), rect(3.999, 0, 8, 1)])  # 0.001 m²
    assert check_polygons(tiny).status == "clean"  # default 0.01 m²
    assert len(check_polygons(tiny, min_overlap_area_m2=0).findings) == 1


# --- input quality ---------------------------------------------------------


def bowtie():
    return Polygon([(X0, Y0), (X0 + 10, Y0 + 10), (X0 + 10, Y0), (X0, Y0 + 10)])


def test_invalid_input_is_partial_never_clean():
    """A bowtie over a square: without the check it would look clean."""
    feats = layer([bowtie(), rect(0, 0, 10, 10)])
    r = check_polygons(feats, check_gaps=True, coverage=BLOCK)
    assert r.status == "partial"
    assert not r.ok
    inv = rows(r, "invalid_geometry")
    assert list(inv["fid_a"]) == [0]
    assert "Self-intersection" in inv.iloc[0]["reason"]
    assert [s["fid"] for s in r.skipped] == [0]
    assert r.checks["overlap"].status == "incomplete"
    assert r.checks["gap"].status == "incomplete"
    assert "unknown" in r.checks["gap"].message


def test_repair_is_explicit_in_memory_and_reported():
    feats = layer([bowtie(), rect(0, 0, 10, 10)])
    before = feats.geometry.to_wkb().tolist()
    r = check_polygons(feats, repair_invalid=True)
    assert r.status == "issues"
    assert r.skipped == []
    assert rows(r, "containment").iloc[0]["area_m2"] == 50.0
    assert "Repaired in memory" in rows(r, "invalid_geometry").iloc[0]["reason"]
    assert feats.geometry.to_wkb().tolist() == before  # input untouched


def test_empty_and_non_polygon_features_are_skipped_and_reported():
    feats = layer([rect(0, 0, 4, 4), None, Polygon(), Point(X0, Y0), rect(3, 0, 8, 4)])
    r = check_polygons(feats)
    assert r.status == "partial"
    assert r.counts_by_type() == {"overlap": 1, "empty_geometry": 2, "not_polygon": 1}
    assert sorted(s["fid"] for s in r.skipped) == [1, 2, 3]
    assert (r.feature_count, r.checked_count) == (5, 2)
    ov = rows(r, "overlap").iloc[0]
    assert (ov["fid_a"], ov["fid_b"]) == (0, 4)  # FIDs still point at source rows


def test_failed_geometry_operation_is_reported_not_swallowed(monkeypatch):
    real = shapely.intersection

    def flaky(a, b, *args, **kwargs):
        if getattr(a, "geom_type", None) is None:  # the vectorised call
            raise shapely.errors.GEOSException("TopologyException: test")
        if a.equals(rect(0, 0, 4, 4)):
            raise shapely.errors.GEOSException("TopologyException: test")
        return real(a, b, *args, **kwargs)

    monkeypatch.setattr("ovc.engine.overlaps.shapely.intersection", flaky)
    feats = layer([rect(0, 0, 4, 4), rect(3, 0, 8, 4), rect(7, 0, 12, 4)])
    r = check_polygons(feats)
    assert r.status == "partial"
    assert r.checks["overlap"].status == "incomplete"
    assert "could not be compared" in r.checks["overlap"].message
    assert r.counts_by_type() == {"overlap": 1}  # the pair that still worked
    assert r.skipped[0]["fid"] == 0


def test_layer_without_features_or_geometry_fails():
    assert check_polygons(layer([])).status == "failed"
    r = check_polygons(layer([None, None]))
    assert r.status == "failed"
    assert "nothing to check" in r.message


def test_repeated_and_missing_ids_are_reported_and_fids_still_locate_features():
    feats = layer(
        [rect(0, 0, 4, 4), rect(3, 0, 8, 4), rect(20, 0, 24, 4)],
        ref=["A", "A", None],
    )
    feats.index = [11, 12, 13]
    r = check_polygons(feats, id_field="ref")
    ov = rows(r, "overlap").iloc[0]
    assert (ov["fid_a"], ov["fid_b"], ov["id_a"], ov["id_b"]) == (11, 12, "A", "A")
    assert any("2 feature(s) share a value" in w for w in r.warnings)
    assert any("1 feature(s) have no value" in w for w in r.warnings)
    assert check_polygons(feats, id_field="nope").status == "failed"


# --- CRS and measurement ---------------------------------------------------


def test_missing_crs_fails_unless_declared():
    feats = gpd.GeoDataFrame(geometry=[rect(0, 0, 4, 10), rect(3, 0, 10, 10)])
    r = check_polygons(feats)
    assert r.status == "failed"
    assert "no CRS" in r.message
    r = check_polygons(feats, assume_crs=CRS)
    assert rows(r, "overlap").iloc[0]["area_m2"] == 10.0
    assert any("declared" in w for w in r.warnings)
    assert feats.crs is None  # input untouched


def test_degrees_are_never_reported_as_square_metres():
    feats = layer([rect(0, 0, 40, 100), rect(30, 0, 100, 100)]).to_crs(4326)
    r = check_polygons(feats)
    ov = rows(r, "overlap").iloc[0]
    assert ov["area_m2"] == pytest.approx(1000.0, rel=1e-4)  # not ~1e-7 deg²
    assert r.measurement.reprojected
    assert r.measurement.working_crs.to_epsg() == 32636
    assert "degrees" in r.measurement.method


def test_web_mercator_areas_are_not_trusted():
    feats = layer([rect(0, 0, 40, 100), rect(30, 0, 100, 100)]).to_crs(3857)
    planar_3857 = feats.geometry.iloc[0].intersection(feats.geometry.iloc[1]).area
    assert planar_3857 > 1300  # what a naive planar area would report at 30°N
    r = check_polygons(feats)
    assert rows(r, "overlap").iloc[0]["area_m2"] == pytest.approx(1000.0, rel=1e-4)
    assert "distorts area" in r.measurement.method


def test_projected_crs_in_feet_is_converted_to_square_metres():
    # EPSG:2263, New York Long Island (US survey foot)
    ft = 1200 / 3937
    feats = layer(
        [
            box(1_000_000, 200_000, 1_000_040, 200_100),
            box(1_000_030, 200_000, 1_000_100, 200_100),
        ],
        crs="EPSG:2263",
    )
    r = check_polygons(feats)
    assert rows(r, "overlap").iloc[0]["area_m2"] == pytest.approx(
        1000 * ft * ft, rel=1e-9
    )
    assert not r.measurement.reprojected


def test_findings_can_be_reprojected_and_keep_their_measured_area():
    feats = layer([rect(0, 0, 4, 10), rect(3, 0, 10, 10)])
    r = check_polygons(feats)
    wgs = r.findings_in(4326)
    assert wgs.crs.to_epsg() == 4326
    assert wgs.iloc[0]["area_m2"] == 10.0


def test_invalid_options_fail_clearly():
    feats = layer([rect(0, 0, 4, 10)])
    assert check_polygons(feats, check_overlaps=False).status == "failed"
    assert check_polygons(feats, min_overlap_area_m2=-1).status == "failed"
    assert check_polygons(feats, duplicate_ratio=0).status == "failed"
