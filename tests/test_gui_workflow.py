"""The click-through workflow in a real browser, from launch to export.

Starts the app the way the launcher does, then drives the page with
Playwright: file picker, layer selector, checks, linked list and map,
filter, export, and the failed / partial states.

Skipped when Playwright or a Chromium build is not available. Set
``OVC_CHROMIUM`` to a Chromium executable to use a specific build.
"""

import glob
import os
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Polygon, box

from ovc.sample_data import sample_path

sync_api = pytest.importorskip("playwright.sync_api")

SAMPLE = sample_path()


def _launch_browser(playwright):
    exe = os.environ.get("OVC_CHROMIUM")
    if not exe:
        found = glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome")
        exe = found[0] if found else None
    try:
        return playwright.chromium.launch(executable_path=exe, args=["--no-sandbox"])
    except Exception as exc:  # no browser installed
        pytest.skip(f"Chromium is not available: {exc}")


@pytest.fixture()
def app(tmp_path):
    """The app process, started through its launcher on a free port."""
    home = tmp_path / "home"
    home.mkdir()
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home), PYTHONUNBUFFERED="1")
    proc = subprocess.Popen(
        [sys.executable, "-m", "ovc.app", "--no-browser"],
        stdout=subprocess.PIPE,
        text=True,
        env=env,
    )
    url = proc.stdout.readline().strip()
    assert url.startswith("http://127.0.0.1:"), url
    yield proc, url
    if proc.poll() is None:
        proc.kill()
    proc.wait(timeout=10)


@pytest.fixture()
def page(app):
    with sync_api.sync_playwright() as playwright:
        browser = _launch_browser(playwright)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.goto(app[1])
        page.wait_for_selector("body[data-ready='1']")
        yield page
        assert errors == []
        browser.close()


def pick_file(page, button, path):
    """Use the file picker: open it, go to the folder, click the file."""
    page.click(button)
    open_folder(page, Path(path).parent)
    page.click(f"#dialog-list button.file:has-text('{Path(path).name}')")
    page.wait_for_selector("#dialog", state="hidden")
    target = "coverage" if "coverage" in button else "layer"
    page.wait_for_function(
        "([id, path]) => document.getElementById(id).dataset.loaded === path",
        arg=[f"{target}-box", str(path)],
    )


def open_folder(page, folder):
    # wait for the dialog's first listing before typing over its folder box
    page.wait_for_function("() => !!document.getElementById('dialog').dataset.dir")
    page.fill("#dialog-dir", str(folder))
    page.press("#dialog-dir", "Enter")
    page.wait_for_function(
        "(dir) => document.getElementById('dialog').dataset.dir === dir",
        arg=str(folder),
    )


def run_checks(page):
    page.click("#run")
    page.wait_for_selector("#step-results:not([hidden]) #status[data-status]")
    return page.get_attribute("#status", "data-status")


def facts(page, target):
    keys = page.locator(f"#{target}-facts dt").all_inner_texts()
    values = page.locator(f"#{target}-facts dd").all_inner_texts()
    return dict(zip(keys, values))


