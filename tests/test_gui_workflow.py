"""The click-through workflow in a real browser, from launch to export.

Starts the app the way the launcher does, then drives the page with
Playwright: Add Data, the Contents pane, the OVC Toolbox, the linked
results list and map, the Select tool, filter, export, theme, bug report,
and the failed / partial states.

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
def app_env():
    """Extra environment for the app process (a test can override this)."""
    return {"OVC_NO_UPDATE_CHECK": "1"}


@pytest.fixture()
def app(tmp_path, app_env):
    """The app process, started through its launcher on a free port."""
    home = tmp_path / "home"
    home.mkdir()
    env = dict(
        os.environ,
        HOME=str(home),
        USERPROFILE=str(home),
        PYTHONUNBUFFERED="1",
        OVC_NO_NATIVE_DIALOG="1",
        OVC_NO_OPEN_URL="1",
        **app_env,
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


def add_data(page, path, layers=None):
    """Add Data: open the picker, go to the folder, click the file."""
    page.evaluate("() => { delete document.body.dataset.lastAdd; }")
    page.click("#add-data")
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


def toc(page):
    return page.locator("#toc li[data-layer]").evaluate_all(
        "(items) => items.map((li) => li.dataset.layer)"
    )


def node(page, layer):
    return f"#toc li[data-layer='{layer}'] > .node"


def open_tool(page, tool_id):
    page.click("#qa-toolbox")
    page.wait_for_selector("#pane-geoprocessing:not([hidden])")
    if page.is_visible("#gp-back"):
        page.click("#gp-back")
    page.click(f"#gp-tree li[data-tool='{tool_id}'] > .node")
    page.wait_for_selector("#gp-tool:not([hidden])")


def run_tool(page):
    page.click("#gp-run")
    page.wait_for_selector("#step-results:not([hidden]) #status[data-status]")
    return page.get_attribute("#status", "data-status")


def map_point(page, layer, fx, fy):
    """Screen position at fraction (fx, fy) of a layer's extent."""
    return page.evaluate(
        """([name, fx, fy]) => {
            const a = window.ovcApp;
            const l = a.state.layers.find((x) => x.info.name === name);
            const b = l.group.getBounds();
            const ll = [b.getSouth() + (b.getNorth() - b.getSouth()) * fy,
                        b.getWest() + (b.getEast() - b.getWest()) * fx];
            const p = a.map.latLngToContainerPoint(ll);
            const r = a.map.getContainer().getBoundingClientRect();
            return [r.left + p.x, r.top + p.y];
        }""",
        [layer, fx, fy],
    )


