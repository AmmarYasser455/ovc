/* OVC map app. Talks to the local OVC server; no data leaves this computer. */
(function () {
  "use strict";

  const TOKEN = new URLSearchParams(location.search).get("t") || "";
  const COLORS = {
    overlap: "#d32f2f",
    containment: "#ef6c00",
    duplicate: "#7b1fa2",
    gap: "#00838f",
    invalid_geometry: "#5d4037",
    empty_geometry: "#757575",
    not_polygon: "#757575",
  };
  const CHECK_NAMES = { overlap: "Overlap check", gap: "Gap check", input: "Input quality" };
  const STATUS_NAMES = {
    clean: "Clean",
    issues: "Issues found",
    partial: "Partial run",
    failed: "Failed",
  };

  const $ = (id) => document.getElementById(id);
  const S = {
    config: null,
    layer: { path: null, layers: [], info: null },
    coverage: { path: null, layers: [], info: null },
    summary: null,
    findings: [],
    filter: new Set(), // empty = show every issue type
    selected: null,
    exportDefault: "",
    busy: false,
  };

  // ---------------------------------------------------------------- helpers
  async function api(path, options = {}) {
    const init = { method: options.method || "GET", headers: { "X-OVC-Token": TOKEN } };
    if (options.body !== undefined) {
      init.method = "POST";
      init.headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(options.body);
    }
    let response;
    try {
      response = await fetch(path, init);
    } catch (e) {
      throw new Error("OVC is not running any more. Open OVC again.");
    }
    let data = {};
    try { data = await response.json(); } catch (e) { /* not JSON */ }
    if (!response.ok) {
      const err = new Error(data.error || `Request failed (${response.status})`);
      err.code = data.code;
      throw err;
    }
    return data;
  }

  function qs(params) {
    const p = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== null && v !== undefined && v !== "") p.set(k, v);
    });
    return p.toString();
  }

  function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    Object.entries(attrs).forEach(([k, v]) => {
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
      else if (v !== false && v !== null && v !== undefined) node.setAttribute(k, v);
    });
    children.forEach((c) => node.append(c));
    return node;
  }

  function fmtArea(a) {
    if (a === null || a === undefined) return "";
    if (a >= 100) return a.toLocaleString("en", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + " m²";
    if (a >= 0.01) return a.toLocaleString("en", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " m²";
    return a.toPrecision(3) + " m²";
  }

  function featureLabel(fid, id) {
    return id === null || id === undefined ? `FID ${fid}` : `FID ${fid} (ID ${id})`;
  }

  function assumeCrs() {
    if ($("crs-wrap").hidden) return "";
    const v = $("assume-crs").value.trim();
    if (!v) return "";
    return /^\d+$/.test(v) ? `EPSG:${v}` : v;
  }

  // -------------------------------------------------------------------- map
  const map = L.map("map", { maxZoom: 24, zoomSnap: 0.25, worldCopyJump: false }).setView([20, 10], 2);
  ["source", "coverage", "finding", "highlight", "dot"].forEach((name, i) => {
    map.createPane(name).style.zIndex = 410 + i * 10;
  });
  map.getPane("highlight").style.pointerEvents = "none";
  const canvas = L.canvas({ pane: "source" });
  L.control.scale({ imperial: false, maxWidth: 160 }).addTo(map);

  const osm = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 24,
    maxNativeZoom: 19,
    attribution: "© OpenStreetMap contributors",
  });
  const basemapControl = L.control({ position: "topright" });
  basemapControl.onAdd = function () {
    const box = el("label", { class: "basemap" });
    const input = el("input", { type: "checkbox", id: "basemap" });
    input.addEventListener("change", () => (input.checked ? osm.addTo(map) : osm.remove()));
    box.append(input, " OpenStreetMap background (needs internet)");
    L.DomEvent.disableClickPropagation(box);
    return box;
  };
  basemapControl.addTo(map);

  const legend = L.control({ position: "bottomright" });
  legend.onAdd = function () {
    this._div = el("div", { class: "legend" });
    return this._div;
  };
  legend.addTo(map);

  const layers = {
    source: L.geoJSON(null, {
      pane: "source", renderer: canvas, interactive: false,
      style: { color: "#4b5563", weight: 1, fillColor: "#9aa3ad", fillOpacity: 0.35 },
    }).addTo(map),
    coverage: L.geoJSON(null, {
      pane: "coverage", interactive: false,
      style: { color: "#121417", weight: 2, dashArray: "7 5", fill: false },
    }).addTo(map),
    findings: L.layerGroup().addTo(map),
    highlight: L.layerGroup().addTo(map),
    dots: L.layerGroup().addTo(map),
  };

  function updateLegend() {
    const div = legend._div;
    div.replaceChildren();
    const add = (node, text) => div.append(el("div", {}, node, text));
    add(el("span", { class: "swatch", style: "background:#9aa3ad" }), "Checked features");
    if (layers.coverage.getLayers().length) add(el("span", { class: "line" }), "Coverage area");
    const types = [...new Set(S.findings.map((f) => f.properties.issue_type))];
    types.forEach((t) => {
      add(el("span", { class: "swatch", style: `background:${COLORS[t]}` }), S.config.issue_types[t] || t);
    });
  }

  function fitTo(bounds) {
    if (!bounds) return;
    map.fitBounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]], { padding: [40, 40], maxZoom: 22 });
  }

  const previewSeq = { layer: 0, coverage: 0 };

  async function showLayerOnMap(target) {
    const item = S[target];
    const group = target === "layer" ? layers.source : layers.coverage;
    const seq = ++previewSeq[target]; // a newer choice makes this request stale
    group.clearLayers();
    if (target === "layer") { $("map-note").hidden = true; }
    if (!item.path || !item.info) { updateLegend(); return; }
    try {
      const data = await api("/api/preview?" + qs({
        path: item.path, layer: item.info.name, assume_crs: target === "layer" ? assumeCrs() : "",
      }));
      if (seq !== previewSeq[target]) return;
      group.clearLayers();
      group.addData(data);
      if (target === "layer") {
        $("map-hint").hidden = true;
        if (data.truncated) {
          $("map-note").textContent =
            `This layer has ${data.total.toLocaleString("en")} features, too many to draw at once. ` +
            "All of them are checked; the features behind a finding are drawn when you select it.";
          $("map-note").hidden = false;
        }
        fitTo(data.bounds);
      }
    } catch (e) {
      if (seq !== previewSeq[target]) return;
      if (target === "layer") {
        $("map-hint").textContent = e.message;
        $("map-hint").hidden = false;
      }
    }
    updateLegend();
  }

  // ------------------------------------------------------------ file dialog
  const dialog = { mode: "open", onPick: null, dir: null, overwrite: false };

  async function openDialog(options) {
    Object.assign(dialog, { overwrite: false, initial: true }, options);
    $("dialog-title").textContent = options.title;
    $("dialog-save").hidden = options.mode !== "save";
    $("dialog-name").value = options.name || "";
    $("dialog-save-btn").textContent = "Save";
    $("dialog-foot").textContent = options.mode === "save"
      ? "Pick the folder, then check the file name."
      : "Shows folders and vector files: " + S.config.extensions.join(", ");
    const places = $("dialog-places");
    places.replaceChildren();
    S.config.places.forEach((p) => {
      places.append(el("button", { text: p.label, onclick: () => browseTo(p.path) }));
    });
    delete $("dialog").dataset.dir;
    $("dialog").hidden = false;
    await browseTo(options.dir || localStorage.getItem("ovc-last-dir") || "");
    (options.mode === "save" ? $("dialog-name") : $("dialog-dir")).focus();
  }

  function closeDialog() { $("dialog").hidden = true; }

  let browseSeq = 0;

  async function browseTo(dir) {
    const error = $("dialog-error");
    error.hidden = true;
    const seq = ++browseSeq; // only the latest folder request may update the list
    let data;
    try {
      data = await api("/api/browse?" + qs({ dir }));
      if (seq !== browseSeq) return;
    } catch (e) {
      if (seq !== browseSeq) return;
      if (dir && dialog.initial) { dialog.initial = false; return browseTo(""); } // start folder is gone
      error.textContent = e.message;
      error.hidden = false;
      return;
    }
    dialog.initial = false;
    dialog.dir = data.dir;
    $("dialog").dataset.dir = data.dir;
    dialog.parent = data.parent;
    dialog.overwrite = false;
    $("dialog-save-btn").textContent = "Save";
    $("dialog-dir").value = data.dir;
    $("dialog-up").disabled = !data.parent;
    const list = $("dialog-list");
    list.replaceChildren();
    data.entries.forEach((entry) => {
      const isDir = entry.type === "dir";
      const disabled = !isDir && dialog.mode === "save";
      const button = el("button", {
        class: isDir ? "dir" : "file", disabled: disabled ? "" : null,
        onclick: () => (isDir ? browseTo(entry.path) : pick(entry.path)),
      }, el("span", { class: "kind", text: isDir ? "Folder" : "Layer" }), el("span", { text: entry.name }));
      list.append(el("li", {}, button));
    });
    if (!data.entries.length) {
      list.append(el("li", { class: "empty-list", text: "No folders or vector files here." }));
    }
  }

  function pick(path) {
    localStorage.setItem("ovc-last-dir", dialog.dir);
    closeDialog();
    dialog.onPick(path);
  }

  $("dialog-close").addEventListener("click", closeDialog);
  $("dialog-up").addEventListener("click", () => dialog.parent && browseTo(dialog.parent));
  $("dialog-go").addEventListener("click", () => goToTypedPath());
  $("dialog-dir").addEventListener("keydown", (e) => { if (e.key === "Enter") goToTypedPath(); });
  $("dialog-name").addEventListener("input", () => {
    dialog.overwrite = false;
    $("dialog-save-btn").textContent = "Save";
    $("dialog-error").hidden = true;
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("dialog").hidden) closeDialog(); });

  async function goToTypedPath() {
    // A pasted path may be a folder or, when opening, the file itself.
    const typed = $("dialog-dir").value.trim().replace(/^"|"$/g, "");
    const lower = typed.toLowerCase();
    if (dialog.mode === "open" && S.config.extensions.some((x) => lower.endsWith(x))) {
      closeDialog();
      dialog.onPick(typed);
      return;
    }
    await browseTo(typed);
  }

  // ----------------------------------------------------------- layer choice
  function facts(target, info) {
    const dl = $(target + "-facts");
    dl.replaceChildren();
    if (!info) return;
    const add = (k, v) => dl.append(el("dt", { text: k }), el("dd", { text: v }));
    add("Layer", info.name);
    add("Features", info.feature_count.toLocaleString("en"));
    add("Geometry", info.geometry_type);
    add("CRS", info.has_crs ? info.crs : "Missing");
  }

  async function chooseFile(target, path, preferredLayer) {
    const item = S[target];
    const problem = $(target + "-problem");
    problem.hidden = true;
    delete $(target + "-box").dataset.loaded;
    let data;
    try {
      data = await api("/api/layers?" + qs({ path }));
    } catch (e) {
      item.path = null; item.layers = []; item.info = null;
      $(target + "-box").hidden = false;
      $(target + "-path").textContent = path;
      $(target + "-select").replaceChildren();
      facts(target, null);
      problem.textContent = `This file could not be opened. ${e.message}`;
      problem.hidden = false;
      onInputsChanged(target);
      $(target + "-box").dataset.loaded = path;
      return;
    }
    item.path = path;
    item.layers = data.layers;
    $(target + "-box").hidden = false;
    $(target + "-path").textContent = path;
    const select = $(target + "-select");
    select.replaceChildren();
    data.layers.forEach((info) => {
      const text = `${info.name} (${info.geometry_type}, ${info.feature_count.toLocaleString("en")})`;
      select.append(el("option", { value: info.name, text }));
    });
    // Default: the first polygon layer; for coverage, not the layer being checked.
    const polygons = data.layers.filter((i) => i.is_polygon);
    let first = polygons[0] || data.layers[0];
    if (target === "coverage" && S.layer.info && S.layer.path === path) {
      first = polygons.find((i) => i.name !== S.layer.info.name) || first;
    }
    if (preferredLayer && data.layers.some((i) => i.name === preferredLayer)) {
      first = { name: preferredLayer };
    }
    select.value = first.name;
    if (target === "layer") $("layer-select-wrap").hidden = data.layers.length < 2;
    onLayerSelected(target);
    $(target + "-box").dataset.loaded = path;
  }

  function onLayerSelected(target) {
    const item = S[target];
    const name = $(target + "-select").value;
    item.info = item.layers.find((i) => i.name === name) || null;
    facts(target, item.info);
    const problem = $(target + "-problem");
    problem.hidden = true;
    const info = item.info;
    if (info) {
      let text = "";
      if (!info.is_polygon) {
        text = `This is a ${info.geometry_type} layer. OVC checks polygon layers; choose a polygon layer.`;
      } else if (info.feature_count === 0) {
        text = "This layer has no features.";
      } else if (target === "coverage" && !info.has_crs) {
        text = "This layer has no CRS, so it cannot be compared with the layer being checked. Define its CRS in the file.";
      } else if (target === "coverage" && S.layer.info && S.layer.path === item.path && S.layer.info.name === info.name) {
        text = "This is the layer being checked. Choose the layer that outlines the area it should cover.";
      }
      if (text) { problem.textContent = text; problem.hidden = false; }
    }
    if (target === "layer") {
      $("crs-wrap").hidden = !(info && !info.has_crs);
      const idField = $("id-field");
      idField.replaceChildren(el("option", { value: "", text: "FID only" }));
      (info ? info.fields : []).forEach((f) => idField.append(el("option", { value: f, text: f })));
    }
    onInputsChanged(target);
    showLayerOnMap(target);
  }

  function usable(target) {
    const item = S[target];
    return !!(item.path && item.info && $(target + "-problem").hidden);
  }

  function onInputsChanged(target) {
    if (target === "layer") clearResults();
    $("gap-inputs").hidden = !$("check-gaps").checked;
    $("coverage-missing").hidden = usable("coverage");
    updateRunState();
  }

  function updateRunState() {
    let hint = "";
    if (!S.layer.path || !S.layer.info) hint = "Choose a layer first.";
    else if (!usable("layer")) hint = "This layer cannot be checked. See the note above.";
    else if (!S.layer.info.has_crs && !assumeCrs()) hint = "Declare the layer's CRS to continue.";
    else if (!$("check-overlaps").checked && !$("check-gaps").checked) hint = "Tick at least one check.";
    else if ($("check-gaps").checked && !usable("coverage")) {
      hint = "The gap check needs a coverage layer. Choose one, or untick Gaps to check overlaps only.";
    }
    $("run").disabled = !!hint || S.busy;
    $("run-hint").textContent = S.busy ? "" : hint;
  }

  // -------------------------------------------------------------------- run
  async function run() {
    S.busy = true;
    clearResults();
    updateRunState();
    $("progress").hidden = false;
    setProgress("Starting", 0);
    const gaps = $("check-gaps").checked;
    const body = {
      path: S.layer.path,
      layer: S.layer.info.name,
      id_field: $("id-field").value,
      assume_crs: assumeCrs(),
      check_overlaps: $("check-overlaps").checked,
      check_gaps: gaps,
      coverage: gaps && usable("coverage") ? { path: S.coverage.path, layer: S.coverage.info.name } : null,
      min_overlap_area_m2: parseFloat($("min-overlap").value || "0"),
      min_gap_area_m2: parseFloat($("min-gap").value || "0"),
      repair_invalid: $("repair").checked,
    };
    try {
      await api("/api/scan", { body });
      let job;
      do {
        await new Promise((r) => setTimeout(r, 250));
        job = await api("/api/job");
        setProgress(job.stage, job.fraction);
      } while (job.state === "running");
      S.summary = job.summary;
      S.exportDefault = job.export_default || "";
      S.findings = job.summary.status === "failed" ? [] : (await api("/api/findings")).features;
    } catch (e) {
      S.summary = { status: "failed", message: e.message, checks: {}, warnings: [], skipped: [], counts_by_type: {} };
      S.findings = [];
    }
    S.busy = false;
    $("progress").hidden = true;
    updateRunState();
    renderResults();
  }

  function setProgress(stage, fraction) {
    $("bar-fill").style.width = Math.round((fraction || 0) * 100) + "%";
    $("progress-text").textContent = (stage || "Working") + "…";
  }

  // ---------------------------------------------------------------- results
  function clearResults() {
    S.summary = null; S.findings = []; S.selected = null; S.filter = new Set();
    $("step-results").hidden = true;
    $("export-done").textContent = "";
    layers.findings.clearLayers(); layers.highlight.clearLayers(); layers.dots.clearLayers();
    updateLegend();
  }

  function renderResults() {
    const s = S.summary;
    $("step-results").hidden = false;
    const status = $("status");
    status.className = "status " + s.status;
    status.replaceChildren(el("span", { class: "kind", text: STATUS_NAMES[s.status] || s.status }), s.message);
    status.dataset.status = s.status;

    const lines = $("check-lines");
    lines.replaceChildren();
    Object.values(s.checks || {}).filter((c) => c.requested).forEach((c) => {
      const tag = { complete: "Complete", incomplete: "Incomplete", not_run: "Not run" }[c.status];
      lines.append(el("li", {},
        el("span", { class: "tag " + c.status, text: tag }),
        `${CHECK_NAMES[c.name]}: ${c.count} finding${c.count === 1 ? "" : "s"}. ${c.message}`));
    });

    const warnings = $("warnings");
    warnings.replaceChildren();
    (s.warnings || []).forEach((w) => warnings.append(el("div", { class: "note warn", text: w })));

    const skipped = s.skipped || [];
    $("skipped-wrap").hidden = !skipped.length;
    $("skipped-summary").textContent = `${skipped.length} skipped feature${skipped.length === 1 ? "" : "s"}`;
    const list = $("skipped-list");
    list.replaceChildren();
    skipped.forEach((k) => list.append(el("li", { text: `${featureLabel(k.fid, k.id)}: ${k.problem}. ${k.effect}` })));

    $("area-method").textContent = s.area_method ? `Areas are in square metres. ${s.area_method}` : "";
    const failed = s.status === "failed";
    $("filters").hidden = failed;
    $("findings").hidden = failed;
    $("export").hidden = failed;
    renderFilters();
    renderFindings();
    drawFindings();
    updateLegend();
    $("step-results").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function visibleFindings() {
    return S.findings.filter((f) => !S.filter.size || S.filter.has(f.properties.issue_type));
  }

  function renderFilters() {
    const box = $("filters");
    box.replaceChildren();
    const counts = S.summary.counts_by_type || {};
    const types = Object.keys(counts);
    if (types.length < 1) return;
    const total = S.findings.length;
    box.append(el("button", {
      class: "chip", "aria-pressed": String(!S.filter.size), "data-type": "all",
      onclick: () => { S.filter.clear(); applyFilter(); },
    }, `All (${total})`));
    Object.keys(S.config.issue_types).filter((t) => counts[t]).forEach((t) => {
      box.append(el("button", {
        class: "chip", "aria-pressed": String(S.filter.has(t)), "data-type": t,
        onclick: () => { S.filter.has(t) ? S.filter.delete(t) : S.filter.add(t); applyFilter(); },
      }, el("span", { class: "swatch", style: `background:${COLORS[t]}` }), `${S.config.issue_types[t]} (${counts[t]})`));
    });
  }

  function applyFilter() {
    if (S.selected !== null && !visibleFindings().some((f) => f.properties.finding_id === S.selected)) {
      S.selected = null;
      layers.highlight.clearLayers();
    }
    renderFilters(); renderFindings(); drawFindings();
  }

  function idsText(p) {
    if (p.check === "gap") return p.related_fids ? `Borders FID ${p.related_fids}` : "No bordering features";
    const a = featureLabel(p.fid_a, p.id_a);
    return p.fid_b === null || p.fid_b === undefined ? a : `${a} and ${featureLabel(p.fid_b, p.id_b)}`;
  }

  function renderFindings() {
    const list = $("findings");
    list.replaceChildren();
    const shown = visibleFindings();
    $("export").textContent = `Export ${shown.length} finding${shown.length === 1 ? "" : "s"}…`;
    if (!S.findings.length) return;
    shown.forEach((f) => {
      const p = f.properties;
      const selected = p.finding_id === S.selected;
      const button = el("button", {
        class: "finding-btn", "aria-expanded": String(selected),
        onclick: () => select(selected ? null : p.finding_id),
      },
        el("span", { class: "swatch", style: `background:${COLORS[p.issue_type]}` }),
        el("span", { class: "what" }, p.label, el("span", { class: "ids", text: idsText(p) })),
        el("span", { class: "area", text: fmtArea(p.area_m2) }));
      const li = el("li", { class: selected ? "selected" : "", "data-id": p.finding_id, "data-type": p.issue_type }, button);
      if (selected) li.append(detail(f));
      list.append(li);
    });
  }

  function detail(f) {
    const p = f.properties;
    const dl = el("dl");
    const add = (k, v) => dl.append(el("dt", { text: k }), el("dd", { text: v }));
    add("Check", CHECK_NAMES[p.check] || p.check);
    add("Issue", p.label);
    add("Features", idsText(p));
    if (p.area_m2 !== null) {
      const share = p.overlap_ratio !== null && p.check === "overlap"
        ? ` (${(p.overlap_ratio * 100).toFixed(1)}% of the smaller feature)` : "";
      add("Area", fmtArea(p.area_m2) + share);
    }
    add("Why", p.reason);
    if (!f.geometry) add("Map", "This feature has no polygon geometry to show.");
    return el("div", { class: "detail" }, dl);
  }

  function findingStyle(type, selected) {
    return {
      color: COLORS[type], weight: selected ? 4 : 2, fillColor: COLORS[type],
      fillOpacity: selected ? 0.75 : 0.55, dashArray: type === "invalid_geometry" ? "5 4" : null,
    };
  }

  function drawFindings() {
    layers.findings.clearLayers();
    layers.dots.clearLayers();
    visibleFindings().filter((f) => f.geometry).forEach((f) => {
      const p = f.properties;
      const selected = p.finding_id === S.selected;
      const shape = L.geoJSON(f, { pane: "finding", style: findingStyle(p.issue_type, selected) });
      shape.on("click", () => select(p.finding_id));
      shape.bindTooltip(`${p.label} · ${fmtArea(p.area_m2)}`, { sticky: true });
      layers.findings.addLayer(shape);
      // A dot keeps small findings visible and clickable at every zoom.
      const b = f.bbox;
      const dot = L.circleMarker([(b[1] + b[3]) / 2, (b[0] + b[2]) / 2], {
        pane: "dot", radius: selected ? 9 : 6, color: "#fff", weight: 2,
        fillColor: COLORS[p.issue_type], fillOpacity: 1,
      });
      dot.on("click", () => select(p.finding_id));
      dot.bindTooltip(`${p.label} · ${fmtArea(p.area_m2)}`);
      layers.dots.addLayer(dot);
    });
  }

  async function select(id) {
    S.selected = id;
    renderFindings();
    drawFindings();
    layers.highlight.clearLayers();
    if (id === null) return;
    const f = S.findings.find((x) => x.properties.finding_id === id);
    const li = document.querySelector(`#findings li[data-id="${id}"]`);
    if (li) li.scrollIntoView({ block: "nearest" });
    if (f.bbox) fitTo(f.bbox);
    const p = f.properties;
    const fids = [p.fid_a, p.fid_b].filter((v) => v !== null && v !== undefined);
    if (p.check === "gap" && p.related_fids) {
      p.related_fids.split(",").forEach((v) => fids.push(parseInt(v, 10)));
    }
    if (!fids.length || !S.layer.info) return;
    try {
      const data = await api("/api/features?" + qs({
        path: S.layer.path, layer: S.layer.info.name, assume_crs: assumeCrs(), fids: fids.join(","),
      }));
      if (S.selected !== id) return;
      const labelled = p.check !== "gap";
      L.geoJSON(data, {
        pane: "highlight", interactive: false,
        style: { color: "#121417", weight: 3, fill: false, dashArray: labelled ? null : "2 6" },
        onEachFeature: (feature, layer) => {
          if (labelled) {
            layer.bindTooltip(`FID ${feature.properties.fid}`, {
              permanent: true, direction: "center", className: "fid-label", pane: "highlight",
            });
          }
        },
      }).addTo(layers.highlight);
    } catch (e) { /* highlighting is a convenience; the finding itself is shown */ }
  }

  // ----------------------------------------------------------------- export
  function startExport() {
    const sep = S.exportDefault.includes("\\") ? "\\" : "/";
    const cut = S.exportDefault.lastIndexOf(sep);
    openDialog({
      mode: "save",
      title: "Save findings",
      dir: cut > 0 ? S.exportDefault.slice(0, cut) : "",
      name: cut >= 0 ? S.exportDefault.slice(cut + 1) : "ovc_findings.gpkg",
    });
  }

  async function saveExport() {
    const name = $("dialog-name").value.trim();
    const error = $("dialog-error");
    error.hidden = true;
    if (!name) { error.textContent = "Enter a file name."; error.hidden = false; return; }
    const typed = $("dialog-dir").value.trim();
    if (typed && typed !== dialog.dir) {
      // A folder was typed but not opened yet: save there, not in the old one.
      const wasOverwrite = dialog.overwrite;
      await browseTo(typed);
      if (dialog.dir !== typed && !error.hidden) return;
      dialog.overwrite = wasOverwrite && false;
    }
    const sep = dialog.dir.includes("\\") ? "\\" : "/";
    const path = dialog.dir.endsWith(sep) ? dialog.dir + name : dialog.dir + sep + name;
    try {
      const done = await api("/api/export", {
        body: { path, overwrite: dialog.overwrite, issue_types: S.filter.size ? [...S.filter] : null },
      });
      closeDialog();
      $("export-done").textContent = `Saved ${done.count} finding${done.count === 1 ? "" : "s"} to ${done.path} (${done.crs}).`;
    } catch (e) {
      if (e.code === "exists") {
        dialog.overwrite = true;
        $("dialog-save-btn").textContent = "Replace file";
        error.textContent = `${e.message} Press "Replace file" to overwrite it, or change the name.`;
      } else {
        error.textContent = e.message;
      }
      error.hidden = false;
    }
  }

  // ------------------------------------------------------------------- wire
  $("choose-layer").addEventListener("click", () => openDialog({
    mode: "open", title: "Choose the layer to check", onPick: (p) => chooseFile("layer", p),
  }));
  $("choose-coverage").addEventListener("click", () => openDialog({
    mode: "open", title: "Choose the coverage layer", onPick: (p) => chooseFile("coverage", p),
    dir: S.layer.path ? S.layer.path.replace(/[\\/][^\\/]*$/, "") : "",
  }));
  $("use-sample").addEventListener("click", async () => {
    await chooseFile("layer", S.config.sample, "parcels");
    $("id-field").value = "parcel_ref";
    $("check-gaps").checked = true;
    await chooseFile("coverage", S.config.sample, "block");
  });
  $("layer-select").addEventListener("change", () => {
    onLayerSelected("layer");
    if (S.coverage.info) onLayerSelected("coverage");
  });
  $("coverage-select").addEventListener("change", () => onLayerSelected("coverage"));
  $("assume-crs").addEventListener("change", () => { onInputsChanged("layer"); showLayerOnMap("layer"); });
  $("assume-crs").addEventListener("input", updateRunState);
  ["check-overlaps", "check-gaps"].forEach((id) => $(id).addEventListener("change", () => onInputsChanged("checks")));
  $("run").addEventListener("click", run);
  $("export").addEventListener("click", startExport);
  $("dialog-save-btn").addEventListener("click", saveExport);
  $("quit").addEventListener("click", async () => {
    try { await api("/api/quit", { body: {} }); } catch (e) { /* already stopped */ }
    document.body.replaceChildren(el("p", { style: "padding:40px;font-size:16px", text: "OVC has stopped. You can close this tab." }));
  });
  setInterval(() => api("/api/ping").catch(() => {}), 20000);
  window.addEventListener("pagehide", () => navigator.sendBeacon("/api/bye?" + qs({ t: TOKEN })));

  window.ovcApp = { map, layers, state: S }; // for automated UI tests

  api("/api/config").then((config) => {
    S.config = config;
    $("version").textContent = "v" + config.version;
    $("min-overlap").value = config.defaults.min_area_m2;
    $("min-gap").value = config.defaults.min_area_m2;
    updateLegend();
    updateRunState();
    document.body.dataset.ready = "1";
  }).catch((e) => {
    document.body.replaceChildren(el("p", { style: "padding:40px;font-size:16px", text: e.message }));
  });
})();
