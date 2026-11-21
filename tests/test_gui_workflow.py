"""The click-through workflow in a real browser, from launch to export.

Starts the app the way the launcher does, then drives the page with
Playwright: add layers through the file picker, the Layers panel, checks,
linked list and map, the toolbar tools, filter, export, and the failed /
partial states.

Native file dialogs are switched off for the test (nobody is there to click
them), so the in-page file browser is used. Skipped when Playwright or a
Chromium build is not available. Set ``OVC_CHROMIUM`` to a Chromium
executable to use a specific build.
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
    env = dict(
        os.environ,
        HOME=str(home),
        USERPROFILE=str(home),
        PYTHONUNBUFFERED="1",
        OVC_NO_NATIVE_DIALOG="1",
    )
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
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.goto(app[1])
        # the splash names the app, the organisation and its founder
        splash = page.inner_text("#splash")
        assert "Overlap Violation Checker" in splash
        assert "OpenTerra" in splash and "Founded by Ammar Yasser" in splash
        page.wait_for_selector("body[data-ready='1']")
        page.wait_for_selector("#splash", state="detached")
        yield page
        assert errors == []
        browser.close()


def open_folder(page, folder):
    # wait for the dialog's first listing before typing over its folder box
    page.wait_for_function("() => !!document.getElementById('dialog').dataset.dir")
    page.fill("#dialog-dir", str(folder))
    page.press("#dialog-dir", "Enter")
    page.wait_for_function(
        "(dir) => document.getElementById('dialog').dataset.dir === dir",
        arg=str(folder),
    )


def add_file(page, path, layers=None):
    """Add layer: open the picker, go to the folder, click the file."""
    page.evaluate("() => { delete document.body.dataset.lastAdd; }")
    page.click("#choose-layer")
    open_folder(page, Path(path).parent)
    page.click(f"#dialog-list button.file:has-text('{Path(path).name}')")
    page.wait_for_selector("#dialog", state="hidden")
    if layers is not None:  # a multi-layer file asks which layers to add
        page.wait_for_selector("#modal:not([hidden]) #modal-ok")
        for box_ in page.locator("#modal-body input[type=checkbox]").all():
            box_.set_checked(box_.get_attribute("value") in layers)
        page.click("#modal-ok")
    page.wait_for_function("() => !!document.body.dataset.lastAdd")
    return page.evaluate("() => document.body.dataset.lastAdd")


def run_checks(page):
    page.click("#run")
    page.wait_for_selector("#step-results:not([hidden]) #status[data-status]")
    return page.get_attribute("#status", "data-status")


def facts(page):
    keys = page.locator("#layer-facts dt").all_inner_texts()
    values = page.locator("#layer-facts dd").all_inner_texts()
    return dict(zip(keys, values))


def toc(page):
    return page.locator("#toc li[data-layer]").evaluate_all(
        "(items) => items.map((li) => li.dataset.layer)"
    )


def selected_option(page, select):
    return page.eval_on_selector(
        select, "(s) => s.options[s.selectedIndex].text.split(' ')[0]"
    )


def test_review_workflow_from_launch_to_export(app, page, tmp_path):
    proc, _ = app
    assert page.is_disabled("#run") and page.is_disabled("#export")
    assert page.inner_text("#run-hint") == "Add a polygon layer first."

    # 1. add layers: the picker, then "select layers to add" -----------------
    assert add_file(page, SAMPLE, ["buildings", "parcels", "block"]).startswith("ok:")
    assert sorted(toc(page)) == ["block", "buildings", "parcels"]
    assert selected_option(page, "#target-layer") in {"buildings", "parcels", "block"}
    page.select_option("#target-layer", label="buildings  (ovc_sample.gpkg)")
    assert facts(page) == {
        "Features": "9",
        "Geometry": "Polygon",
        "CRS": "EPSG:32636 - WGS 84 / UTM zone 36N",
    }
    assert "EPSG:32636" in page.inner_text("#sb-crs")

    # 2. layers panel: hide, restyle, reorder, remove -----------------------
    row = "#toc li[data-layer='buildings']"
    page.uncheck(f"{row} input[type=checkbox]")
    assert (
        page.evaluate(
            "() => { const a = window.ovcApp; const l = a.state.layers.find((x) => x.info.name === 'buildings');"
            " return a.map.hasLayer(l.group); }"
        )
        is False
    )
    page.check(f"{row} input[type=checkbox]")
    page.click(f"{row} button[title='Symbology']")
    page.fill(f"{row} .toc-adjust input[type=color]", "#3366cc")
    assert (
        page.evaluate(
            "() => window.ovcApp.state.layers.find((x) => x.info.name === 'buildings').color"
        )
        == "#3366cc"
    )
    before = toc(page)
    page.click(f"#toc li[data-layer='{before[0]}'] button[title='Move down']")
    after = toc(page)
    assert after[1] == before[0] and after[0] == before[1]

    # 3. overlaps only: the courtyard and the shared wall are not findings ---
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

    # 4. remove a layer from the map; switch the layer being checked --------
    page.click("#toc li[data-layer='buildings'] button[title^='Remove']")
    assert sorted(toc(page)) == ["block", "parcels"]
    assert page.is_hidden("#step-results")  # its results went with it
    page.select_option("#target-layer", label="parcels  (ovc_sample.gpkg)")
    page.select_option("#id-field", "parcel_ref")
    page.check("#check-gaps")
    assert selected_option(page, "#coverage-layer") == "block"
    assert (
        page.locator("#toc li[data-layer='block'] .badge").inner_text().upper()
        == "COVERAGE"
    )
    assert page.is_enabled("#run")

    assert run_checks(page) == "issues"
    assert "2 finding(s) in 8 features" in page.inner_text("#status")
    lines = page.inner_text("#check-lines")
    assert "Overlap check: 1 finding" in lines and "Gap check: 1 finding" in lines
    assert "square metres" in page.inner_text("#area-method")

    # 5. list and map are linked -------------------------------------------
    page.click("#findings li[data-type='gap'] button")
    detail = page.inner_text("#findings li.selected .detail")
    assert "Gap check" in detail and "10.00 m²" in detail
    assert "Borders FID 5, 7, 8" in detail
    assert "not covered by any feature" in detail
    page.wait_for_function("window.ovcApp.overlays.highlight.getLayers().length === 1")
    view = page.evaluate("""() => {
            const app = window.ovcApp;
            const f = app.state.findings.find((x) => x.properties.issue_type === 'gap');
            const b = app.map.getBounds();
            const shown = app.overlays.highlight.getLayers()[0].getLayers();
            return {
                inside: b.contains([[f.bbox[1], f.bbox[0]], [f.bbox[3], f.bbox[2]]]),
                zoom: app.map.getZoom(),
                highlighted: shown.map((l) => l.feature.properties.fid).sort(),
            };
        }""")
    assert view["inside"] and view["zoom"] >= 19  # zoomed to the 1 m x 10 m strip
    assert view["highlighted"] == [5, 7, 8]
    page.fill("#findings li.selected textarea", "Check with survey")

    page.click("#findings li[data-type='overlap'] button")
    detail = page.inner_text("#findings li.selected .detail")
    assert "FID 2 (ID P2) and FID 3 (ID P3)" in detail
    assert "30.00 m² (10.0% of the smaller feature)" in detail
    page.wait_for_function("""() => {
            const g = window.ovcApp.overlays.highlight.getLayers()[0];
            return g && g.getLayers().length === 2;
        }""")

    # 6. toolbar: full extent, select a feature, clear ----------------------
    page.click("#zoom-full")
    page.wait_for_function("() => window.ovcApp.map.getZoom() < 21")
    page.click("#clear-selection")
    assert page.locator("#findings li.selected").count() == 0
    page.click("#tool-select")
    page.wait_for_timeout(400)  # let the zoom animation settle
    # click the middle of parcel P1 (0-20 m, 0-15 m of the block)
    spot = page.evaluate("""() => {
            const a = window.ovcApp;
            const l = a.state.layers.find((x) => x.info.name === 'parcels');
            const b = l.group.getBounds();
            const ll = [b.getSouth() + (b.getNorth() - b.getSouth()) * 0.15,
                        b.getWest() + (b.getEast() - b.getWest()) * 0.15];
            const p = a.map.latLngToContainerPoint(ll);
            const r = a.map.getContainer().getBoundingClientRect();
            return [r.left + p.x, r.top + p.y];
        }""")
    page.mouse.click(spot[0], spot[1])
    page.wait_for_selector("#panel-feature:not([hidden])")
    assert "parcels · FID 1" in page.inner_text("#feature-title")
    assert "P1" in page.inner_text("#feature-table")
    page.keyboard.press("Escape")
    assert page.is_hidden("#panel-feature")
    page.click("#tool-pan")

    # 7. filter by issue type; dismiss and restore a finding ----------------
    page.click("#filters .chip[data-type='gap']")
    assert page.locator("#findings li").count() == 1
    assert page.get_attribute("#export", "data-count") == "1"
    page.click("#filters .chip[data-type='all']")
    assert page.locator("#findings li").count() == 2
    page.click("#findings li[data-type='overlap'] button")
    page.click("#delete-item")
    assert page.locator("#findings li").count() == 1
    assert "1 finding dismissed" in page.inner_text("#dismissed-note")
    page.click("#restore")
    assert page.locator("#findings li").count() == 2

    # 8. export, then reopen the file ---------------------------------------
    before_bytes = SAMPLE.read_bytes()
    page.click("#export")
    page.wait_for_selector("#dialog:not([hidden])")
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
    assert back.loc["gap", "review_note"] == "Check with survey"
    assert back.loc["overlap", "area_m2"] == 30.0
    assert back.loc["overlap"].geometry.equals(
        box(330_038, 3_320_000, 330_040, 3_320_015)
    )
    assert (back.loc["overlap", "fid_a"], back.loc["overlap", "fid_b"]) == (2, 3)
    assert (back.loc["overlap", "id_a"], back.loc["overlap", "id_b"]) == ("P2", "P3")
    assert SAMPLE.read_bytes() == before_bytes  # source data intact

    # an existing file is only replaced after an explicit second click
    page.click("#export")
    page.wait_for_selector("#dialog:not([hidden])")
    open_folder(page, tmp_path)
    page.fill("#dialog-name", "review.gpkg")
    page.click("#dialog-save-btn")
    page.wait_for_selector("#dialog-error:not([hidden])")
    assert "already exists" in page.inner_text("#dialog-error")
    assert page.inner_text("#dialog-save-btn") == "Replace file"
    page.click("#dialog-close")

    # 9. about box, then quitting stops the app -----------------------------
    page.click("#about")
    about = page.inner_text("#modal-body")
    assert "OpenTerra" in about and "Founded by Ammar Yasser" in about
    page.click("#modal-close")
    page.click("#quit")
    assert proc.wait(timeout=15) == 0


def test_sample_button_sets_up_the_gap_check(page):
    page.click("#use-sample")
    page.wait_for_selector("body[data-sample='1']")
    assert selected_option(page, "#target-layer") == "parcels"
    assert selected_option(page, "#coverage-layer") == "block"
    assert page.is_checked("#check-gaps")
    assert run_checks(page) == "issues"
    assert page.locator("#findings li").count() == 2
    assert "Findings" in page.inner_text("#toc li.toc-findings")


def test_failed_and_partial_runs_are_not_shown_as_clean(page, tmp_path):
    broken = tmp_path / "broken.gpkg"
    broken.write_bytes(b"not a geopackage")
    assert add_file(page, broken).startswith("error:")
    assert "could not be opened" in page.inner_text("#modal-title")
    page.click("#modal-close")
    assert toc(page) == [] and page.is_disabled("#run")

    invalid = tmp_path / "invalid.gpkg"
    bowtie = Polygon([(0, 0), (10, 10), (10, 0), (0, 10)])
    gpd.GeoDataFrame(
        geometry=[bowtie, box(500_000, 3_000_000, 500_010, 3_000_010)], crs=32636
    ).to_file(invalid, driver="GPKG")
    assert add_file(page, invalid).startswith("ok:")
    assert run_checks(page) == "partial"
    assert "PARTIAL RUN" in page.inner_text("#status").upper()
    assert "not a clean result" in page.inner_text("#status")
    assert "Incomplete" in page.inner_text("#check-lines")
    assert page.inner_text("#skipped-summary") == "1 skipped feature"

    # the file disappears between adding it and running: a failed run
    invalid.unlink()
    assert run_checks(page) == "failed"
    assert "FAILED" in page.inner_text("#status").upper()
    assert page.is_disabled("#export")