def test_review_workflow_from_launch_to_export(app, page, tmp_path):
    proc, _ = app
    assert page.is_disabled("#run")
    assert page.inner_text("#run-hint") == "Choose a layer first."

    # 1. file picker and layer selector --------------------------------
    pick_file(page, "#choose-layer", SAMPLE)
    options = page.locator("#layer-select option").all_inner_texts()
    assert [o.split(" ")[0] for o in options] == ["buildings", "parcels", "block"]
    assert facts(page, "layer") == {
        "Layer": "buildings",
        "Features": "9",
        "Geometry": "Polygon",
        "CRS": "EPSG:32636 - WGS 84 / UTM zone 36N",
    }

    # 2. overlaps only: the courtyard and the shared wall are not findings
    assert page.is_checked("#check-overlaps") and not page.is_checked("#check-gaps")
    assert run_checks(page) == "issues"
    assert page.locator("#findings li").count() == 3
    chips = page.locator("#filters .chip").all_inner_texts()
    assert chips == [
        "All (3)",
        "Overlap (1)",
        "Feature inside another (1)",
        "Duplicate feature (1)",
    ]

    # 3. switch layer: old results are cleared; gaps need a coverage layer
    page.select_option("#layer-select", "parcels")
    assert page.is_hidden("#step-results")
    page.select_option("#id-field", "parcel_ref")
    page.check("#check-gaps")
    assert page.is_disabled("#run")
    assert "needs a coverage layer" in page.inner_text("#run-hint")
    page.uncheck("#check-gaps")
    assert page.is_enabled("#run")  # overlaps stay available without it
    page.check("#check-gaps")
    pick_file(page, "#choose-coverage", SAMPLE)
    page.select_option("#coverage-select", "block")
    assert facts(page, "coverage")["Features"] == "1"

    assert run_checks(page) == "issues"
    assert "2 finding(s) in 8 features" in page.inner_text("#status")
    lines = page.inner_text("#check-lines")
    assert "Overlap check: 1 finding" in lines and "Gap check: 1 finding" in lines
    assert "square metres" in page.inner_text("#area-method")

    # 4. list and map are linked ------------------------------------------
    page.click("#findings li[data-type='gap'] button")
    detail = page.inner_text("#findings li.selected .detail")
    assert "Gap check" in detail and "10.00 m²" in detail
    assert "Borders FID 5, 7, 8" in detail
    assert "not covered by any feature" in detail
    page.wait_for_function("window.ovcApp.layers.highlight.getLayers().length === 1")
    view = page.evaluate("""() => {
            const app = window.ovcApp;
            const f = app.state.findings.find((x) => x.properties.issue_type === 'gap');
            const b = app.map.getBounds();
            const shown = app.layers.highlight.getLayers()[0].getLayers();
            return {
                inside: b.contains([[f.bbox[1], f.bbox[0]], [f.bbox[3], f.bbox[2]]]),
                zoom: app.map.getZoom(),
                highlighted: shown.map((l) => l.feature.properties.fid).sort(),
            };
        }""")
    assert view["inside"] and view["zoom"] >= 19  # zoomed to the 1 m x 10 m strip
    assert view["highlighted"] == [5, 7, 8]

    page.click("#findings li[data-type='overlap'] button")
    detail = page.inner_text("#findings li.selected .detail")
    assert "FID 2 (ID P2) and FID 3 (ID P3)" in detail
    assert "30.00 m² (10.0% of the smaller feature)" in detail
    page.wait_for_function("""() => {
            const g = window.ovcApp.layers.highlight.getLayers()[0];
            return g && g.getLayers().length === 2;
        }""")

    # 5. filter by issue type ------------------------------------------------
    page.click("#filters .chip[data-type='gap']")
    assert page.locator("#findings li").count() == 1
    assert page.inner_text("#export") == "Export 1 finding…"
    page.click("#filters .chip[data-type='all']")
    assert page.locator("#findings li").count() == 2

    # 6. export, then reopen the file ---------------------------------------
    before = SAMPLE.read_bytes()
    page.click("#export")
    assert page.input_value("#dialog-name") == "ovc_sample_parcels_ovc_findings.gpkg"
    open_folder(page, tmp_path)
    page.fill("#dialog-name", "review.gpkg")
    page.click("#dialog-save-btn")
    page.wait_for_selector("#dialog", state="hidden")
    assert "Saved 2 findings" in page.inner_text("#export-done")

    out = tmp_path / "review.gpkg"
    back = gpd.read_file(out, layer="ovc_findings").set_index("issue_type")
    assert back.crs.to_epsg() == 32636
    assert sorted(back.index) == ["gap", "overlap"]
    assert back.loc["gap", "area_m2"] == 10.0
    assert back.loc["gap"].geometry.equals(box(330_040, 3_320_030, 330_041, 3_320_040))
    assert back.loc["overlap", "area_m2"] == 30.0
    assert back.loc["overlap"].geometry.equals(
        box(330_038, 3_320_000, 330_040, 3_320_015)
    )
    assert (back.loc["overlap", "fid_a"], back.loc["overlap", "fid_b"]) == (2, 3)
    assert (back.loc["overlap", "id_a"], back.loc["overlap", "id_b"]) == ("P2", "P3")
    assert SAMPLE.read_bytes() == before  # source data intact

    # an existing file is only replaced after an explicit second click
    page.click("#export")
    open_folder(page, tmp_path)
    page.fill("#dialog-name", "review.gpkg")
    page.click("#dialog-save-btn")
    page.wait_for_selector("#dialog-error:not([hidden])")
    assert "already exists" in page.inner_text("#dialog-error")
    assert page.inner_text("#dialog-save-btn") == "Replace file"
    page.click("#dialog-close")

    # 7. quitting stops the app ----------------------------------------------
    page.click("#quit")
    assert proc.wait(timeout=15) == 0


def test_failed_and_partial_runs_are_not_shown_as_clean(page, tmp_path):
    broken = tmp_path / "broken.gpkg"
    broken.write_bytes(b"not a geopackage")
    pick_file(page, "#choose-layer", broken)
    assert "could not be opened" in page.inner_text("#layer-problem")
    assert page.is_disabled("#run")

    invalid = tmp_path / "invalid.gpkg"
    bowtie = Polygon([(0, 0), (10, 10), (10, 0), (0, 10)])
    gpd.GeoDataFrame(
        geometry=[bowtie, box(500_000, 3_000_000, 500_010, 3_000_010)], crs=32636
    ).to_file(invalid, driver="GPKG")
    pick_file(page, "#choose-layer", invalid)
    assert run_checks(page) == "partial"
    assert "PARTIAL RUN" in page.inner_text("#status").upper()
    assert "not a clean result" in page.inner_text("#status")
    assert "Incomplete" in page.inner_text("#check-lines")
    assert page.inner_text("#skipped-summary") == "1 skipped feature"

    # the file disappears between choosing it and running: a failed run
    invalid.unlink()
    assert run_checks(page) == "failed"
    assert "FAILED" in page.inner_text("#status").upper()
    assert page.is_hidden("#export")
