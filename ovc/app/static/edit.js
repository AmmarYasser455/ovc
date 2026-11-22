/* Editing a layer, as in desktop GIS: Start Editing, change the features,
   Save Edits. OVC keeps the working copy (with undo) until it is saved;
   the map, Select and the checks all read that copy. Drawing and vertex
   editing use Leaflet-Geoman (MIT); move and rotate act on the whole
   selection at once. */
(function () {
  "use strict";
  const C = window.OVC;
  const { S, $, el, api, map } = C;
  const EDIT = "#c2410c"; // sketch colour: distinct from the cyan selection
  const COPY_STYLE = { color: EDIT, weight: 2, fillColor: EDIT, fillOpacity: 0.12, pmIgnore: false };
  const DRAW_SHAPES = {
    "draw-polygon": "Polygon", "draw-rectangle": "Rectangle", "draw-circle": "Circle",
    "draw-line": "Line", "draw-point": "CircleMarker",
  };
  const MODIFY = ["edit-move", "edit-rotate", "edit-reshape"];

  L.PM.setOptIn(true); // only shapes OVC hands to Geoman can be edited or snapped to
  map.createPane("editing").style.zIndex = 590;
  map.pm.setGlobalOptions({
    snappable: true, snapDistance: 14, allowSelfIntersection: false, continueDrawing: false,
    templineStyle: { color: EDIT }, hintlineStyle: { color: EDIT, dashArray: "5 5" },
    pathOptions: { color: EDIT, fillColor: EDIT, fillOpacity: 0.12 },
    markerStyle: { draggable: true },
  });

  const E = { copies: [], group: L.featureGroup().addTo(map), guides: L.featureGroup().addTo(map), drag: null, center: null, angle: 0 };

  const editLayer = () => (S.editing ? C.layerById(S.editing.layerId) : null);
  const selCount = () => (S.editing && S.sel.layer === S.editing.layerId ? S.sel.fids.length : 0);
  const target = (extra) => { const l = editLayer(); return Object.assign({ path: l.path, layer: l.info.name }, extra); };

  function failed(title, e) {
    C.showModal(title, [el("p", { text: e.message || String(e) })], [{ text: "Close", primary: true }]);
  }

  function ask(title, text, buttons) {
    return new Promise((resolve) => {
      C.showModal(title, [el("p", { text })], buttons.map(([label, value, primary]) => ({
        text: label, primary: !!primary, id: primary ? "modal-ok" : null, onclick: () => resolve(value),
      })), () => resolve("cancel"));
    });
  }

  // ---------------------------------------------------------- the session
  async function start(l) {
    l = l || C.layerById(S.active) || C.selectableLayer();
    if (!l) { C.message("Choose the layer to edit in Contents first."); return; }
    if (S.editing) {
      if (S.editing.layerId === l.id) return;
      if (!(await stop())) return;
    }
    if (l.error) { failed("This layer cannot be edited", { message: l.error }); return; }
    let status;
    try {
      status = await api("/api/edit/start", { body: { path: l.path, layer: l.info.name, assume_crs: l.assumeCrs || null } });
    } catch (e) { failed("Editing could not start", e); return; }
    S.editing = Object.assign({ layerId: l.id }, status);
    S.active = l.id;
    if (S.sel.layer !== l.id) C.clearFeature();
    C.renderContents();
    C.showRibbonTab("edit");
    sync();
    C.message(`Editing ${l.info.name}. Select features to change them, or draw new ones. Nothing is written until Save Edits.`);
    document.body.dataset.editing = l.info.name;
  }

  // Resolves true once editing has stopped (saved, discarded or nothing to save).
  async function stop() {
    if (!S.editing) return true;
    const l = editLayer();
    if (S.editing.dirty) {
      const choice = await ask("Save your edits?", `Save the edits to ${l.info.name} before you stop editing?`,
        [["Cancel", "cancel"], ["Discard edits", "discard"], ["Save", "save", true]]);
      if (choice === "cancel") return false;
      if (choice === "save" && !(await writeEdits())) return false;
    }
    if (S.editing) await api("/api/edit/discard", { body: target() }).catch(() => {});
    end(l);
    return true;
  }
  S.stopEditingFirst = stop;

  function end(l) {
    if (MODIFY.includes(S.tool) || DRAW_SHAPES[S.tool] || S.tool === "edit-split") C.setTool("select");
    S.editing = null;
    delete document.body.dataset.editing;
    if (l && C.layerById(l.id)) { C.loadLayerData(l, false); C.refreshSelection(); }
    sync();
    C.message(l ? `Stopped editing ${l.info.name}.` : "");
  }

  S.onLayerRemoved = (l) => {
    if (S.editing && S.editing.layerId === l.id) {
      api("/api/edit/discard", { body: { path: l.path, layer: l.info.name } }).catch(() => {});
      S.editing = null;
      teardown();
      sync();
    }
  };

  async function writeEdits() {
    const l = editLayer();
    try {
      const res = await api("/api/edit/save", { body: target() });
      C.message(`Saved the edits to ${res.saved}. The original is backed up in ${res.backup}.`);
      document.body.dataset.savedEdits = res.backup;
      S.editing.dirty = false;
      return res;
    } catch (e) {
      failed("The edits were not saved", e);
      return null;
    } finally {
      if (l) l.info.feature_count = S.editing ? S.editing.count : l.info.feature_count;
    }
  }

  async function saveEdits() {
    if (!S.editing || !S.editing.dirty) return;
    const l = editLayer();
    const choice = await ask("Save edits", `Write your edits to ${C.fileName(l.path)}? A copy of the original file is kept in OVC's backups folder first.`,
      [["Cancel", "cancel"], ["Save", "save", true]]);
    if (choice !== "save") return;
    if (!(await writeEdits())) return;
    // Saving ends the server's copy; keep editing from the saved file.
    try {
      const status = await api("/api/edit/start", { body: { path: l.path, layer: l.info.name, assume_crs: l.assumeCrs || null } });
      Object.assign(S.editing, status);
    } catch (e) { end(l); }
    C.loadLayerData(l, false);
    sync();
  }

  async function discardEdits() {
    if (!S.editing || !S.editing.dirty) return;
    const l = editLayer();
    const choice = await ask("Discard edits", `Throw away the unsaved edits to ${l.info.name}?`, [["Cancel", "cancel"], ["Discard", "discard", true]]);
    if (choice !== "discard") return;
    await api("/api/edit/discard", { body: target() }).catch(() => {});
    try {
      const status = await api("/api/edit/start", { body: { path: l.path, layer: l.info.name, assume_crs: l.assumeCrs || null } });
      Object.assign(S.editing, status);
    } catch (e) { end(l); return; }
    C.setTool("select");
    await C.loadLayerData(l, false);
    await C.refreshSelection();
    sync();
    C.message("Discarded the unsaved edits.");
  }

  // ------------------------------------------------------------ operations
  async function run(op, reselect) {
    const l = editLayer();
    if (!l) return null;
    let res;
    try {
      res = await api("/api/edit/op", { body: target({ op }) });
    } catch (e) { C.message(e.message); failed("That edit was not made", e); return null; }
    Object.assign(S.editing, { dirty: res.dirty, can_undo: res.can_undo, can_redo: res.can_redo, count: res.count });
    l.info.feature_count = res.count;
    await C.loadLayerData(l, false);
    const fids = reselect === "changed" ? res.changed.map((c) => c.fid) : reselect;
    if (Array.isArray(fids) && fids.length) await C.selectFeatures(l, { fids }, "replace");
    else if (reselect === "clear") C.clearFeature();
    else await C.refreshSelection();
    sync();
    return res;
  }

  function needEditing() {
    if (S.editing) return true;
    C.message("Start Editing first (Edit tab), with the layer chosen in Contents.");
    return false;
  }
  function needSelection(min, max) {
    const n = selCount();
    if (n >= min && (!max || n <= max)) return true;
    C.message(max === 1 ? "Select one feature of the layer you are editing first." : min > 1
      ? `Select ${min} or more features of the layer you are editing first.`
      : "Select the features to change first (Select tool).");
    return false;
  }

  const undo = () => needEditing() && S.editing.can_undo && run({ op: "undo" });
  const redo = () => needEditing() && S.editing.can_redo && run({ op: "redo" });
  const del = () => needEditing() && needSelection(1) && run({ op: "delete", fids: [...S.sel.fids] }, "clear");
  const merge = () => needEditing() && needSelection(2) && run({ op: "merge", fids: [...S.sel.fids] }, "changed");

  // ------------------------------------------------------------- drawing
  function snapGuides() {
    // Snap to the edited layer's features in view, unless it is drawn simplified.
    E.guides.clearLayers();
    const l = editLayer();
    if (!l || l.simplified || l.truncated) return;
    const view = map.getBounds().pad(0.2);
    let n = 0;
    l.group.eachLayer((f) => {
      if (n > 1500) return;
      const b = f.getBounds ? f.getBounds() : L.latLngBounds([f.getLatLng()]);
      if (!view.intersects(b)) return;
      n++;
      L.geoJSON(f.toGeoJSON(), {
        pane: "editing", pmIgnore: false, interactive: false, style: { opacity: 0, fillOpacity: 0 },
        pointToLayer: (ft, ll) => L.circleMarker(ll, { pane: "editing", radius: 1, opacity: 0, fillOpacity: 0, pmIgnore: false, interactive: false }),
      }).eachLayer((g) => g.addTo(E.guides));
    });
  }

  function startDraw(tool) {
    if (!needEditing()) { setTimeout(() => C.setTool("select")); return; }
    snapGuides();
    map.pm.enableDraw(DRAW_SHAPES[tool], { continueDrawing: true });
    C.message({
      "draw-polygon": "Polygon: click each corner; click the first corner, or double-click, to finish.",
      "draw-rectangle": "Rectangle: click one corner, then the opposite corner.",
      "draw-circle": "Circle: click the centre, then click at the radius.",
      "draw-line": "Line: click each vertex; click the last vertex again to finish.",
      "draw-point": "Point: click where it goes.",
    }[tool]);
  }
  function stopDraw() { map.pm.disableDraw(); E.guides.clearLayers(); }

  map.on("pm:create", async (e) => {
    const layer = e.layer;
    const geometry = e.shape === "Circle"
      ? L.PM.Utils.circleToPolygon(layer, 72).toGeoJSON().geometry
      : layer.toGeoJSON().geometry;
    layer.remove();
    if (!S.editing) return;
    if (S.tool === "edit-split") {
      const fid = S.sel.fids[0];
      const res = await run({ op: "split", fids: [fid], line: geometry }, "changed");
      if (res) C.message(`Split into ${res.changed.length} features.`);
      C.setTool("select");
      return;
    }
    const res = await run({ op: "add", geometry }, "changed");
    if (res) C.message(`Added feature FID ${res.changed[0].fid}. Keep drawing, or press Esc.`);
  });

  function startSplit() {
    if (!needEditing() || !needSelection(1, 1)) { setTimeout(() => C.setTool("select")); return; }
    snapGuides();
    map.pm.enableDraw("Line", { continueDrawing: false });
    C.message("Split: draw a line all the way across the selected feature; click the last vertex again to finish.");
  }

  // ----------------------------------------------- move, rotate, vertices
  const mapLL = (ll, fn) => (Array.isArray(ll) ? ll.map((x) => mapLL(x, fn)) : fn(ll));
  const getLL = (c) => (c.getLatLngs ? c.getLatLngs() : c.getLatLng());
  const setLL = (c, v) => (c.setLatLngs ? c.setLatLngs(v) : c.setLatLng(v));
  const Z = () => map.getZoom(); // project at one zoom: unrounded, unlike container points

  function makeCopies() {
    teardown();
    S.sel.fids.forEach((fid) => {
      const f = S.sel.features[fid];
      if (!f) return;
      L.geoJSON(f, {
        pane: "editing", style: COPY_STYLE, pmIgnore: false,
        pointToLayer: (ft, ll) => L.circleMarker(ll, Object.assign({ pane: "editing", radius: 6 }, COPY_STYLE)),
      }).eachLayer((c) => { c._ovcFid = fid; c.addTo(E.group); E.copies.push(c); });
    });
    E.start = E.copies.map((c) => mapLL(getLL(c), (p) => L.latLng(p.lat, p.lng)));
    overlays().selection.remove();
  }

  function teardown() {
    E.copies.forEach((c) => { if (c.pm) c.pm.disable(); });
    E.group.clearLayers();
    E.copies = [];
    E.drag = null;
    E.center = null;
    E.guides.clearLayers();
    if (!map.hasLayer(overlays().selection)) overlays().selection.addTo(map);
    $("edit-bar").hidden = true;
  }
  const overlays = () => C.overlays;

  function showBar(text) {
    $("edit-bar-text").textContent = text;
    $("edit-bar").hidden = false;
  }

  function startModify(tool) {
    if (!needEditing() || !needSelection(1)) { setTimeout(() => C.setTool("select")); return; }
    makeCopies();
    if (tool === "edit-reshape") {
      snapGuides();
      E.copies.forEach((c) => c.pm.enable({ allowSelfIntersection: false, snappable: true, draggable: false }));
      showBar("Drag a vertex to move it, drag a midpoint to add one, right-click a vertex to remove it.");
    } else if (tool === "edit-move") {
      showBar("Drag on the map to move the selected features.");
    } else {
      const b = E.group.getBounds();
      E.center = map.project(b.getCenter(), Z());
      E.angle = 0;
      L.circleMarker(b.getCenter(), { pane: "editing", radius: 5, color: EDIT, weight: 2, fillColor: "#fff", fillOpacity: 1, interactive: false }).addTo(E.group);
      showBar("Drag around the centre to rotate the selected features.");
    }
  }

  async function finishModify() {
    const tool = S.tool;
    if (!MODIFY.includes(tool) || !E.copies.length) return false;
    const features = E.copies.map((c) => ({ fid: c._ovcFid, geometry: c.toGeoJSON().geometry }));
    const fids = [...new Set(features.map((f) => f.fid))];
    teardown();
    C.setTool("select");
    const res = await run({ op: "update", features }, fids);
    if (res) C.message(`${tool === "edit-move" ? "Moved" : tool === "edit-rotate" ? "Rotated" : "Reshaped"} ${fids.length} feature${fids.length === 1 ? "" : "s"}.`);
    return true;
  }

  $("edit-bar-finish").addEventListener("click", finishModify);
  $("edit-bar-cancel").addEventListener("click", () => C.setTool("select"));

  const box = map.getContainer();
  box.addEventListener("mousedown", (e) => {
    if ((S.tool !== "edit-move" && S.tool !== "edit-rotate") || e.button !== 0 || !E.copies.length) return;
    if (e.target.closest(".leaflet-control, .map-float")) return;
    E.drag = { from: map.project(map.mouseEventToLatLng(e), Z()), base: E.copies.map((c) => mapLL(getLL(c), (p) => L.latLng(p.lat, p.lng))), angle: E.angle };
    e.preventDefault();
  });
  box.addEventListener("mousemove", (e) => {
    if (!E.drag) return;
    const here = map.project(map.mouseEventToLatLng(e), Z());
    let fn;
    if (S.tool === "edit-move") {
      const d = here.subtract(E.drag.from);
      fn = (p) => map.unproject(map.project(p, Z()).add(d), Z());
    } else {
      const a0 = Math.atan2(E.drag.from.y - E.center.y, E.drag.from.x - E.center.x);
      const a1 = Math.atan2(here.y - E.center.y, here.x - E.center.x);
      const t = a1 - a0, cos = Math.cos(t), sin = Math.sin(t);
      E.angle = E.drag.angle + (t * 180) / Math.PI;
      fn = (p) => {
        const q = map.project(p, Z()).subtract(E.center);
        return map.unproject(L.point(q.x * cos - q.y * sin, q.x * sin + q.y * cos).add(E.center), Z());
      };
      // Screen y points down, so a positive angle on screen is clockwise.
      showBar(`Rotation: ${(((E.angle % 360) + 540) % 360 - 180).toFixed(1)}° clockwise. Press Finish or Enter to apply.`);
    }
    E.copies.forEach((c, i) => setLL(c, mapLL(E.drag.base[i], fn)));
  });
  document.addEventListener("mouseup", () => {
    if (!E.drag) return;
    E.drag = null;
    if (S.tool === "edit-move") showBar("Drag again to adjust, then press Finish or Enter.");
  });

  // ------------------------------------------------------------- export
  async function exportLayer(l) {
    l = l || editLayer() || C.layerById(S.active);
    if (!l) { C.message("Choose a layer in Contents first."); return; }
    const write = async (out, overwrite) => {
      const res = await api("/api/layer/export", { body: { path: l.path, layer: l.info.name, out, overwrite } });
      C.message(`Exported ${l.info.name}${S.editing && S.editing.layerId === l.id ? ", with your edits," : ""} to ${res.saved}.`);
      document.body.dataset.exported = res.saved;
      return res;
    };
    const picked = await C.pickPath({
      mode: "save", kind: "layer", title: `Export ${l.info.name}`,
      dir: S.settings.last_dir || C.dirName(l.path), name: `${l.info.name}_export.gpkg`,
      saveHint: "GeoPackage (.gpkg), shapefile (.shp), GeoJSON, FlatGeobuf, GML or KML. The layer keeps its coordinate system.",
      onSave: write,
    });
    if (picked) {
      try { await write(picked.path, true); } catch (e) { failed("The layer was not exported", e); }
    }
  }
  S.startEditing = start;
  S.exportLayer = exportLayer;

  // ------------------------------------------------------------ the ribbon
  function sync() {
    const ed = S.editing;
    const n = selCount();
    const type = ed ? ed.geometry_type : "";
    $("edit-toggle").setAttribute("aria-pressed", String(!!ed));
    $("edit-toggle-label").textContent = ed ? "Stop Editing" : "Start Editing";
    document.querySelectorAll("[data-geom]").forEach((b) => { b.disabled = !ed || !(type === "Mixed" || b.dataset.geom === type); });
    const set = (id, on) => { $(id).disabled = !on && S.tool !== id; };
    set("edit-move", ed && n >= 1);
    set("edit-rotate", ed && n >= 1 && type !== "Point");
    set("edit-reshape", ed && n >= 1);
    set("edit-merge", ed && n >= 2);
    set("edit-split", ed && n === 1 && type !== "Point");
    set("edit-delete", ed && n >= 1);
    $("edit-save").disabled = !ed || !ed.dirty;
    $("edit-discard").disabled = !ed || !ed.dirty;
    $("edit-undo").disabled = !ed || !ed.can_undo;
    $("edit-redo").disabled = !ed || !ed.can_redo;
  }
  S.onToolsUpdate = sync;
  S.onSelectionChange = sync;

  Object.entries(DRAW_SHAPES).forEach(([tool]) => { C.toolHooks[tool] = { on: () => startDraw(tool), off: stopDraw }; });
  MODIFY.forEach((tool) => { C.toolHooks[tool] = { on: () => startModify(tool), off: teardown }; });
  C.toolHooks["edit-split"] = { on: startSplit, off: stopDraw };

  const toggleTool = (tool) => () => {
    if (!needEditing()) return;
    C.setTool(S.tool === tool ? "select" : tool);
  };
  Object.assign(C.commands, {
    "edit-toggle": () => (S.editing ? stop() : start()),
    "edit-save": saveEdits,
    "edit-discard": discardEdits,
    "edit-undo": undo,
    "edit-redo": redo,
    "edit-delete": del,
    "edit-merge": merge,
    "export-layer": () => exportLayer(),
  });
  [...Object.keys(DRAW_SHAPES), ...MODIFY, "edit-split"].forEach((tool) => { C.commands[tool] = toggleTool(tool); });

  const prevEscape = S.onEscape;
  S.onEscape = () => {
    if (S.editing && (MODIFY.includes(S.tool) || DRAW_SHAPES[S.tool] || S.tool === "edit-split")) { C.setTool("select"); return true; }
    return prevEscape ? prevEscape() : false;
  };
  const prevEnter = S.onEnter;
  S.onEnter = () => {
    if (MODIFY.includes(S.tool) && E.copies.length) { finishModify(); return true; }
    return prevEnter ? prevEnter() : false;
  };
  C.edit = { start, stop, run, exportLayer, state: E };
  sync();
})();
