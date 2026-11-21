/* OVC map app. Talks to the local OVC server; no data leaves this computer. */
(function () {
  "use strict";

  const STARTED = Date.now();
  const TOKEN = new URLSearchParams(location.search).get("t") || "";
  const COLORS = {}; // issue type -> colour, filled from the server's issue registry
  const LAYER_COLORS = ["#7d8fa3", "#8aa37d", "#a38d7d", "#8f7da3", "#7da3a0", "#a3a07d"];
  const CHECK_NAMES = { overlap: "Overlap check", gap: "Gap check", input: "Input quality" };
  const STATUS_NAMES = { clean: "Clean", issues: "Issues found", partial: "Partial run", failed: "Failed" };

  const $ = (id) => document.getElementById(id);
  const S = {
    config: null,
    layers: [], // index 0 is drawn on top
    nextId: 1,
    active: null, // id of the layer highlighted in the Layers panel
    target: null, // id of the layer being checked
    coverage: null, // id of the coverage layer
    findingsVisible: true,
    summary: null,
    findings: [],
    filter: new Set(), // empty = show every issue type
    dismissed: new Set(),
    notes: {},
    selected: null,
    feature: null, // identify result
    tool: "pan",
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

  function icon(name) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", "#i-" + name);
    svg.append(use);
    return svg;
  }

  function iconButton(name, title, onclick, disabled) {
    const b = el("button", { class: "icon-btn", title, "aria-label": title, disabled: disabled ? "" : null, onclick });
    b.append(icon(name));
    return b;
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

  function fileName(path) { return path.replace(/^.*[\\/]/, ""); }
  function dirName(path) { return path.replace(/[\\/][^\\/]*$/, ""); }
  function layerById(id) { return S.layers.find((l) => l.id === id) || null; }
  function message(text) { $("sb-message").textContent = text || ""; }

  function assumeCrsInput() {
    const v = $("assume-crs").value.trim();
    if (!v) return "";
    return /^\d+$/.test(v) ? `EPSG:${v}` : v;
  }

  // -------------------------------------------------------------------- map
  const map = L.map("map", { maxZoom: 24, zoomSnap: 0.25, zoomControl: false }).setView([20, 10], 2);
  [["finding", 560], ["identify", 565], ["highlight", 570], ["dot", 580]].forEach(([name, z]) => {
    map.createPane(name).style.zIndex = z;
  });
  map.getPane("highlight").style.pointerEvents = "none";
  map.getPane("identify").style.pointerEvents = "none";
  L.control.scale({ imperial: false, maxWidth: 160 }).addTo(map);

  const osm = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 24, maxNativeZoom: 19, attribution: "© OpenStreetMap contributors",
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

  const overlays = {
    findings: L.layerGroup().addTo(map),
    identify: L.layerGroup().addTo(map),
    highlight: L.layerGroup().addTo(map),
    dots: L.layerGroup().addTo(map),
  };

  function fitTo(bounds) {
    if (!bounds) return;
    const go = () => map.fitBounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]], { padding: [40, 40], maxZoom: 22 });
    // Leaflet ignores a zoom requested while another is animating: queue it.
    if (map._animatingZoom) map.once("zoomend", go); else go();
  }

  function unionBounds(list) {
    const b = list.filter(Boolean);
    if (!b.length) return null;
    return [
      Math.min(...b.map((x) => x[0])), Math.min(...b.map((x) => x[1])),
      Math.max(...b.map((x) => x[2])), Math.max(...b.map((x) => x[3])),
    ];
  }

  map.on("mousemove", (e) => {
    $("sb-coords").textContent = `Lon, Lat: ${e.latlng.lng.toFixed(6)}, ${e.latlng.lat.toFixed(6)}`;
  });
  function updateScale() {
    const mpp = (156543.03392 * Math.cos((map.getCenter().lat * Math.PI) / 180)) / Math.pow(2, map.getZoom());
    const scale = Math.round(mpp / 0.000264583);
    $("sb-scale").textContent = "Scale: 1:" + scale.toLocaleString("en");
  }
  map.on("zoomend moveend", updateScale);

  // ----------------------------------------------------------------- layers
  function layerStyle(l) {
    return {
      color: l.color, weight: l.width, dashArray: l.dash ? "7 5" : null,
      fill: l.fill, fillColor: l.color, fillOpacity: l.opacity,
    };
  }

  function applyStyle(l) {
    l.group.setStyle(layerStyle(l));
  }

  function applyOrder() {
    const n = S.layers.length;
    S.layers.forEach((l, i) => { map.getPane(l.pane).style.zIndex = 400 + (n - i); });
  }

  function createLayer(path, info) {
    const existing = S.layers.find((l) => l.path === path && l.info.name === info.name);
    if (existing) return existing;
    const id = S.nextId++;
    const pane = "lyr" + id;
    map.createPane(pane);
    const renderer = L.canvas({ pane });
    const isLine = /line/i.test(info.geometry_type);
    const l = {
      id, path, info, pane, renderer,
      visible: true,
      color: LAYER_COLORS[(id - 1) % LAYER_COLORS.length],
      opacity: 0.4, width: isLine ? 2 : 1, fill: !isLine, dash: false, isLine,
      assumeCrs: "", bounds: null, error: "", truncated: false, adjust: false,
    };
    l.group = L.geoJSON(null, {
      pane, renderer, interactive: false,
      style: () => layerStyle(l),
      pointToLayer: (f, latlng) => L.circleMarker(latlng, { pane, renderer, radius: 4, interactive: false }),
    }).addTo(map);
    S.layers.unshift(l);
    applyOrder();
    return l;
  }

  async function loadLayerData(l, zoom) {
    const seq = (l.seq = (l.seq || 0) + 1);
    try {
      const data = await api("/api/preview?" + qs({ path: l.path, layer: l.info.name, assume_crs: l.assumeCrs }));
      if (seq !== l.seq || !layerById(l.id)) return;
      l.group.clearLayers();
      l.group.addData(data);
      l.bounds = data.bounds;
      l.truncated = data.truncated;
      l.error = "";
      $("map-hint").hidden = true;
      if (data.truncated) {
        $("map-note").textContent =
          `${l.info.name} has ${data.total.toLocaleString("en")} features, too many to draw at once. ` +
          "All of them are checked; the features behind a finding are drawn when you select it.";
        $("map-note").hidden = false;
      }
      if (zoom) fitTo(l.bounds);
    } catch (e) {
      if (seq !== l.seq) return;
      l.group.clearLayers();
      l.bounds = null;
      l.error = e.message;
    }
    l.loaded = true;
    renderToc();
  }

  function removeLayer(id) {
    const l = layerById(id);
    if (!l) return;
    l.group.remove();
    if (map.hasLayer(l.renderer)) map.removeLayer(l.renderer); // or it keeps handling zooms
    const paneEl = map.getPane(l.pane);
    if (paneEl) paneEl.remove();
    delete map._panes[l.pane];
    S.layers = S.layers.filter((x) => x.id !== id);
    if (S.active === id) S.active = null;
    if (S.coverage === id) S.coverage = null;
    if (S.target === id) { S.target = null; clearResults(); }
    if (!S.layers.length) { $("map-hint").hidden = false; $("map-note").hidden = true; }
    refreshLayerUi();
    message(`Removed ${l.info.name} from the map. The file is unchanged.`);
  }

  function moveLayer(id, delta) {
    const i = S.layers.findIndex((l) => l.id === id);
    const j = i + delta;
    if (i < 0 || j < 0 || j >= S.layers.length) return;
    [S.layers[i], S.layers[j]] = [S.layers[j], S.layers[i]];
    applyOrder();
    renderToc();
  }

  function renderToc() {
    const toc = $("toc");
    toc.replaceChildren();
    $("toc-empty").hidden = S.layers.length > 0;

    if (S.findings.length) {
      const box = el("input", { type: "checkbox", id: "toc-findings", title: "Show or hide findings" });
      box.checked = S.findingsVisible;
      box.addEventListener("change", () => { S.findingsVisible = box.checked; drawFindings(); });
      const li = el("li", { class: "toc-findings" },
        el("div", { class: "toc-row" }, box,
          el("span", { class: "toc-name" }, "Findings", el("small", { text: `${visibleFindings().length} shown` }))));
      const sub = el("ul", { class: "toc-sub" });
      [...new Set(S.findings.map((f) => f.properties.issue_type))].forEach((t) => {
        sub.append(el("li", {}, el("span", { class: "swatch", style: `background:${COLORS[t]}` }), S.config.issue_types[t] || t));
      });
      li.append(sub);
      toc.append(li);
    }

    S.layers.forEach((l, i) => {
      const box = el("input", { type: "checkbox", title: "Show or hide this layer" });
      box.checked = l.visible;
      box.addEventListener("change", () => {
        l.visible = box.checked;
        l.visible ? l.group.addTo(map) : l.group.remove();
      });
      const swatch = el("span", {
        class: "toc-swatch" + (l.isLine ? " line" : ""),
        style: l.isLine ? `border-color:${l.color}` :
          `border-color:${l.color};${l.dash ? "border-style:dashed;" : ""}background:${l.fill ? l.color + "66" : "transparent"}`,
      });
      const name = el("button", {
        class: "toc-name", title: `${l.path}\n${l.info.geometry_type}, ${l.info.feature_count.toLocaleString("en")} features, CRS ${l.info.has_crs ? l.info.crs : "missing"}`,
        onclick: () => { S.active = S.active === l.id ? null : l.id; renderToc(); },
      }, l.info.name);
      const row = el("div", { class: "toc-row" }, box, swatch, name);
      if (l.id === S.target) row.append(el("span", { class: "badge", text: "Checked" }));
      if (l.id === S.coverage) row.append(el("span", { class: "badge cov", text: "Coverage" }));
      row.append(
        iconButton("zoomlayer", "Zoom to layer", () => fitTo(l.bounds), !l.bounds),
        iconButton("up", "Move up", () => moveLayer(l.id, -1), i === 0),
        iconButton("down", "Move down", () => moveLayer(l.id, 1), i === S.layers.length - 1),
        iconButton("style", "Symbology", () => { l.adjust = !l.adjust; renderToc(); }),
        iconButton("close", "Remove from the map (the file is not changed)", () => removeLayer(l.id)));
      const li = el("li", { class: l.id === S.active ? "active" : "", "data-layer": l.info.name, "data-id": l.id }, row);
      if (l.error) li.append(el("div", { class: "note warn", style: "margin:0 8px 6px 28px", text: l.error }));
      if (l.adjust) li.append(adjustPanel(l));
      toc.append(li);
    });
  }

  function adjustPanel(l) {
    const color = el("input", { type: "color", value: l.color });
    color.addEventListener("input", () => { l.color = color.value; applyStyle(l); });
    color.addEventListener("change", renderToc);
    const opacity = el("input", { type: "range", min: "0", max: "1", step: "0.05", value: String(l.opacity) });
    opacity.addEventListener("input", () => { l.opacity = parseFloat(opacity.value); applyStyle(l); });
    const width = el("input", { type: "range", min: "0.5", max: "5", step: "0.5", value: String(l.width) });
    width.addEventListener("input", () => { l.width = parseFloat(width.value); applyStyle(l); });
    const fill = el("input", { type: "checkbox" });
    fill.checked = l.fill;
    fill.addEventListener("change", () => { l.fill = fill.checked; applyStyle(l); renderToc(); });
    const dash = el("input", { type: "checkbox" });
    dash.checked = l.dash;
    dash.addEventListener("change", () => { l.dash = dash.checked; applyStyle(l); renderToc(); });
    const panel = el("div", { class: "toc-adjust" },
      el("span", { text: "Colour" }), color,
      el("span", { text: "Outline width" }), width);
    if (!l.isLine) {
      panel.append(el("span", { text: "Fill" }), fill, el("span", { text: "Fill opacity" }), opacity);
    }
    panel.append(el("span", { text: "Dashed outline" }), dash);
    return panel;
  }

  // ------------------------------------------------------ check form inputs
  function polygonLayers() {
    return S.layers.filter((l) => l.info.is_polygon && l.info.feature_count > 0);
  }

  function fillSelect(select, layers, value, emptyText) {
    select.replaceChildren();
    if (!layers.length) select.append(el("option", { value: "", text: emptyText }));
    layers.forEach((l) => {
      select.append(el("option", { value: String(l.id), text: `${l.info.name}  (${fileName(l.path)})` }));
    });
    select.value = value !== null && layers.some((l) => l.id === value) ? String(value) : (layers[0] ? String(layers[0].id) : "");
    select.disabled = !layers.length;
    return select.value ? parseInt(select.value, 10) : null;
  }

  function refreshLayerUi() {
    const candidates = polygonLayers();
    const before = S.target;
    S.target = fillSelect($("target-layer"), candidates, S.target, "No polygon layer added");
    const others = candidates.filter((l) => l.id !== S.target);
    S.coverage = fillSelect($("coverage-layer"), others, S.coverage, "No other polygon layer added");
    if (S.target !== before) onTargetChanged(); else { renderToc(); updateForm(); }
  }

  function onTargetChanged() {
    clearResults();
    const l = layerById(S.target);
    const dl = $("layer-facts");
    dl.replaceChildren();
    const idField = $("id-field");
    idField.replaceChildren(el("option", { value: "", text: "FID only" }));
    $("assume-crs").value = l ? l.assumeCrs.replace(/^EPSG:/, "") : "";
    if (l) {
      const add = (k, v) => dl.append(el("dt", { text: k }), el("dd", { text: v }));
      add("Features", l.info.feature_count.toLocaleString("en"));
      add("Geometry", l.info.geometry_type);
      add("CRS", l.info.has_crs ? l.info.crs : "Missing");
      l.info.fields.forEach((f) => idField.append(el("option", { value: f, text: f })));
    }
    $("crs-wrap").hidden = !(l && !l.info.has_crs);
    $("sb-crs").textContent = "Layer CRS: " + (l ? (l.info.has_crs ? l.info.crs : "missing") : "-");
    const others = polygonLayers().filter((x) => x.id !== S.target);
    S.coverage = fillSelect($("coverage-layer"), others, S.coverage, "No other polygon layer added");
    renderToc();
    updateForm();
  }

  function updateForm() {
    const gaps = $("check-gaps").checked;
    $("gap-inputs").hidden = !gaps;
    const cov = layerById(S.coverage);
    const problem = $("coverage-problem");
    problem.hidden = true;
    if (gaps && cov && !cov.info.has_crs) {
      problem.textContent = "This layer has no CRS, so it cannot be compared with the layer being checked. Define its CRS in the file.";
      problem.hidden = false;
    }
    $("coverage-missing").hidden = !!cov;
    updateRunState();
  }

  function coverageUsable() {
    const cov = layerById(S.coverage);
    return !!(cov && cov.info.has_crs);
  }

  function updateRunState() {
    const l = layerById(S.target);
    let hint = "";
    if (!l) hint = "Add a polygon layer first.";
    else if (!l.info.has_crs && !assumeCrsInput()) hint = "Declare the layer's CRS to continue.";
    else if (!$("check-overlaps").checked && !$("check-gaps").checked) hint = "Tick at least one check.";
    else if ($("check-gaps").checked && !coverageUsable()) {
      hint = "The gap check needs a coverage layer. Add one, or untick Gaps to check overlaps only.";
    }
    $("run").disabled = !!hint || S.busy;
    $("run-hint").textContent = S.busy ? "" : (hint || "Ready. Press Run checks.");
    updateTools();
  }

  function updateTools() {
    const hasResult = !!S.summary && S.summary.status !== "failed";
    $("export").disabled = !hasResult || S.busy;
    $("restore").disabled = !S.dismissed.size;
    $("delete-item").disabled = S.selected === null && S.active === null;
    $("clear-selection").disabled = S.selected === null && !S.feature;
    $("zoom-layer").disabled = !(layerById(S.active) && layerById(S.active).bounds);
    $("zoom-selection").disabled = S.selected === null && !S.feature;
    $("zoom-full").disabled = !S.layers.some((l) => l.bounds);
  }

  function setCoverageStyle(l) {
    // The coverage area reads as a boundary: dashed outline, no fill, on top.
    Object.assign(l, { fill: false, dash: true, color: "#121417", width: 2 });
    applyStyle(l);
    S.layers = [l, ...S.layers.filter((x) => x.id !== l.id)];
    applyOrder();
  }

  // ---------------------------------------------------------- adding layers
  let pickBusy = false;

  async function pickPath(options) {
    // The operating system's own dialog when there is one, else the in-page browser.
    if (S.config.native_dialog && !options.inPage) {
      if (pickBusy) return null;
      pickBusy = true;
      message("Waiting for the file dialog…");
      try {
        const res = await api("/api/pick", {
          body: { mode: options.mode, title: options.title, initial_dir: options.dir || "", initial_name: options.name || "" },
        });
        if (res.native) return res.path ? { path: res.path, confirmed: true } : null;
      } catch (e) { /* fall through to the in-page browser */ } finally {
        pickBusy = false;
        message("");
      }
    }
    return new Promise((resolve) => openDialog(Object.assign({}, options, { resolve })));
  }

  async function addFile(path, wanted) {
    let data;
    try {
      data = await api("/api/layers?" + qs({ path }));
    } catch (e) {
      showModal("This file could not be opened", [el("p", { text: e.message }), el("p", { class: "path", text: path })],
        [{ text: "Close", primary: true }]);
      document.body.dataset.lastAdd = "error:" + path;
      return [];
    }
    let chosen = data.layers;
    if (wanted) chosen = data.layers.filter((i) => wanted.includes(i.name));
    else if (data.layers.length > 1) chosen = await chooseLayers(path, data.layers);
    const added = chosen.map((info) => createLayer(path, info));
    refreshLayerUi();
    const firstLoad = S.layers.length === added.length;
    await Promise.all(added.map((l) => loadLayerData(l, false)));
    if (added.length) {
      if (firstLoad) zoomFull(); else fitTo(unionBounds(added.map((l) => l.bounds)));
      S.active = added[0].id;
      renderToc();
      message(`Added ${added.map((l) => l.info.name).join(", ")}.`);
    }
    updateTools();
    document.body.dataset.lastAdd = "ok:" + path;
    return added;
  }

  function chooseLayers(path, infos) {
    return new Promise((resolve) => {
      const boxes = infos.map((info) => {
        const box = el("input", { type: "checkbox", value: info.name });
        box.checked = info.feature_count > 0;
        return el("label", { class: "pick" }, box,
          `${info.name}`, el("small", { style: "display:inline", text: `${info.geometry_type}, ${info.feature_count.toLocaleString("en")} features` }));
      });
      showModal("Select layers to add", [el("p", { class: "path", text: fileName(path) }), ...boxes], [
        { text: "Cancel", onclick: () => resolve([]) },
        {
          text: "Add layers", primary: true, id: "modal-ok",
          onclick: () => resolve(infos.filter((info, i) => boxes[i].querySelector("input").checked)),
        },
      ], () => resolve([]));
    });
  }

  async function addLayerFlow(inPage) {
    const last = localStorage.getItem("ovc-last-dir") || "";
    const picked = await pickPath({ mode: "open", title: "Add layer", dir: last, inPage });
    if (!picked) return;
    localStorage.setItem("ovc-last-dir", dirName(picked.path));
    await addFile(picked.path);
  }

  async function loadSample() {
    const added = await addFile(S.config.sample, ["parcels", "block"]);
    const parcels = added.find((l) => l.info.name === "parcels");
    const block = added.find((l) => l.info.name === "block");
    if (!parcels || !block) return;
    S.target = parcels.id;
    refreshLayerUi();
    onTargetChanged();
    $("id-field").value = "parcel_ref";
    $("check-gaps").checked = true;
    S.coverage = block.id;
    $("coverage-layer").value = String(block.id);
    setCoverageStyle(block);
    renderToc();
    updateForm();
    document.body.dataset.sample = "1";
  }

  // ---------------------------------------------------------------- modals
  function showModal(title, body, actions, onClose) {
    $("modal-title").textContent = title;
    $("modal-body").replaceChildren(...body);
    const bar = $("modal-actions");
    bar.replaceChildren();
    const close = () => { $("modal").hidden = true; };
    actions.forEach((a) => {
      bar.append(el("button", {
        class: a.primary ? "primary" : "", id: a.id || null, text: a.text,
        onclick: () => { close(); if (a.onclick) a.onclick(); },
      }));
    });
    $("modal-close").onclick = () => { close(); if (onClose) onClose(); };
    $("modal").hidden = false;
  }

  function showAbout() {
    const a = S.config.app;
    showModal("About OVC", [el("div", { class: "about" },
      el("img", { src: "/static/ovc-icon.png", alt: "" }),
      el("h4", { text: `${a.name} - ${a.title}` }),
      el("p", { text: `Version ${S.config.version}` }),
      el("p", { class: "org", text: a.organization }),
      el("p", { text: `Founded by ${a.founder}` }),
      el("p", { class: "fine", text: "Runs on this computer only. Input files are opened read-only. MIT License. Map display by Leaflet (BSD 2-Clause)." }),
    )], [{ text: "Close", primary: true }]);
  }

  // ----------------------------------------------- in-page file browser
  const dialog = { mode: "open", dir: null, overwrite: false, resolve: null };
  let browseSeq = 0;

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
    S.config.places.forEach((p) => places.append(el("button", { text: p.label, onclick: () => browseTo(p.path) })));
    delete $("dialog").dataset.dir;
    $("dialog").hidden = false;
    await browseTo(options.dir || "");
    (options.mode === "save" ? $("dialog-name") : $("dialog-dir")).focus();
  }

  function closeDialog(result) {
    $("dialog").hidden = true;
    if (dialog.resolve) { const r = dialog.resolve; dialog.resolve = null; r(result || null); }
  }

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
        onclick: () => (isDir ? browseTo(entry.path) : closeDialog({ path: entry.path })),
      }, el("span", { class: "kind", text: isDir ? "Folder" : "Layer" }), el("span", { text: entry.name }));
      list.append(el("li", {}, button));
    });
    if (!data.entries.length) list.append(el("li", { class: "empty-list", text: "No folders or vector files here." }));
  }

  async function goToTypedPath() {
    // A pasted path may be a folder or, when opening, the file itself.
    const typed = $("dialog-dir").value.trim().replace(/^"|"$/g, "");
    const lower = typed.toLowerCase();
    if (dialog.mode === "open" && S.config.extensions.some((x) => lower.endsWith(x))) {
      closeDialog({ path: typed });
      return;
    }
    await browseTo(typed);
  }

  async function saveFromDialog() {
    const name = $("dialog-name").value.trim();
    const error = $("dialog-error");
    error.hidden = true;
    if (!name) { error.textContent = "Enter a file name."; error.hidden = false; return; }
    const typed = $("dialog-dir").value.trim();
    if (typed && typed !== dialog.dir) {
      await browseTo(typed); // a folder was typed but not opened yet: save there
      if (dialog.dir !== typed && !error.hidden) return;
    }
    const sep = dialog.dir.includes("\\") ? "\\" : "/";
    const path = dialog.dir.endsWith(sep) ? dialog.dir + name : dialog.dir + sep + name;
    try {
      await exportTo(path, dialog.overwrite);
      closeDialog(null);
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

  // -------------------------------------------------------------------- run
  async function run() {
    const l = layerById(S.target);
    if (!l || $("run").disabled) return;
    S.busy = true;
    clearResults();
    updateRunState();
    $("progress").hidden = false;
    setProgress("Starting", 0);
    const gaps = $("check-gaps").checked;
    const cov = layerById(S.coverage);
    const body = {
      path: l.path,
      layer: l.info.name,
      id_field: $("id-field").value,
      assume_crs: l.info.has_crs ? "" : assumeCrsInput(),
      check_overlaps: $("check-overlaps").checked,
      check_gaps: gaps,
      coverage: gaps && cov ? { path: cov.path, layer: cov.info.name } : null,
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
  function showRightDock() {
    $("dock-right").hidden = $("step-results").hidden && $("panel-feature").hidden;
    map.invalidateSize();
  }

  function clearResults() {
    S.summary = null; S.findings = []; S.selected = null; S.filter = new Set();
    S.dismissed = new Set(); S.notes = {};
    $("step-results").hidden = true;
    $("export-done").textContent = "";
    overlays.findings.clearLayers(); overlays.highlight.clearLayers(); overlays.dots.clearLayers();
    showRightDock();
    renderToc();
    updateTools();
  }

  function renderResults() {
    const s = S.summary;
    $("step-results").hidden = false;
    showRightDock();
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
    refreshFindings();
    message(s.message);
  }

  function visibleFindings() {
    return S.findings.filter((f) =>
      !S.dismissed.has(f.properties.finding_id) && (!S.filter.size || S.filter.has(f.properties.issue_type)));
  }

  function refreshFindings() {
    if (S.selected !== null && !visibleFindings().some((f) => f.properties.finding_id === S.selected)) {
      S.selected = null;
      overlays.highlight.clearLayers();
    }
    renderFilters(); renderFindings(); drawFindings(); renderToc(); updateTools();
  }

  function renderFilters() {
    const box = $("filters");
    box.replaceChildren();
    const live = S.findings.filter((f) => !S.dismissed.has(f.properties.finding_id));
    const counts = {};
    live.forEach((f) => { counts[f.properties.issue_type] = (counts[f.properties.issue_type] || 0) + 1; });
    const note = $("dismissed-note");
    note.hidden = !S.dismissed.size;
    note.textContent = `${S.dismissed.size} finding${S.dismissed.size === 1 ? "" : "s"} dismissed. They are left out of the export; use Restore to bring them back.`;
    if (!Object.keys(counts).length) return;
    box.append(el("button", {
      class: "chip", "aria-pressed": String(!S.filter.size), "data-type": "all",
      onclick: () => { S.filter.clear(); refreshFindings(); },
    }, `All (${live.length})`));
    Object.keys(S.config.issue_types).filter((t) => counts[t]).forEach((t) => {
      box.append(el("button", {
        class: "chip", "aria-pressed": String(S.filter.has(t)), "data-type": t,
        onclick: () => { S.filter.has(t) ? S.filter.delete(t) : S.filter.add(t); refreshFindings(); },
      }, el("span", { class: "swatch", style: `background:${COLORS[t]}` }), `${S.config.issue_types[t]} (${counts[t]})`));
    });
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
    $("export").title = `Save ${shown.length} finding${shown.length === 1 ? "" : "s"} as a GIS layer (Ctrl+E)`;
    $("export").dataset.count = shown.length;
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
    const note = el("textarea", { placeholder: "Review note (saved with the export)", "aria-label": "Review note" });
    note.value = S.notes[p.finding_id] || "";
    note.addEventListener("input", () => { S.notes[p.finding_id] = note.value; });
    return el("div", { class: "detail" }, dl, note);
  }

  function findingStyle(type, selected) {
    return {
      color: COLORS[type], weight: selected ? 4 : 2, fillColor: COLORS[type],
      fillOpacity: selected ? 0.75 : 0.55, dashArray: type === "invalid_geometry" ? "5 4" : null,
    };
  }

  function drawFindings() {
    overlays.findings.clearLayers();
    overlays.dots.clearLayers();
    if (!S.findingsVisible) return;
    visibleFindings().filter((f) => f.geometry).forEach((f) => {
      const p = f.properties;
      const selected = p.finding_id === S.selected;
      const shape = L.geoJSON(f, { pane: "finding", style: findingStyle(p.issue_type, selected) });
      shape.on("click", (e) => { L.DomEvent.stop(e); select(p.finding_id); });
      shape.bindTooltip(`${p.label} · ${fmtArea(p.area_m2)}`, { sticky: true });
      overlays.findings.addLayer(shape);
      // A dot keeps small findings visible and clickable at every zoom.
      const b = f.bbox;
      const dot = L.circleMarker([(b[1] + b[3]) / 2, (b[0] + b[2]) / 2], {
        pane: "dot", radius: selected ? 9 : 6, color: "#fff", weight: 2,
        fillColor: COLORS[p.issue_type], fillOpacity: 1,
      });
      dot.on("click", (e) => { L.DomEvent.stop(e); select(p.finding_id); });
      dot.bindTooltip(`${p.label} · ${fmtArea(p.area_m2)}`);
      overlays.dots.addLayer(dot);
    });
  }

  async function select(id) {
    S.selected = id;
    renderFindings();
    drawFindings();
    overlays.highlight.clearLayers();
    updateTools();
    if (id === null) return;
    const f = S.findings.find((x) => x.properties.finding_id === id);
    const li = document.querySelector(`#findings li[data-id="${id}"]`);
    if (li) li.scrollIntoView({ block: "nearest" });
    if (f.bbox) fitTo(f.bbox);
    const p = f.properties;
    const fids = [p.fid_a, p.fid_b].filter((v) => v !== null && v !== undefined);
    if (p.check === "gap" && p.related_fids) p.related_fids.split(",").forEach((v) => fids.push(parseInt(v, 10)));
    const l = layerById(S.target);
    if (!fids.length || !l) return;
    try {
      const data = await api("/api/features?" + qs({
        path: l.path, layer: l.info.name, assume_crs: l.assumeCrs, fids: fids.join(","),
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
      }).addTo(overlays.highlight);
    } catch (e) { /* highlighting is a convenience; the finding itself is shown */ }
  }

  // --------------------------------------------------------------- identify
  function setTool(tool) {
    S.tool = tool;
    $("tool-pan").setAttribute("aria-pressed", String(tool === "pan"));
    $("tool-select").setAttribute("aria-pressed", String(tool === "select"));
    $("map").classList.toggle("tool-select", tool === "select");
    message(tool === "select" ? "Select: click a feature to see its attributes." : "");
  }

  function clearFeature() {
    S.feature = null;
    overlays.identify.clearLayers();
    $("panel-feature").hidden = true;
    showRightDock();
    updateTools();
  }

  async function identifyAt(latlng) {
    const p = map.latLngToContainerPoint(latlng);
    const tol = Math.abs(map.containerPointToLatLng([p.x + 5, p.y]).lng - latlng.lng);
    for (const l of S.layers.filter((x) => x.visible && !x.error)) {
      let res;
      try {
        res = await api("/api/identify?" + qs({
          path: l.path, layer: l.info.name, assume_crs: l.assumeCrs,
          lon: latlng.lng, lat: latlng.lat,
          tol: l.info.is_polygon && l.fill ? 0 : tol,
          edge: l.info.is_polygon && !l.fill ? "1" : "",
        }));
      } catch (e) { continue; }
      if (!res.feature) continue;
      S.feature = { layer: l.id, fid: res.fid, bounds: L.geoJSON(res.feature).getBounds() };
      overlays.identify.clearLayers();
      L.geoJSON(res.feature, {
        pane: "identify", interactive: false,
        style: { color: "#00b7ff", weight: 3, fillColor: "#00b7ff", fillOpacity: 0.15 },
        pointToLayer: (f, ll) => L.circleMarker(ll, { pane: "identify", radius: 7, interactive: false }),
      }).addTo(overlays.identify);
      $("feature-title").textContent = `${l.info.name} · FID ${res.fid} · ${res.geometry_type}`;
      const table = $("feature-table");
      table.replaceChildren();
      Object.entries(res.attributes).forEach(([k, v]) => {
        table.append(el("tr", {}, el("th", { text: k }), el("td", { text: v === null ? "NULL" : String(v) })));
      });
      if (!Object.keys(res.attributes).length) table.append(el("tr", {}, el("td", { text: "This layer has no attributes." })));
      $("panel-feature").hidden = false;
      $("panel-feature").dataset.fid = res.fid;
      showRightDock();
      updateTools();
      message(`Selected FID ${res.fid} in ${l.info.name}.`);
      return;
    }
    clearFeature();
    message("No feature here.");
  }

  map.on("click", (e) => { if (S.tool === "select") identifyAt(e.latlng); });

  // ------------------------------------------------------- toolbar actions
  function zoomFull() {
    fitTo(unionBounds(S.layers.filter((l) => l.visible).map((l) => l.bounds)));
  }

  function zoomSelection() {
    const f = S.findings.find((x) => x.properties.finding_id === S.selected);
    if (f && f.bbox) fitTo(f.bbox);
    else if (S.feature) map.fitBounds(S.feature.bounds, { padding: [60, 60], maxZoom: 22 });
  }

  function clearSelection() {
    if (S.selected !== null) select(null);
    clearFeature();
  }

  function deleteItem() {
    if (S.selected !== null) {
      S.dismissed.add(S.selected);
      S.selected = null;
      overlays.highlight.clearLayers();
      refreshFindings();
      message("Finding dismissed. It will be left out of the export.");
    } else if (S.active !== null) {
      removeLayer(S.active);
    }
  }

  function restoreDismissed() {
    S.dismissed = new Set();
    refreshFindings();
    message("Dismissed findings restored.");
  }

  // ----------------------------------------------------------------- export
  async function exportTo(path, overwrite) {
    const shown = visibleFindings();
    const notes = {};
    shown.forEach((f) => { if (S.notes[f.properties.finding_id]) notes[f.properties.finding_id] = S.notes[f.properties.finding_id]; });
    const done = await api("/api/export", {
      body: {
        path, overwrite,
        issue_types: S.filter.size ? [...S.filter] : null,
        finding_ids: S.dismissed.size ? shown.map((f) => f.properties.finding_id) : null,
        notes,
      },
    });
    const text = `Saved ${done.count} finding${done.count === 1 ? "" : "s"} to ${done.path} (${done.crs}).`;
    $("export-done").textContent = text;
    message(text);
    return done;
  }

  async function startExport() {
    if ($("export").disabled) return;
    const sep = S.exportDefault.includes("\\") ? "\\" : "/";
    const cut = S.exportDefault.lastIndexOf(sep);
    const picked = await pickPath({
      mode: "save", title: "Save findings",
      dir: cut > 0 ? S.exportDefault.slice(0, cut) : "",
      name: cut >= 0 ? S.exportDefault.slice(cut + 1) : "ovc_findings.gpkg",
    });
    if (!picked) return; // cancelled, or the in-page dialog saved it itself
    try {
      await exportTo(picked.path, true); // the system dialog already asked about replacing
    } catch (e) {
      showModal("The findings were not saved", [el("p", { text: e.message })], [{ text: "Close", primary: true }]);
    }
  }

  // ------------------------------------------------------------------- wire
  $("choose-layer").addEventListener("click", () => addLayerFlow(false));
  $("add-gdb").addEventListener("click", () => addLayerFlow(true));
  $("use-sample").addEventListener("click", loadSample);
  $("tool-pan").addEventListener("click", () => setTool("pan"));
  $("tool-select").addEventListener("click", () => setTool("select"));
  $("zoom-in").addEventListener("click", () => map.zoomIn());
  $("zoom-out").addEventListener("click", () => map.zoomOut());
  $("zoom-full").addEventListener("click", zoomFull);
  $("zoom-layer").addEventListener("click", () => { const l = layerById(S.active); if (l) fitTo(l.bounds); });
  $("zoom-selection").addEventListener("click", zoomSelection);
  $("clear-selection").addEventListener("click", clearSelection);
  $("delete-item").addEventListener("click", deleteItem);
  $("restore").addEventListener("click", restoreDismissed);
  $("run").addEventListener("click", run);
  $("export").addEventListener("click", startExport);
  $("about").addEventListener("click", showAbout);

  $("target-layer").addEventListener("change", () => {
    S.target = $("target-layer").value ? parseInt($("target-layer").value, 10) : null;
    onTargetChanged();
  });
  $("coverage-layer").addEventListener("change", () => {
    S.coverage = $("coverage-layer").value ? parseInt($("coverage-layer").value, 10) : null;
    const cov = layerById(S.coverage);
    if (cov) setCoverageStyle(cov);
    renderToc();
    updateForm();
  });
  $("assume-crs").addEventListener("change", () => {
    const l = layerById(S.target);
    if (l && !l.info.has_crs) { l.assumeCrs = assumeCrsInput(); loadLayerData(l, true); }
    clearResults();
    updateRunState();
  });
  $("assume-crs").addEventListener("input", updateRunState);
  $("check-overlaps").addEventListener("change", updateForm);
  $("check-gaps").addEventListener("change", () => {
    if ($("check-gaps").checked && layerById(S.coverage)) setCoverageStyle(layerById(S.coverage));
    renderToc();
    updateForm();
  });

  $("dialog-close").addEventListener("click", () => closeDialog(null));
  $("dialog-up").addEventListener("click", () => dialog.parent && browseTo(dialog.parent));
  $("dialog-go").addEventListener("click", goToTypedPath);
  $("dialog-dir").addEventListener("keydown", (e) => { if (e.key === "Enter") goToTypedPath(); });
  $("dialog-save-btn").addEventListener("click", saveFromDialog);
  $("dialog-name").addEventListener("input", () => {
    dialog.overwrite = false;
    $("dialog-save-btn").textContent = "Save";
    $("dialog-error").hidden = true;
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (!$("dialog").hidden) return closeDialog(null);
      if (!$("modal").hidden) return $("modal-close").click();
      return clearSelection();
    }
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
    if (!$("dialog").hidden || !$("modal").hidden) return;
    if (e.ctrlKey && e.key.toLowerCase() === "o") { e.preventDefault(); addLayerFlow(false); }
    else if (e.ctrlKey && e.key.toLowerCase() === "e") { e.preventDefault(); startExport(); }
    else if (e.key === "F5") { e.preventDefault(); run(); }
    else if (typing) return;
    else if (e.key === "Delete") deleteItem();
    else if (e.key.toLowerCase() === "s") setTool("select");
    else if (e.key.toLowerCase() === "p") setTool("pan");
    else if (e.key === "Home") zoomFull();
    else if (e.key === "+" || e.key === "=") map.zoomIn();
    else if (e.key === "-") map.zoomOut();
  });

  $("quit").addEventListener("click", async () => {
    try { await api("/api/quit", { body: {} }); } catch (e) { /* already stopped */ }
    document.body.replaceChildren(el("p", { style: "padding:40px;font-size:16px", text: "OVC has stopped. You can close this tab." }));
  });
  setInterval(() => api("/api/ping").catch(() => {}), 20000);
  window.addEventListener("pagehide", () => navigator.sendBeacon("/api/bye?" + qs({ t: TOKEN })));

  window.ovcApp = { map, overlays, state: S }; // for automated UI tests

  api("/api/config").then((config) => {
    S.config = config;
    Object.assign(COLORS, config.issue_colors);
    $("splash-version").textContent = "Version " + config.version;
    $("splash-org").textContent = config.app.organization;
    $("splash-founder").textContent = "Founded by " + config.app.founder;
    $("app-org").textContent = config.app.organization;
    $("min-overlap").value = config.defaults.min_area_m2;
    $("min-gap").value = config.defaults.min_area_m2;
    refreshLayerUi();
    updateScale();
    // Keep the splash up long enough to read, then hand over to the app.
    setTimeout(() => {
      $("splash").classList.add("done");
      document.body.dataset.ready = "1";
      setTimeout(() => $("splash").remove(), 400);
    }, Math.max(0, 1200 - (Date.now() - STARTED)));
  }).catch((e) => {
    document.body.replaceChildren(el("p", { style: "padding:40px;font-size:16px", text: e.message }));
  });
})();