def test_review_workflow_from_launch_to_export(app, page, tmp_path):
    proc, _ = app
    assert page.is_disabled("#export")

    # 1. Add Data: the picker, then "select layers to add" ------------------
    assert add_data(page, SAMPLE, ["buildings", "parcels", "block"]).startswith("ok:")
    assert sorted(toc(page)) == ["block", "buildings", "parcels"]

    # 2. Contents: visibility, symbology, reorder (menu and drag), panes ---
    page.uncheck(f"{node(page, 'buildings')} input[type=checkbox]")
    hidden = page.evaluate(
        "() => { const a = window.ovcApp; const l = a.state.layers.find((x) => x.info.name === 'buildings');"
        " return a.map.hasLayer(l.group); }"
    )
    assert hidden is False
    page.check(f"{node(page, 'buildings')} input[type=checkbox]")

    page.dblclick(f"{node(page, 'buildings')} .label")
    page.wait_for_selector("#pane-symbology:not([hidden])")
    assert page.inner_text("#sym-layer") == "buildings"
    page.fill("#sym-color", "#3366cc")
    assert (
        page.evaluate(
            "() => window.ovcApp.state.layers.find((x) => x.info.name === 'buildings').color"
        )
        == "#3366cc"
    )

    before = toc(page)
    page.click(f"{node(page, before[0])}", button="right")
    page.click("#ctx [data-ctx='down']")
    after = toc(page)
    assert after[:2] == [before[1], before[0]]
    page.drag_and_drop(
        f"#toc li[data-layer='{after[2]}'] > .node",
        f"#toc li[data-layer='{after[0]}'] > .node",
        target_position={"x": 20, "y": 2},
    )
    assert toc(page)[0] == after[2]  # dragged to the top of the drawing order

    page.click("#contents-close")
    assert page.is_hidden("#dock-left")
    page.click(".rtab[data-tab='view']")
    page.click("#rp-view [data-cmd='show-contents']")
    assert page.is_visible("#dock-left")
    page.click(".rtab[data-tab='map']")

    # 3. Toolbox > Find Overlaps on buildings ------------------------------
    open_tool(page, "find-overlaps")
    assert page.inner_text("#gp-title") == "Find Overlaps"
    page.select_option("#gp-input", label="buildings")
    page.select_option("#gp-id_field", "bldg_ref")
    assert run_tool(page) == "issues"
    assert page.locator("#findings li").count() == 3
    chips = page.locator("#filters .chip").all_inner_texts()
    assert chips == [
        "All (3)",
        "Overlap (1)",
        "Feature inside another (1)",
        "Duplicate feature (1)",
    ]
    assert "Find Overlaps completed" in page.inner_text("#gp-message")

    # 4. removing the checked layer clears its results ----------------------
    page.click(node(page, "buildings"), button="right")
    page.click("#ctx [data-ctx='remove']")
    assert sorted(toc(page)) == ["block", "parcels"]
    assert page.is_hidden("#step-results")

    # 5. Toolbox > Find Gaps on parcels with the block as coverage ----------
    page.click("#dock-tabs [data-pane='geoprocessing']")
    open_tool(page, "find-gaps")
    page.select_option("#gp-input", label="parcels")
    page.select_option("#gp-coverage", label="block")
    page.select_option("#gp-id_field", "parcel_ref")
    assert page.is_checked("#gp-also_overlaps")
    assert run_tool(page) == "issues"
    assert "2 finding(s) in 8 features" in page.inner_text("#status")
    lines = page.inner_text("#check-lines")
    assert "Overlap check: 1 finding" in lines and "Gap check: 1 finding" in lines
    assert "square metres" in page.inner_text("#area-method")

    # 6. list and map are linked --------------------------------------------
    page.click("#findings li[data-type='gap'] button")
    detail = page.inner_text("#findings li.selected .detail")
    assert "Gap check" in detail and "10.00 m²" in detail
    assert "Borders FID 5, 7, 8" in detail
    page.wait_for_function("window.ovcApp.overlays.highlight.getLayers().length === 1")
    view = page.evaluate("""() => {
            const app = window.ovcApp;
            const f = app.state.findings.find((x) => x.properties.issue_type === 'gap');
            const b = app.map.getBounds();
            const shown = app.overlays.highlight.getLayers()[0].getLayers();
            const path = document.querySelector('.leaflet-pane[class*="finding"] path')
              || app.map.getPane('finding').querySelector('path');
            const r = path.getBoundingClientRect();
            return {
                inside: b.contains([[f.bbox[1], f.bbox[0]], [f.bbox[3], f.bbox[2]]]),
                zoom: app.map.getZoom(),
                highlighted: shown.map((l) => l.feature.properties.fid).sort(),
                drawnSize: [r.width, r.height],
            };
        }""")
    assert view["inside"] and view["zoom"] >= 19  # zoomed to the 1 m x 10 m strip
    assert view["highlighted"] == [5, 7, 8]
    # findings are drawn at map scale, not shrunk by the icon styles
    assert max(view["drawnSize"]) > 40
    page.fill("#findings li.selected textarea", "Check with survey")

    page.click("#findings li[data-type='overlap'] button")
    detail = page.inner_text("#findings li.selected .detail")
    assert "FID 2 (ID P2) and FID 3 (ID P3)" in detail
    assert "30.00 m² (10.0% of the smaller feature)" in detail

    # 7. Select tool: outline and attributes of a clicked feature -----------
    page.click("#zoom-full")
    page.wait_for_function("() => window.ovcApp.map.getZoom() < 21")
    page.click("#clear-selection")
    page.click("#tool-select")
    page.wait_for_timeout(400)  # let the zoom animation settle
    x, y = map_point(page, "parcels", 0.15, 0.15)  # inside parcel P1
    page.mouse.click(x, y)
    page.wait_for_selector("#pane-attributes:not([hidden])")
    assert "parcels · FID 1" in page.inner_text("#feature-title")
    assert "P1" in page.inner_text("#feature-table")
    outline = page.evaluate(
        "() => window.ovcApp.overlays.selection.getLayers()[0].getLayers()[0].options.color"
    )
    assert outline == "#00e5ff"
    page.keyboard.press("Escape")
    assert (
        page.evaluate("() => window.ovcApp.overlays.selection.getLayers().length") == 0
    )
    page.click("#tool-pan")

    # 8. filter by issue type; dismiss and restore a finding -----------------
    page.click("#dock-tabs [data-pane='results']")
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

    # 9. export, then reopen the file -----------------------------------------
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

    # 10. theme, bug report, about, quit -------------------------------------
    page.click(".rtab[data-tab='view']")
    page.click("#theme-dark")
    assert page.get_attribute("html", "data-theme") == "dark"
    page.click(".rtab[data-tab='help']")
    page.click("#report-bug")
    page.fill("#bug-what", "The layer did not draw")
    page.check("#bug-include-log")
    with page.expect_request("**/api/open-url") as request:
        page.click("#bug-open")
    url = request.value.post_data_json["url"]
    assert url.startswith("https://github.com/AmmarYasser455/ovc/issues/new?")
    assert "The+layer+did+not+draw" in url or "The%20layer%20did%20not%20draw" in url
    assert "OVC+version" in url or "OVC%20version" in url

    page.click("#about")
    about = page.inner_text("#modal-body")
    assert "OpenTerra" in about and "Founded by Ammar Yasser" in about
    page.click("#modal-close")
    page.click("#quit")
    assert proc.wait(timeout=15) == 0


def test_sample_button_opens_find_gaps_ready_to_run(page):
    page.click("#use-sample")
    page.wait_for_selector("body[data-sample='1']")
    assert page.inner_text("#gp-title") == "Find Gaps"
    assert (
        page.eval_on_selector("#gp-input", "(s) => s.options[s.selectedIndex].text")
        == "parcels"
    )
    assert (
        page.eval_on_selector("#gp-coverage", "(s) => s.options[s.selectedIndex].text")
        == "block"
    )
    assert run_tool(page) == "issues"
    assert page.locator("#findings li").count() == 2
    assert "Findings" in page.inner_text("#toc li.toc-findings")


def test_failed_and_partial_runs_are_not_shown_as_clean(page, tmp_path):
    broken = tmp_path / "broken.gpkg"
    broken.write_bytes(b"not a geopackage")
    assert add_data(page, broken).startswith("error:")
    assert "could not be opened" in page.inner_text("#modal-title")
    page.click("#modal-close")
    assert toc(page) == []

    invalid = tmp_path / "invalid.gpkg"
    bowtie = Polygon([(0, 0), (10, 10), (10, 0), (0, 10)])
    gpd.GeoDataFrame(
        geometry=[bowtie, box(500_000, 3_000_000, 500_010, 3_000_010)], crs=32636
    ).to_file(invalid, driver="GPKG")
    assert add_data(page, invalid).startswith("ok:")
    open_tool(page, "find-overlaps")
    assert run_tool(page) == "partial"
    assert "PARTIAL RUN" in page.inner_text("#status").upper()
    assert "not a clean result" in page.inner_text("#status")
    assert "Incomplete" in page.inner_text("#check-lines")
    assert page.inner_text("#skipped-summary") == "1 skipped feature"

    # the file disappears between adding it and running: a failed run
    invalid.unlink()
    page.click("#dock-tabs [data-pane='geoprocessing']")
    assert run_tool(page) == "failed"
    assert "FAILED" in page.inner_text("#status").upper()
    assert page.is_disabled("#export")


class TestUpdateBar:
    """A newer release on the feed shows the update bar after start-up."""

    @pytest.fixture()
    def app_env(self, tmp_path):
        import json
        import threading
        from functools import partial
        from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

        www = tmp_path / "www"
        www.mkdir()
        (www / "latest.json").write_text(
            json.dumps(
                {
                    "tag_name": "v99.0.0",
                    "html_url": "https://github.com/AmmarYasser455/ovc/releases/tag/v99.0.0",
                    "body": "",
                    "assets": [],
                }
            )
        )
        handler = partial(SimpleHTTPRequestHandler, directory=str(www))
        handler.log_message = lambda *a: None
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        yield {
            "OVC_UPDATE_FEED": f"http://127.0.0.1:{server.server_address[1]}/latest.json"
        }
        server.shutdown()
        server.server_close()

    def test_update_bar_announces_a_new_release(self, page):
        page.wait_for_selector("#update-bar:not([hidden])")
        assert "OVC 99.0.0 is available" in page.inner_text("#update-text")
        assert page.get_attribute("#update-notes", "href").endswith("/tag/v99.0.0")
        # run from source here, so the bar offers the release page, not an install
        assert page.inner_text("#update-action") == "Release page"
        page.click("#update-later")
        assert page.is_hidden("#update-bar")

        page.click(".rtab[data-tab='help']")
        page.click("#about")
        page.wait_for_selector("#update-auto")
        assert page.is_checked("#update-auto")
        page.click("#update-check-now")
        page.wait_for_function(
            "() => document.getElementById('update-check-result').textContent.includes('99.0.0')"
        )
