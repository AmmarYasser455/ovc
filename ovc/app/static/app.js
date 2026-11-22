/* OVC desktop app. Talks to the local OVC server; no data leaves this computer
   (except the optional update check to GitHub). */
(function () {
  "use strict";

  const STARTED = Date.now();
  const PARAMS = new URLSearchParams(location.search);
  const TOKEN = PARAMS.get("t") || "";
  const IN_WINDOW = PARAMS.get("w") === "1"; // OVC's own desktop window
  const TOOLBOX = window.OVC_TOOLBOX;
  const COLORS = {}; // issue type -> colour, from the server's issue registry
  const LAYER_COLORS = ["#6f8bab", "#7f9c6c", "#a6866b", "#8b78a6", "#5f9e9a", "#a59a5e"];
  const SELECT_COLOR = "#00e5ff"; // selection colour, as in desktop GIS
  const CHECK_NAMES = { overlap: "Overlap check", gap: "Gap check", input: "Input quality" };
  const STATUS_NAMES = { clean: "Clean", issues: "Issues found", partial: "Partial run", failed: "Failed" };

  const $ = (id) => document.getElementById(id);
  const S = {
    config: null,
    layers: [], // index 0 is drawn on top, as listed in Contents
    nextId: 1,
    active: null, // layer highlighted in Contents
    expanded: new Set(), // layers whose legend is shown
    runLayer: null, // layer the last run checked
    findingsVisible: true,
    summary: null,
    findings: [],
    filter: new Set(), // empty = every issue type
    dismissed: new Set(),
    notes: {},
    selected: null, // finding id
    feature: null, // selected map feature (Select tool)
    tool: "pan",
    exportDefault: "",
    busy: false,
    update: null,
    panes: [], // open panes in the right dock, in tab order
    pane: null, // active pane
    left: { width: 290, collapsed: false },
    right: { width: 370, collapsed: false },
    gp: { tool: null, values: {} },
    symLayer: null,
    theme: "light",
  };

  // ---------------------------------------------------------------- helpers
  async function api(path, options = {}) {
    const init = { method: options.method || "GET", headers: { "X-OVC-Token": TOKEN } };
    if (options.body !== undefined) {
      init.method = "POST";
      init.headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(options.body);
    }
    if (options.raw !== undefined) {
      init.method = "POST";
      init.headers["Content-Type"] = "application/octet-stream";
      init.body = options.raw;
    }
    let response;
    try {
      response = await fetch(path, init);
    } catch (e) {
      throw new Error(await whyFetchFailed());
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

  async function whyFetchFailed() {
    // Tell a dropped request apart from OVC having stopped.
    try {
      const ctl = new AbortController();
      setTimeout(() => ctl.abort(), 3000);
      const r = await fetch("/api/ping", { headers: { "X-OVC-Token": TOKEN }, signal: ctl.signal });
      if (r.ok) return "The request was interrupted before OVC answered. Try again.";
    } catch (e) { /* OVC is not answering */ }
    return "OVC has stopped. Close this window and open OVC again; it will offer to report what happened.";
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
    children.forEach((c) => c !== null && c !== undefined && node.append(c));
    return node;
  }

  function icon(name, cls) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    if (cls) svg.setAttribute("class", cls);
    const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", "#i-" + name);
    svg.append(use);
    return svg;
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
  function outlineColor() { return S.theme === "dark" ? "#f3eee4" : "#121417"; }
  function epsg(text) {
    const v = String(text || "").trim();
    return /^\d+$/.test(v) ? `EPSG:${v}` : v;
  }

  async function openExternal(url) {
    // In the analyst's own browser (signed in to GitHub), not inside OVC.
    try { await api("/api/open-url", { body: { url } }); } catch (e) { window.open(url, "_blank", "noopener"); }
  }

  // -------------------------------------------------------------------- map
  const map = L.map("map", { maxZoom: 24, zoomSnap: 0.25, zoomControl: true }).setView([20, 10], 2);
  [["finding", 560], ["highlight", 570], ["selection", 575], ["dot", 580]].forEach(([name, z]) => {
    map.createPane(name).style.zIndex = z;
  });
  map.getPane("highlight").style.pointerEvents = "none";
  map.getPane("selection").style.pointerEvents = "none";
  L.control.scale({ imperial: false, maxWidth: 160 }).addTo(map);

  const overlays = {
    findings: L.layerGroup().addTo(map),
    highlight: L.layerGroup().addTo(map),
    selection: L.layerGroup().addTo(map),
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
    $("sb-scale").textContent = "Scale: 1:" + Math.round(mpp / 0.000264583).toLocaleString("en");
  }
  map.on("zoomend moveend", updateScale);

  // ----------------------------------------------------------------- layers
  function layerStyle(l) {
    return {
      color: l.color, weight: l.width, dashArray: l.dash ? "7 5" : null,
      fill: l.fill, fillColor: l.color, fillOpacity: l.opacity,
    };
  }

  function applyStyle(l) { l.group.setStyle(layerStyle(l)); }

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
    const isPoint = /point/i.test(info.geometry_type);
    const l = {
      id, path, info, pane, renderer, visible: true,
      color: LAYER_COLORS[(id - 1) % LAYER_COLORS.length],
      opacity: 0.45, width: isLine ? 2 : 1, fill: !isLine, dash: false, isLine, isPoint,
      assumeCrs: "", bounds: null, error: "", truncated: false,
    };
    l.group = L.geoJSON(null, {
      pane, renderer, interactive: false,
      style: () => layerStyle(l),
      pointToLayer: (f, latlng) => L.circleMarker(latlng, { pane, renderer, radius: 4, interactive: false }),
    }).addTo(map);
    S.layers.unshift(l);
    S.expanded.add(id);
    applyOrder();
    markDirty();
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
      l.simplified = data.simplified;
      l.error = "";
      if (data.simplified) {
        message(`${l.info.name}: ${data.total.toLocaleString("en")} features, drawn simplified to screen detail. Checks use the exact shapes.`);
      }
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
      l.error = e.code === "no_crs"
        ? "No CRS: it cannot be drawn. Set its coordinate system in the tool that uses it."
        : e.message;
    }
    renderContents();
    updateTools();
  }

  function removeLayer(id) {
    const l = layerById(id);
    if (!l) return;
    l.group.remove();
    if (map.hasLayer(l.renderer)) map.removeLayer(l.renderer);
    const paneEl = map.getPane(l.pane);
    if (paneEl) paneEl.remove();
    delete map._panes[l.pane];
    S.layers = S.layers.filter((x) => x.id !== id);
    S.expanded.delete(id);
    markDirty();
    if (S.onLayerRemoved) S.onLayerRemoved(l);
    if (S.active === id) S.active = null;
    if (S.runLayer === id) clearResults();
    if (S.sel.layer === id) clearFeature();
    if (S.symLayer === id) { S.symLayer = null; closePane("symbology"); }
    if (!S.layers.length) { $("map-hint").hidden = false; $("map-note").hidden = true; }
    renderContents();
    renderToolForm();
    updateTools();
    message(`Removed ${l.info.name} from the map. The file is unchanged.`);
  }

  function moveLayer(id, toIndex) {
    const from = S.layers.findIndex((l) => l.id === id);
    if (from < 0) return;
    const to = Math.max(0, Math.min(S.layers.length - 1, toIndex));
    if (to === from) return;
    const [l] = S.layers.splice(from, 1);
    S.layers.splice(to, 0, l);
    applyOrder();
    renderContents();
    markDirty();
  }

  // --------------------------------------------------------------- contents
  function patch(l) {
    const style = l.isLine
      ? `border-color:${l.color}`
      : `border-color:${l.color};${l.dash ? "border-style:dashed;" : ""}background:${l.fill ? hexAlpha(l.color, l.opacity) : "transparent"}`;
    return el("span", { class: "patch" + (l.isLine ? " line" : ""), style });
  }

  function hexAlpha(hex, alpha) {
    const a = Math.round(Math.max(0, Math.min(1, alpha)) * 255).toString(16).padStart(2, "0");
    return hex + a;
  }

  function caret(open, onclick, none) {
    const b = el("button", { class: "caret" + (open ? " open" : "") + (none ? " none" : ""), tabindex: "-1", "aria-label": open ? "Collapse" : "Expand", onclick });
    b.append(icon("caret"));
    return b;
  }

  function renderContents() {
    const toc = $("toc");
    toc.replaceChildren();
    $("toc-empty").hidden = S.layers.length > 0;
    if (!S.layers.length && !S.findings.length) return;

    const mapNode = el("li", { role: "treeitem", "aria-expanded": "true" },
      el("div", { class: "node" }, caret(true, null, true), icon("map", "kind"), el("span", { class: "label", text: "Map" })));
    const list = el("ul", { role: "group" });

    if (S.findings.length) {
      const open = S.expanded.has("findings");
      const box = el("input", { type: "checkbox", id: "toc-findings", title: "Show or hide findings" });
      box.checked = S.findingsVisible;
      box.addEventListener("change", () => { S.findingsVisible = box.checked; drawFindings(); });
      const li = el("li", { class: "toc-findings", role: "treeitem" },
        el("div", { class: "node" },
          caret(open, () => { open ? S.expanded.delete("findings") : S.expanded.add("findings"); renderContents(); }),
          box, el("span", { class: "label" }, "Findings", el("small", { text: `(${visibleFindings().length})` }))));
      if (open) {
        [...new Set(S.findings.map((f) => f.properties.issue_type))].forEach((t) => {
          li.append(el("div", { class: "legend" }, el("span", { class: "swatch", style: `background:${COLORS[t]}` }), S.config.issue_types[t] || t));
        });
      }
      list.append(li);
    }

    S.layers.forEach((l) => {
      const open = S.expanded.has(l.id);
      const box = el("input", { type: "checkbox", title: "Show or hide this layer" });
      box.checked = l.visible;
      box.addEventListener("click", (e) => e.stopPropagation());
      box.addEventListener("change", () => {
        l.visible = box.checked;
        markDirty();
        l.visible ? l.group.addTo(map) : l.group.remove();
      });
      const node = el("div", {
        class: "node" + (l.id === S.active ? " active" : ""),
        title: `${l.path}\n${l.info.geometry_type} · ${l.info.feature_count.toLocaleString("en")} features · CRS ${l.info.has_crs ? l.info.crs : "missing"}`,
        onclick: () => { S.active = l.id; renderContents(); updateTools(); },
        ondblclick: () => openSymbology(l.id),
        oncontextmenu: (e) => { e.preventDefault(); S.active = l.id; renderContents(); updateTools(); showContextMenu(e.clientX, e.clientY, l); },
      },
        caret(open, (e) => { e.stopPropagation(); open ? S.expanded.delete(l.id) : S.expanded.add(l.id); renderContents(); }),
        box, el("span", { class: "label", text: l.info.name }),
        l.error ? el("span", { class: "warn-dot", title: l.error }) : null);
      const li = el("li", { role: "treeitem", draggable: "true", "data-layer": l.info.name, "data-id": l.id }, node);
      if (open) li.append(el("div", { class: "legend" }, patch(l), l.info.geometry_type));
      if (l.error) li.append(el("div", { class: "error", text: l.error }));
      wireDrag(li, l);
      list.append(li);
    });
    mapNode.append(list);
    toc.append(mapNode);
  }

  let dragId = null;
  function wireDrag(li, l) {
    li.addEventListener("dragstart", (e) => { dragId = l.id; e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", String(l.id)); });
    li.addEventListener("dragend", () => { dragId = null; clearDropMarks(); });
    li.addEventListener("dragover", (e) => {
      if (dragId === null || dragId === l.id) return;
      e.preventDefault();
      const r = li.getBoundingClientRect();
      clearDropMarks();
      li.classList.add(e.clientY < r.top + r.height / 2 ? "drop-before" : "drop-after");
    });
    li.addEventListener("drop", (e) => {
      e.preventDefault();
      if (dragId === null) return;
      const before = li.classList.contains("drop-before");
      clearDropMarks();
      const target = S.layers.findIndex((x) => x.id === l.id);
      const from = S.layers.findIndex((x) => x.id === dragId);
      let to = before ? target : target + 1;
      if (from < to) to -= 1;
      moveLayer(dragId, to);
      dragId = null;
    });
  }
  function clearDropMarks() {
    document.querySelectorAll(".drop-before, .drop-after").forEach((n) => n.classList.remove("drop-before", "drop-after"));
  }

  // ---- context menu
  let ctxLayer = null;
  function showContextMenu(x, y, l) {
    ctxLayer = l;
    const menu = $("ctx");
    const i = S.layers.indexOf(l);
    menu.querySelector('[data-ctx="zoom"]').setAttribute("aria-disabled", String(!l.bounds));
    menu.querySelector('[data-ctx="up"]').setAttribute("aria-disabled", String(i === 0));
    menu.querySelector('[data-ctx="down"]').setAttribute("aria-disabled", String(i === S.layers.length - 1));
    menu.hidden = false;
    const w = menu.offsetWidth, h = menu.offsetHeight;
    menu.style.left = Math.min(x, innerWidth - w - 4) + "px";
    menu.style.top = Math.min(y, innerHeight - h - 4) + "px";
  }
  function hideContextMenu() { $("ctx").hidden = true; ctxLayer = null; }
  $("ctx").addEventListener("click", (e) => {
    const item = e.target.closest("[data-ctx]");
    if (!item || !ctxLayer) return;
    const l = ctxLayer;
    hideContextMenu();
    const i = S.layers.indexOf(l);
    ({
      zoom: () => fitTo(l.bounds),
      symbology: () => openSymbology(l.id),
      properties: () => showProperties(l),
      up: () => moveLayer(l.id, i - 1),
      down: () => moveLayer(l.id, i + 1),
      remove: () => removeLayer(l.id),
      edit: () => { S.active = l.id; renderContents(); if (S.startEditing) S.startEditing(l); },
      export: () => { if (S.exportLayer) S.exportLayer(l); },
    })[item.dataset.ctx]();
  });
  document.addEventListener("mousedown", (e) => { if (!e.target.closest("#ctx")) hideContextMenu(); });

  function showProperties(l) {
    const rows = [
      ["Source", l.path], ["Layer", l.info.name], ["Geometry", l.info.geometry_type],
      ["Features", l.info.feature_count.toLocaleString("en")], ["Coordinate system", l.info.has_crs ? l.info.crs : "Missing"],
      ["Fields", l.info.fields.length ? l.info.fields.join(", ") : "None"],
    ];
    const table = el("table", { class: "attrs" });
    rows.forEach(([k, v]) => table.append(el("tr", {}, el("th", { text: k }), el("td", { text: v }))));
    showModal(`Layer Properties: ${l.info.name}`, [table], [{ text: "Close", primary: true }]);
  }

  // ---- symbology pane
  function openSymbology(id) {
    const l = layerById(id);
    if (!l) return;
    S.symLayer = id;
    $("sym-layer").textContent = l.info.name;
    $("sym-color").value = l.color;
    $("sym-width").value = String(l.width);
    $("sym-fill").checked = l.fill;
    $("sym-opacity").value = String(1 - l.opacity);
    $("sym-dash").checked = l.dash;
    document.querySelectorAll("#pane-symbology .sym-fill").forEach((n) => { n.hidden = l.isLine; });
    openPane("symbology");
  }
  function symChanged() {
    const l = layerById(S.symLayer);
    if (!l) return;
    l.color = $("sym-color").value;
    l.width = parseFloat($("sym-width").value);
    l.fill = $("sym-fill").checked;
    l.opacity = 1 - parseFloat($("sym-opacity").value);
    l.dash = $("sym-dash").checked;
    l.autoOutline = false; // the analyst chose this colour
    applyStyle(l);
    renderContents();
    markDirty();
  }
  ["sym-color", "sym-width", "sym-fill", "sym-opacity", "sym-dash"].forEach((id) => $(id).addEventListener("input", symChanged));

  function setCoverageStyle(l) {
    // The coverage area reads as a boundary: dashed outline, no fill.
    Object.assign(l, { fill: false, dash: true, color: outlineColor(), width: 2, autoOutline: true });
    applyStyle(l);
  }

  // ------------------------------------------------------------- dock panes
  function openPane(name) {
    if (!S.panes.includes(name)) S.panes.push(name);
    S.pane = name;
    S.paneJustOpened = true;
    renderDock();
  }
  function closePane(name) {
    S.panes = S.panes.filter((p) => p !== name);
    if (S.pane === name) S.pane = S.panes[S.panes.length - 1] || null;
    renderDock();
  }
  function renderDock() {
    if (S.panes.length && S.pane) S.right.collapsed = S.right.collapsed && !S.paneJustOpened;
    S.paneJustOpened = false;
    const tabs = $("dock-tabs");
    tabs.replaceChildren();
    S.panes.forEach((name) => {
      const section = $("pane-" + name);
      tabs.append(el("button", {
        class: "dock-tab", role: "tab", "data-pane": name, "aria-selected": String(name === S.pane),
        text: section.dataset.title, onclick: () => { S.pane = name; renderDock(); },
      }));
    });
    ["geoprocessing", "results", "attributes", "symbology"].forEach((name) => { $("pane-" + name).hidden = name !== S.pane; });
    layoutDocks();
  }
  $("dock-close").addEventListener("click", () => S.pane && closePane(S.pane));
  $("dock-collapse").addEventListener("click", () => { S.right.collapsed = true; layoutDocks(); });

  // ---- splitters and rails: drag a pane narrow to tuck it away, click its rail to bring it back
  const DOCK_MIN = 200, DOCK_MAX = 640, COLLAPSE_AT = 120;

  function layoutDocks() {
    const before = [$("dock-left").offsetWidth, $("dock-right").offsetWidth].join();
    const L = S.left, R = S.right;
    $("dock-left").hidden = L.collapsed;
    $("split-left").hidden = L.collapsed;
    $("rail-left").hidden = !L.collapsed;
    $("dock-left").style.width = L.width + "px";
    const hasPanes = S.panes.length > 0;
    $("dock-right").hidden = !hasPanes || R.collapsed;
    $("split-right").hidden = !hasPanes || R.collapsed;
    $("rail-right").hidden = !hasPanes || !R.collapsed;
    $("dock-right").style.width = R.width + "px";
    if (S.pane) $("rail-right-label").textContent = $("pane-" + S.pane).dataset.title;
    const after = [$("dock-left").offsetWidth, $("dock-right").offsetWidth].join();
    if (before !== after) map.invalidateSize();
    if (S.settings && S.ready) saveSettings({ docks: { left: { width: L.width, collapsed: L.collapsed }, right: { width: R.width, collapsed: R.collapsed } } });
  }

  function setContents(open) { S.left.collapsed = !open; layoutDocks(); }
  $("contents-close").addEventListener("click", () => setContents(false));
  $("rail-left").addEventListener("click", () => setContents(true));
  $("rail-right").addEventListener("click", () => { S.right.collapsed = false; layoutDocks(); });

  function wireSplitter(id, side) {
    const bar = $(id);
    bar.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      bar.setPointerCapture(e.pointerId);
      bar.classList.add("dragging");
      const move = (ev) => {
        const width = side === "left" ? ev.clientX - $("dock-left").getBoundingClientRect().left
          : $("dock-right").getBoundingClientRect().right - ev.clientX;
        if (width < COLLAPSE_AT) { S[side].collapsed = true; stop(); }
        else S[side].width = Math.round(Math.max(DOCK_MIN, Math.min(DOCK_MAX, width)));
        layoutDocks();
      };
      const stop = () => {
        bar.classList.remove("dragging");
        bar.removeEventListener("pointermove", move);
        bar.removeEventListener("pointerup", stop);
        map.invalidateSize();
      };
      bar.addEventListener("pointermove", move);
      bar.addEventListener("pointerup", stop);
    });
    bar.addEventListener("keydown", (e) => {
      const step = e.key === "ArrowLeft" ? -20 : e.key === "ArrowRight" ? 20 : 0;
      if (!step) return;
      S[side].width = Math.max(DOCK_MIN, Math.min(DOCK_MAX, S[side].width + (side === "left" ? step : -step)));
      layoutDocks();
    });
    bar.addEventListener("dblclick", () => { S[side].collapsed = true; layoutDocks(); });
  }
  wireSplitter("split-left", "left");
  wireSplitter("split-right", "right");

  // ---------------------------------------------------------------- toolbox
  function allTools() {
    return TOOLBOX.toolsets.flatMap((set) => set.tools.map((t) => Object.assign({ toolset: set.name }, t)));
  }

  function renderToolTree() {
    const filter = $("gp-search").value.trim().toLowerCase();
    const tree = $("gp-tree");
    tree.replaceChildren();
    const box = el("li", { role: "treeitem", "aria-expanded": "true" },
      el("div", { class: "node" }, caret(true, null, true), el("img", { src: "/static/ovc-icon.png", alt: "" }), el("span", { class: "label", text: TOOLBOX.name })));
    const sets = el("ul", { role: "group" });
    TOOLBOX.toolsets.forEach((set) => {
      const tools = set.tools.filter((t) => !filter || t.name.toLowerCase().includes(filter) || t.summary.toLowerCase().includes(filter));
      if (!tools.length) return;
      const li = el("li", { role: "treeitem", "aria-expanded": "true" },
        el("div", { class: "node" }, caret(true, null, true), icon("toolbox", "kind"), el("span", { class: "label", text: set.name })));
      const ul = el("ul", { role: "group" });
      tools.forEach((t) => {
        ul.append(el("li", { role: "treeitem", "data-tool": t.id },
          el("div", { class: "node tool-node", title: t.summary, onclick: () => openTool(t.id) },
            caret(false, null, true), icon("hammer", "kind"), el("span", { class: "label", text: t.name }))));
      });
      li.append(ul);
      sets.append(li);
    });
    box.append(sets);
    tree.append(box);
  }
  $("gp-search").addEventListener("input", renderToolTree);

  function renderRibbonTools() {
    const box = $("ribbon-tools");
    box.replaceChildren();
    allTools().forEach((t) => {
      const b = el("button", { class: "tool big", "data-open-tool": t.id, title: t.summary, onclick: () => openTool(t.id) }, icon("hammer"), el("span", { text: t.name }));
      box.append(b);
    });
  }

  function openToolbox() {
    if (!S.gp.tool) { $("gp-home").hidden = false; $("gp-tool").hidden = true; }
    openPane("geoprocessing");
    renderToolTree();
  }

  function openTool(id, preset) {
    const tool = allTools().find((t) => t.id === id);
    if (!tool) return;
    S.gp.tool = tool;
    const values = {};
    tool.params.forEach((p) => {
      if (p.type === "number") values[p.name] = p.default;
      else if (p.type === "bool") values[p.name] = !!p.default;
      else values[p.name] = "";
    });
    S.gp.values = Object.assign(values, preset || {});
    $("gp-home").hidden = true;
    $("gp-tool").hidden = false;
    $("gp-title").textContent = tool.name;
    $("gp-summary").textContent = tool.summary;
    $("gp-message").hidden = true;
    renderToolForm();
    openPane("geoprocessing");
  }

  function backToToolbox() {
    S.gp.tool = null;
    $("gp-tool").hidden = true;
    $("gp-home").hidden = false;
    renderToolTree();
  }
  $("gp-back").addEventListener("click", backToToolbox);

  function candidateLayers(p) {
    return S.layers.filter((l) => !p.geometry || (p.geometry === "polygon" && l.info.is_polygon && l.info.feature_count > 0));
  }

  function renderToolForm() {
    const tool = S.gp.tool;
    if (!tool) return;
    const v = S.gp.values;
    const form = $("gp-form");
    form.replaceChildren();
    // choose sensible layer defaults
    tool.params.filter((p) => p.type === "layer").forEach((p) => {
      const options = candidateLayers(p).filter((l) => !p.distinctFrom || l.id !== v[p.distinctFrom]);
      if (!options.some((l) => l.id === v[p.name])) {
        const preferActive = options.find((l) => l.id === S.active);
        v[p.name] = (preferActive || options[0] || { id: "" }).id;
      }
    });
    tool.params.forEach((p) => {
      const id = "gp-" + p.name;
      const wrap = el("div", { class: "param", "data-param": p.name });
      if (p.type === "layer") {
        const select = el("select", { id });
        const options = candidateLayers(p).filter((l) => !p.distinctFrom || l.id !== v[p.distinctFrom]);
        if (!options.length) select.append(el("option", { value: "", text: p.geometry === "polygon" ? "Add a polygon layer first" : "Add a layer first" }));
        options.forEach((l) => select.append(el("option", { value: String(l.id), text: l.info.name })));
        select.value = v[p.name] === "" ? "" : String(v[p.name]);
        select.addEventListener("change", () => { v[p.name] = select.value ? parseInt(select.value, 10) : ""; renderToolForm(); });
        wrap.append(el("label", { class: "plabel", for: id }, p.label, p.required ? el("span", { class: "req", text: "*" }) : null), select);
        const chosen = layerById(v[p.name]);
        if (chosen && !chosen.info.has_crs && p.name !== "input") {
          wrap.append(el("div", { class: "pnote", text: "This layer has no CRS, so it cannot be compared. Define its CRS in the file." }));
        }
      } else if (p.type === "crs") {
        const layer = layerById(v[p.of]);
        if (!layer || layer.info.has_crs) return;
        const input = el("input", { id, type: "text", inputmode: "numeric", placeholder: "for example 32636", value: String(v[p.name] || "").replace(/^EPSG:/, "") });
        input.addEventListener("input", () => { v[p.name] = epsg(input.value); validateTool(); });
        input.addEventListener("change", () => { layer.assumeCrs = epsg(input.value); loadLayerData(layer, true); });
        wrap.append(el("label", { class: "plabel", for: id }, p.label, el("span", { class: "req", text: "*" })), input);
      } else if (p.type === "field") {
        const layer = layerById(v[p.of]);
        const select = el("select", { id });
        select.append(el("option", { value: "", text: "FID only" }));
        (layer ? layer.info.fields : []).forEach((f) => select.append(el("option", { value: f, text: f })));
        if (!layer || !layer.info.fields.includes(v[p.name])) v[p.name] = "";
        select.value = v[p.name];
        select.addEventListener("change", () => { v[p.name] = select.value; });
        wrap.append(el("label", { class: "plabel", for: id, text: p.label }), select);
      } else if (p.type === "number") {
        const input = el("input", { id, type: "number", min: p.min, step: p.step, value: String(v[p.name]) });
        input.addEventListener("input", () => { v[p.name] = input.value === "" ? "" : parseFloat(input.value); validateTool(); });
        wrap.append(el("label", { class: "plabel", for: id, text: p.label }), input);
      } else if (p.type === "bool") {
        const input = el("input", { id, type: "checkbox" });
        input.checked = !!v[p.name];
        input.addEventListener("change", () => { v[p.name] = input.checked; });
        wrap.append(el("label", { class: "check-param", for: id }, input, p.label));
      }
      if (p.help) wrap.append(el("small", { text: p.help }));
      form.append(wrap);
    });
    const input = layerById(v.input);
    $("sb-crs").textContent = "Layer CRS: " + (input ? (input.info.has_crs ? input.info.crs : "missing") : "-");
    validateTool();
  }

  function toolProblem() {
    const tool = S.gp.tool;
    if (!tool) return "Choose a tool.";
    const v = S.gp.values;
    for (const p of tool.params) {
      if (p.type === "layer" && p.required && !layerById(v[p.name])) {
        return p.geometry === "polygon" ? `${p.label}: add a polygon layer with Add Data.` : `${p.label}: add a layer.`;
      }
      if (p.type === "layer" && p.name !== "input" && layerById(v[p.name]) && !layerById(v[p.name]).info.has_crs) {
        return `${p.label} has no CRS.`;
      }
      if (p.type === "crs") {
        const layer = layerById(v[p.of]);
        if (layer && !layer.info.has_crs && !v[p.name]) return "Enter the coordinate system of the input.";
      }
      if (p.type === "number" && (v[p.name] === "" || isNaN(v[p.name]) || v[p.name] < (p.min ?? -Infinity))) {
        return `${p.label} must be a number${p.min !== undefined ? ` of at least ${p.min}` : ""}.`;
      }
    }
    return "";
  }

  function validateTool() {
    const problem = toolProblem();
    $("gp-run").disabled = !!problem || S.busy;
    $("gp-hint").textContent = S.busy ? "" : problem;
  }

  // -------------------------------------------------------------------- run
  async function runTool() {
    if ($("gp-run").disabled) return;
    const tool = S.gp.tool;
    const v = S.gp.values;
    const input = layerById(v.input);
    const req = tool.request(v);
    const body = {
      path: input.path,
      layer: input.info.name,
      id_field: req.id_field || "",
      assume_crs: input.info.has_crs ? "" : epsg(req.assume_crs),
      check_overlaps: !!req.check_overlaps,
      check_gaps: !!req.check_gaps,
      coverage: null,
      min_overlap_area_m2: req.min_overlap_area_m2 ?? S.config.defaults.min_area_m2,
      min_gap_area_m2: req.min_gap_area_m2 ?? S.config.defaults.min_area_m2,
      repair_invalid: !!req.repair_invalid,
    };
    if (req.coverage) {
      const cov = layerById(req.coverage);
      body.coverage = { path: cov.path, layer: cov.info.name };
      setCoverageStyle(cov);
      renderContents();
    }
    if (body.assume_crs) input.assumeCrs = body.assume_crs;
    S.busy = true;
    clearResults();
    validateTool();
    $("progress").hidden = false;
    $("gp-message").hidden = true;
    setProgress("Starting", 0);
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
    S.runLayer = input.id;
    S.busy = false;
    $("progress").hidden = true;
    validateTool();
    const msg = $("gp-message");
    msg.className = "gp-message " + S.summary.status;
    msg.replaceChildren(
      el("strong", { text: `${tool.name} ${S.summary.status === "failed" ? "failed" : "completed"}. ` }),
      S.summary.message, " ",
      el("a", { href: "#", id: "gp-view-results", text: "View results", onclick: (e) => { e.preventDefault(); openPane("results"); } }));
    msg.hidden = false;
    renderResults();
  }

  function setProgress(stage, fraction) {
    $("bar-fill").style.width = Math.round((fraction || 0) * 100) + "%";
    $("progress-text").textContent = (stage || "Working") + "…";
  }

  // ---------------------------------------------------------------- results
  function clearResults() {
    S.summary = null; S.findings = []; S.selected = null; S.filter = new Set();
    S.dismissed = new Set(); S.notes = {}; S.runLayer = null;
    $("step-results").hidden = true;
    $("results-empty").hidden = false;
    $("export-done").textContent = "";
    overlays.findings.clearLayers(); overlays.highlight.clearLayers(); overlays.dots.clearLayers();
    renderContents();
    updateTools();
  }

  function renderResults() {
    const s = S.summary;
    $("step-results").hidden = false;
    $("results-empty").hidden = true;
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
    $("export-pane").hidden = failed;
    S.expanded.add("findings");
    refreshFindings();
    openPane("results");
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
    renderFilters(); renderFindings(); drawFindings(); renderContents(); updateTools();
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
      const b = f.bbox; // a dot keeps small findings visible and clickable
      const dot = L.circleMarker([(b[1] + b[3]) / 2, (b[0] + b[2]) / 2], {
        pane: "dot", radius: selected ? 9 : 6, color: "#fff", weight: 2,
        fillColor: COLORS[p.issue_type], fillOpacity: 1,
      });
      dot.on("click", (e) => { L.DomEvent.stop(e); select(p.finding_id); });
      dot.bindTooltip(`${p.label} · ${fmtArea(p.area_m2)}`);
      overlays.dots.addLayer(dot);
    });
  }

  async function select(id, redrawOnly) {
    S.selected = id;
    renderFindings();
    drawFindings();
    overlays.highlight.clearLayers();
    updateTools();
    if (id === null) return;
    const f = S.findings.find((x) => x.properties.finding_id === id);
    if (!redrawOnly) {
      openPane("results");
      const li = document.querySelector(`#findings li[data-id="${id}"]`);
      if (li) li.scrollIntoView({ block: "nearest" });
      if (f.bbox) fitTo(f.bbox);
    }
    const p = f.properties;
    const fids = [p.fid_a, p.fid_b].filter((v) => v !== null && v !== undefined);
    if (p.check === "gap" && p.related_fids) p.related_fids.split(",").forEach((v) => fids.push(parseInt(v, 10)));
    const l = layerById(S.runLayer);
    if (!fids.length || !l) return;
    try {
      const data = await api("/api/features?" + qs({ path: l.path, layer: l.info.name, assume_crs: l.assumeCrs, fids: fids.join(",") }));
      if (S.selected !== id) return;
      const labelled = p.check !== "gap";
      L.geoJSON(data, {
        pane: "highlight", interactive: false,
        style: { color: outlineColor(), weight: 3, fill: false, dashArray: labelled ? null : "2 6" },
        onEachFeature: (feature, layer) => {
          if (labelled) {
            layer.bindTooltip(`FID ${feature.properties.fid}`, { permanent: true, direction: "center", className: "fid-label", pane: "highlight" });
          }
        },
      }).addTo(overlays.highlight);
    } catch (e) { /* highlighting is a convenience; the finding itself is shown */ }
  }

  // -------------------------------------------------------------- selection
  // Map tools are modes: Explore, Select, Measure, Draw and the edit tools.
  // Add-on scripts register what happens when their mode starts and ends.
  const toolHooks = {};
  const MODE_EDITS = ["edit-move", "edit-rotate", "edit-reshape", "edit-split"];
  const isMode = (cmd) => cmd === "pan" || cmd === "select" || /^(measure-|draw-)/.test(cmd) || MODE_EDITS.includes(cmd);

  function setTool(tool) {
    const prev = S.tool;
    if (prev === tool) return;
    if (toolHooks[prev] && toolHooks[prev].off) toolHooks[prev].off();
    S.tool = tool;
    document.querySelectorAll(".tool.toggle[data-cmd]").forEach((b) => {
      if (isMode(b.dataset.cmd)) b.setAttribute("aria-pressed", String(b.dataset.cmd === tool));
    });
    $("map").classList.toggle("tool-select", tool !== "pan");
    if (tool === "pan") { map.dragging.enable(); map.doubleClickZoom.enable(); }
    else { map.dragging.disable(); map.doubleClickZoom.disable(); }
    message(tool === "select" ? "Select: click a feature or drag a box. Shift adds to the selection, Ctrl removes." : "");
    if (toolHooks[tool] && toolHooks[tool].on) toolHooks[tool].on();
  }

  // The selection belongs to one layer: the layer chosen in Contents, or else
  // the top visible layer.
  S.sel = { layer: null, fids: [], features: {}, rows: {} };

  function selectableLayer() {
    const active = layerById(S.active);
    if (active && active.visible) return active;
    return S.layers.find((l) => l.visible && !l.error) || null;
  }

  async function selectFeatures(l, query, mode = "replace") {
    let res;
    try {
      res = await api("/api/select", { body: Object.assign({ path: l.path, layer: l.info.name, assume_crs: l.assumeCrs }, query) });
    } catch (e) { message(e.message); return; }
    if (S.sel.layer !== l.id || mode === "replace") S.sel = { layer: l.id, fids: [], features: {}, rows: {} };
    const sel = S.sel;
    const features = {};
    res.features.forEach((f) => { features[f.properties.fid] = f; });
    const rows = {};
    res.rows.forEach((r) => { rows[r.fid] = r; });
    if (mode === "remove") {
      sel.fids = sel.fids.filter((f) => !res.fids.includes(f));
    } else {
      res.fids.forEach((f) => { if (!sel.fids.includes(f)) sel.fids.push(f); });
      Object.assign(sel.features, features);
      Object.assign(sel.rows, rows);
    }
    drawSelection();
    renderAttributes();
    updateTools();
    if (S.onSelectionChange) S.onSelectionChange();
    const n = sel.fids.length;
    message(n ? `${n} feature${n === 1 ? "" : "s"} selected in ${l.info.name}.` : "Nothing selected.");
  }

  async function refreshSelection() {
    // Shapes and attributes again after an edit (the FIDs may have changed).
    const l = layerById(S.sel.layer);
    if (!l || !S.sel.fids.length) { drawSelection(); renderAttributes(); return; }
    await selectFeatures(l, { fids: S.sel.fids }, "replace");
  }

  function drawSelection() {
    overlays.selection.clearLayers();
    const feats = S.sel.fids.map((f) => S.sel.features[f]).filter(Boolean);
    if (!feats.length) return;
    L.geoJSON({ type: "FeatureCollection", features: feats }, {
      pane: "selection", interactive: false,
      style: { color: SELECT_COLOR, weight: 2.5, fillColor: SELECT_COLOR, fillOpacity: 0.16 },
      pointToLayer: (f, ll) => L.circleMarker(ll, { pane: "selection", radius: 7, interactive: false }),
    }).addTo(overlays.selection);
  }

  function selectionBounds() {
    const layers = overlays.selection.getLayers();
    if (!layers.length) return null;
    const b = layers[0].getBounds();
    return b.isValid() ? b : null;
  }

  function renderAttributes() {
    const l = layerById(S.sel.layer);
    const fids = S.sel.fids;
    const table = $("feature-table");
    table.replaceChildren();
    $("feature-empty").hidden = fids.length > 0;
    if (!fids.length || !l) { $("feature-title").textContent = ""; return; }
    if (fids.length === 1) {
      const row = S.sel.rows[fids[0]] || { fid: fids[0] };
      $("feature-title").textContent = `${l.info.name}, FID ${fids[0]}`;
      const entries = Object.entries(row).filter(([k]) => k !== "fid");
      entries.forEach(([k, v]) => table.append(el("tr", {}, el("th", { text: k }), el("td", { text: v === null ? "<Null>" : String(v) }))));
      if (!entries.length) table.append(el("tr", {}, el("td", { text: "This layer has no attributes." })));
      $("pane-attributes").dataset.fid = fids[0];
      return;
    }
    $("feature-title").textContent = `${l.info.name}: ${fids.length} features selected`;
    const fields = ["fid", ...l.info.fields].slice(0, 12);
    table.append(el("tr", {}, ...fields.map((f) => el("th", { text: f === "fid" ? "FID" : f }))));
    fids.slice(0, 500).forEach((fid) => {
      const row = S.sel.rows[fid] || { fid };
      const tr = el("tr", { class: "pick-row", title: "Zoom to this feature", onclick: () => {
        const f = S.sel.features[fid];
        if (f) map.fitBounds(L.geoJSON(f).getBounds(), { padding: [60, 60], maxZoom: 22 });
      } }, ...fields.map((f) => el("td", { text: row[f] === null || row[f] === undefined ? "" : String(row[f]) })));
      table.append(tr);
    });
    delete $("pane-attributes").dataset.fid;
  }

  function clearFeature() {
    S.sel = { layer: null, fids: [], features: {}, rows: {} };
    overlays.selection.clearLayers();
    renderAttributes();
    updateTools();
    if (S.onSelectionChange) S.onSelectionChange();
  }

  // Click a feature, or drag a box. Shift adds, Ctrl removes.
  (function wireBoxSelect() {
    let start = null, box = null, mode = "replace";
    const container = map.getContainer();
    container.addEventListener("mousedown", (e) => {
      if (S.tool !== "select" || e.button !== 0) return;
      if (e.target.closest(".leaflet-control")) return;
      start = map.mouseEventToLatLng(e);
      mode = e.shiftKey ? "add" : e.ctrlKey ? "remove" : "replace";
      box = null;
    });
    container.addEventListener("mousemove", (e) => {
      if (!start) return;
      const here = map.mouseEventToLatLng(e);
      if (!box) box = L.rectangle([start, here], { pane: "selection", color: SELECT_COLOR, weight: 1.5, dashArray: "5 4", fillOpacity: 0.06, interactive: false }).addTo(map);
      else box.setBounds([start, here]);
    });
    document.addEventListener("mouseup", (e) => {
      if (!start) return;
      const l = selectableLayer();
      const end = map.mouseEventToLatLng(e);
      let bounds;
      const a = map.latLngToContainerPoint(start), b = map.latLngToContainerPoint(end);
      if (Math.abs(a.x - b.x) < 4 && Math.abs(a.y - b.y) < 4) {
        const lo = map.containerPointToLatLng([a.x - 3, a.y + 3]), hi = map.containerPointToLatLng([a.x + 3, a.y - 3]);
        bounds = [lo.lng, lo.lat, hi.lng, hi.lat];
      } else {
        bounds = [Math.min(start.lng, end.lng), Math.min(start.lat, end.lat), Math.max(start.lng, end.lng), Math.max(start.lat, end.lat)];
      }
      if (box) { box.remove(); box = null; }
      start = null;
      if (!l) { message("Add a layer to select from."); return; }
      selectFeatures(l, { bbox: bounds }, mode).then(() => { if (S.sel.fids.length) openPane("attributes"); });
    });
  })();

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
          body: { mode: options.mode, title: options.title, initial_dir: options.dir || "", initial_name: options.name || "", kind: options.kind || "data" },
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
    const firstLoad = S.layers.length === added.length;
    if (added.length) S.active = added[0].id;
    renderContents();
    await Promise.all(added.map((l) => loadLayerData(l, false)));
    if (added.length) {
      if (firstLoad) zoomFull(); else fitTo(unionBounds(added.map((l) => l.bounds)));
      message(`Added ${added.map((l) => l.info.name).join(", ")}.`);
    }
    renderToolForm();
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
          info.name, el("small", { style: "display:inline", text: `${info.geometry_type}, ${info.feature_count.toLocaleString("en")} features` }));
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
    const picked = await pickPath({ mode: "open", title: "Add Data", dir: S.settings.last_dir || "", inPage });
    if (!picked) return;
    saveSettings({ last_dir: dirName(picked.path) });
    await addFile(picked.path);
  }

  // ---------------------------------------------------------------- modals
  function showModal(title, body, actions, onClose, wide) {
    $("modal").querySelector(".dialog-box").classList.toggle("settings-box", !!wide);
    $("modal-title").textContent = title;
    $("modal-body").replaceChildren(...body);
    const bar = $("modal-actions");
    bar.replaceChildren();
    const close = () => { $("modal").hidden = true; };
    actions.forEach((a) => {
      bar.append(el("button", {
        class: a.primary ? "primary" : "", id: a.id || null, text: a.text,
        onclick: () => { if (!a.keepOpen) close(); if (a.onclick) a.onclick(); },
      }));
    });
    $("modal-close").onclick = () => { close(); if (onClose) onClose(); };
    $("modal").hidden = false;
  }

  function showAbout() {
    const a = S.config.app;
    const auto = el("input", { type: "checkbox", id: "update-auto" });
    auto.checked = !S.update || S.update.enabled !== false;
    auto.addEventListener("change", () => api("/api/update/settings", { body: { enabled: auto.checked } }).catch(() => {}));
    const result = el("span", { id: "update-check-result" });
    const checkNow = el("button", {
      id: "update-check-now", text: "Check now",
      onclick: async () => {
        result.textContent = "Checking…";
        const u = await checkForUpdate(true);
        result.textContent = updateText(u);
      },
    });
    showModal("About OVC", [el("div", { class: "about" },
      el("img", { src: "/static/ovc-icon.png", alt: "" }),
      el("h4", { text: `${a.name} - ${a.title}` }),
      el("p", { text: `Version ${S.config.version}` }),
      el("p", { class: "org", text: a.organization }),
      el("p", { text: `Founded by ${a.founder}` }),
      el("p", { class: "fine", text: "Runs on this computer only. Input files are opened read-only. MIT License. Map display by Leaflet (BSD 2-Clause)." }),
      el("div", { class: "updates" },
        el("label", {}, auto, "Check for updates when OVC starts"),
        el("small", { text: "Asks GitHub for the newest OVC release. Nothing about you or your data is sent." }),
        el("div", { class: "row" }, checkNow, result)),
    )], [{ text: "Close", primary: true }]);
  }

  // ------------------------------------------------------------ report bug
  async function reportBug() {
    let info = {};
    try { info = await api("/api/diagnostics"); } catch (e) { info = { version: S.config.version, log: "", report_url: "https://github.com/AmmarYasser455/ovc/issues/new" }; }
    const what = el("textarea", { id: "bug-what", rows: "4", style: "width:100%", placeholder: "What happened, and what did you expect?" });
    const include = el("input", { type: "checkbox", id: "bug-include-log" });
    const logBox = el("textarea", { class: "log", id: "bug-log", readonly: "", hidden: "" });
    logBox.value = (info.log || "").split("\n").slice(-60).join("\n");
    include.addEventListener("change", () => { logBox.hidden = !include.checked; });
    showModal("Report a Bug", [
      el("p", { text: "Opens a new issue on OVC's GitHub page in your browser, with the OVC and Windows versions filled in. Issues are public." }),
      el("label", { class: "field", for: "bug-what" }, "Describe the problem", what),
      el("label", { class: "pick", style: "margin-top:8px" }, include, "Include the last lines of OVC's log"),
      el("small", { text: "Read it first: file paths in the log can contain your user name." }),
      logBox,
      el("small", { text: `OVC ${info.version || ""} · ${info.os || ""} · ${info.install || ""}` }),
    ], [
      { text: "Open log folder", onclick: showLog },
      { text: "Cancel" },
      {
        text: "Open GitHub issue", primary: true, id: "bug-open",
        onclick: () => openExternal(bugReportUrl(info, what.value, include.checked ? logBox.value : "")),
      },
    ]);
  }

  function bugReportUrl(info, what, log) {
    const first = (what.trim().split("\n")[0] || "").slice(0, 70);
    const body = [
      "## Bug Description", "", what.trim() || "(describe what happened)", "",
      "## Steps to Reproduce", "", "1. ", "",
      "## Expected Behavior", "", "",
      "## Environment", "",
      `- **OVC version**: ${info.version || S.config.version} (${info.install || "unknown"})`,
      `- **OS**: ${info.os || navigator.userAgent}`,
      `- **Python**: ${info.python || ""}`,
      "",
    ];
    if (log) body.push("## Log", "", "```", log.slice(-3500), "```", "");
    return `${info.report_url}?${qs({ labels: "bug", title: "[BUG] " + first, body: body.join("\n") })}`;
  }

  async function showLog() {
    try {
      const res = await api("/api/open-log", { body: {} });
      if (res.opened) { message("Opened the folder with OVC's log."); return; }
      const info = await api("/api/diagnostics");
      const box = el("textarea", { class: "log", readonly: "" });
      box.value = info.log || "(the log is empty)";
      showModal("OVC Log", [el("p", { class: "path", text: res.path }), box], [{ text: "Close", primary: true }]);
    } catch (e) { message(e.message); }
  }

  // ---------------------------------------------------------------- updates
  function updateText(u) {
    if (u.error) return u.error;
    if (u.available) return `OVC ${u.latest} is available.`;
    return `You have the latest version (${u.current}).`;
  }

  function showUpdateBar(u) {
    $("update-text").textContent = `OVC ${u.latest} is available. You have ${u.current}.`;
    $("update-notes").href = u.release_url;
    $("update-notes").onclick = (e) => { e.preventDefault(); openExternal(u.release_url); };
    const action = $("update-action");
    action.disabled = false;
    if (u.can_install) {
      action.textContent = "Install update";
      action.onclick = installUpdate;
    } else if (u.kind === "python") {
      action.textContent = "Release page";
      action.onclick = () => openExternal(u.release_url);
    } else {
      action.textContent = "Download installer";
      action.onclick = () => {
        openExternal(u.download_url);
        $("update-text").textContent =
          "Run OVC-Setup.exe when the download finishes. Once OVC is installed, later updates install with one click.";
      };
    }
    $("update-bar").hidden = false;
    map.invalidateSize();
  }

  async function checkForUpdate(force) {
    let u;
    try { u = await api("/api/update" + (force ? "?force=1" : "")); } catch (e) { return { error: e.message }; }
    S.update = u;
    if (u.available) showUpdateBar(u);
    return u;
  }

  async function installUpdate() {
    const action = $("update-action");
    action.disabled = true;
    $("update-later").disabled = true;
    try {
      await api("/api/update/install", { body: {} });
      let job;
      do {
        await new Promise((r) => setTimeout(r, 300));
        job = await api("/api/update/status");
        if (job.state === "downloading") {
          $("update-text").textContent = `Downloading OVC ${S.update.latest}… ${Math.round(job.fraction * 100)}%`;
        }
      } while (job.state === "downloading" || job.state === "launching");
      if (job.state === "error") throw new Error(job.message);
      $("update-text").textContent = `Installing OVC ${S.update.latest}. OVC will close and open again when it is done.`;
    } catch (e) {
      $("update-text").textContent = `The update was not installed: ${e.message}`;
      action.textContent = "Download installer";
      action.disabled = false;
      action.onclick = () => openExternal(S.update.download_url);
      $("update-later").disabled = false;
    }
  }

  $("update-later").addEventListener("click", () => { $("update-bar").hidden = true; map.invalidateSize(); });

  // ----------------------------------------------- in-page file browser
  const dialog = { mode: "open", dir: null, overwrite: false, resolve: null };
  let browseSeq = 0;

  async function openDialog(options) {
    Object.assign(dialog, { overwrite: false, initial: true, kind: "data", onSave: null }, options);
    $("dialog-title").textContent = options.title;
    $("dialog-save").hidden = options.mode !== "save";
    $("dialog-name").value = options.name || "";
    $("dialog-save-btn").textContent = "Save";
    $("dialog-foot").textContent = options.mode === "save"
      ? "Pick the folder, then check the file name."
      : dialog.kind === "project" ? "Shows folders and OVC projects (.ovcproj)."
        : "Shows folders and vector files: " + S.config.extensions.join(", ");
    $("dialog-save").querySelector("small").textContent = options.saveHint ||
      "GeoPackage (.gpkg) keeps the layer's CRS. GeoJSON (.geojson) is written in WGS 84 (EPSG:4326).";
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
      data = await api("/api/browse?" + qs({ dir, kind: dialog.kind }));
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
      list.append(el("li", {}, el("button", {
        class: isDir ? "dir" : "file", disabled: disabled ? "" : null,
        onclick: () => (isDir ? browseTo(entry.path) : closeDialog({ path: entry.path })),
      }, el("span", { class: "kind", text: isDir ? "Folder" : "Layer" }), el("span", { text: entry.name }))));
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
      await (dialog.onSave || exportTo)(path, dialog.overwrite);
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
      mode: "save", title: "Export Findings",
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

  // ------------------------------------------------------- ribbon commands
  function zoomFull() { fitTo(unionBounds(S.layers.filter((l) => l.visible).map((l) => l.bounds))); }

  function zoomSelection() {
    const f = S.findings.find((x) => x.properties.finding_id === S.selected);
    if (f && f.bbox) fitTo(f.bbox);
    else if (selectionBounds()) map.fitBounds(selectionBounds(), { padding: [60, 60], maxZoom: 22 });
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

  // --------------------------------------------------------------- settings
  // Kept by OVC in ~/.ovc/settings.json: the page itself cannot keep them,
  // because OVC listens on a new port each time and browsers store per port.
  let settingsTimer = null;
  const pendingSettings = {};
  function saveSettings(changes) {
    Object.assign(S.settings, changes);
    Object.assign(pendingSettings, changes);
    clearTimeout(settingsTimer);
    settingsTimer = setTimeout(() => {
      const body = Object.assign({}, pendingSettings);
      Object.keys(pendingSettings).forEach((k) => delete pendingSettings[k]);
      api("/api/settings", { body }).catch(() => {});
    }, 400);
  }

  function setTheme(theme, persist = true) {
    S.theme = theme;
    document.documentElement.dataset.theme = theme;
    $("theme-light").setAttribute("aria-pressed", String(theme === "light"));
    $("theme-dark").setAttribute("aria-pressed", String(theme === "dark"));
    if (persist) saveSettings({ theme });
    // Outlines that follow the theme (coverage areas, finding sources) change with it.
    S.layers.filter((l) => l.autoOutline).forEach((l) => { l.color = outlineColor(); applyStyle(l); });
    if (S.layers.length) renderContents();
    if (S.selected !== null) select(S.selected, true);
  }

  // --------------------------------------------------------------- basemaps
  const BASEMAPS = {
    none: { name: "No basemap" },
    osm: { name: "OpenStreetMap", url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png", attribution: "© OpenStreetMap contributors", maxNativeZoom: 19 },
    "carto-light": { name: "Light Gray (CARTO)", url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", attribution: "© OpenStreetMap contributors © CARTO", maxNativeZoom: 20 },
    "carto-dark": { name: "Dark Gray (CARTO)", url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", attribution: "© OpenStreetMap contributors © CARTO", maxNativeZoom: 20 },
    topo: { name: "Topographic (OpenTopoMap)", url: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", attribution: "© OpenStreetMap contributors, SRTM | © OpenTopoMap (CC-BY-SA)", maxNativeZoom: 17 },
    custom: { name: "Custom tiles (Settings)" },
  };
  let basemapLayer = null;

  function setBasemap(id) {
    if (basemapLayer) { basemapLayer.remove(); basemapLayer = null; }
    let def = BASEMAPS[id] || BASEMAPS.none;
    if (id === "custom") {
      const url = (S.settings.custom_basemap_url || "").trim();
      def = url ? { name: "Custom tiles", url, attribution: "Custom tiles", maxNativeZoom: 19 } : BASEMAPS.none;
    }
    S.basemap = def.url ? id : "none";
    if (def.url) {
      basemapLayer = L.tileLayer(def.url, { maxZoom: 24, maxNativeZoom: def.maxNativeZoom, attribution: def.attribution, subdomains: "abc" }).addTo(map);
    }
    $("basemap-label").textContent = S.basemap === "none" ? "Basemap" : BASEMAPS[S.basemap].name.split(" (")[0];
    markDirty();
  }

  function showBasemapMenu() {
    const menu = $("basemap-list");
    menu.replaceChildren();
    Object.entries(BASEMAPS).forEach(([id, def]) => {
      const item = el("li", { role: "menuitemradio", "aria-checked": String(S.basemap === id), "data-basemap": id }, def.name);
      item.addEventListener("click", () => { menu.hidden = true; setBasemap(id); });
      menu.append(item);
    });
    menu.append(el("li", { class: "sep" }));
    menu.append(el("li", { class: "note-item", text: "Basemaps need an internet connection. Set the default in Project > Settings." }));
    const r = $("basemap").getBoundingClientRect();
    menu.hidden = false;
    menu.style.left = r.left + "px";
    menu.style.top = r.bottom + 4 + "px";
  }
  document.addEventListener("mousedown", (e) => { if (!e.target.closest("#basemap-list, #basemap")) $("basemap-list").hidden = true; });

  async function quit() {
    if (S.beforeQuit && !(await S.beforeQuit())) return;
    try { await api("/api/quit", { body: {} }); } catch (e) { /* already stopped */ }
    stopped();
  }

  function stopped() {
    if (IN_WINDOW) window.close();
    document.body.replaceChildren(el("p", { style: "padding:40px;font-size:16px", text: "OVC has stopped. You can close this window." }));
  }

  // --------------------------------------------------------------- commands
  const COMMANDS = {
    "add-data": () => addLayerFlow(false),
    pan: () => setTool("pan"),
    select: () => setTool("select"),
    "zoom-in": () => map.zoomIn(),
    "zoom-out": () => map.zoomOut(),
    "zoom-full": zoomFull,
    "zoom-layer": () => { const l = layerById(S.active); if (l) fitTo(l.bounds); },
    "zoom-selection": zoomSelection,
    clear: clearSelection,
    delete: deleteItem,
    restore: restoreDismissed,
    toolbox: openToolbox,
    run: () => { if (S.gp.tool) runTool(); },
    export: startExport,
    "show-contents": () => { setLeftTab("contents"); setContents(S.left.collapsed || S.leftTab !== "contents"); },
    "show-catalog": () => { setLeftTab("catalog"); setContents(true); },
    "show-results": () => openPane("results"),
    "show-attributes": () => openPane("attributes"),
    "theme-light": () => setTheme("light"),
    "theme-dark": () => setTheme("dark"),
    "basemap-menu": showBasemapMenu,
    "report-bug": reportBug,
    "show-log": showLog,
    "check-updates": async () => {
      const u = await checkForUpdate(true);
      showModal("Check for Updates", [el("p", { id: "update-check-result", text: updateText(u) })], [{ text: "Close", primary: true }]);
    },
    about: showAbout,
    quit,
  };
  function runCommand(name) {
    const fn = COMMANDS[name];
    if (fn) fn();
  }
  document.querySelectorAll("[data-cmd]").forEach((b) => b.addEventListener("click", () => {
    if (b.closest("#backstage") && b.dataset.cmd !== "quit") closeBackstage();
    runCommand(b.dataset.cmd);
  }));

  function showRibbonTab(name) {
    if (name === "project") { openBackstage(); return; }
    document.querySelectorAll(".rtab").forEach((t) => t.setAttribute("aria-selected", String(t.dataset.tab === name)));
    document.querySelectorAll(".rpanel").forEach((p) => { p.hidden = p.id !== "rp-" + name; });
  }
  document.querySelectorAll(".rtab").forEach((tab) => tab.addEventListener("click", () => showRibbonTab(tab.dataset.tab)));

  function openBackstage() {
    $("backstage").hidden = false;
    if (S.renderBackstage) S.renderBackstage();
  }
  function closeBackstage() { $("backstage").hidden = true; }
  $("bs-back").addEventListener("click", closeBackstage);

  // ---- left dock: Contents | Catalog
  S.leftTab = "contents";
  function setLeftTab(name) {
    S.leftTab = name;
    document.querySelectorAll("[data-left]").forEach((t) => t.setAttribute("aria-selected", String(t.dataset.left === name)));
    $("pane-contents").hidden = name !== "contents";
    $("pane-catalog").hidden = name !== "catalog";
    if (name === "catalog" && S.renderCatalog) S.renderCatalog();
  }
  document.querySelectorAll("[data-left]").forEach((t) => t.addEventListener("click", () => setLeftTab(t.dataset.left)));

  function updateTools() {
    const hasResult = !!S.summary && S.summary.status !== "failed";
    document.querySelectorAll('[data-cmd="export"]').forEach((b) => { b.disabled = !hasResult || S.busy; });
    $("restore").disabled = !S.dismissed.size;
    $("delete-item").disabled = S.selected === null;
    $("clear-selection").disabled = S.selected === null && !S.sel.fids.length;
    $("zoom-layer").disabled = !(layerById(S.active) && layerById(S.active).bounds);
    $("zoom-selection").disabled = S.selected === null && !S.sel.fids.length;
    $("zoom-full").disabled = !S.layers.some((l) => l.bounds);
    if (S.onToolsUpdate) S.onToolsUpdate();
  }

  $("gp-run").addEventListener("click", runTool);
  $("add-gdb").addEventListener("click", () => addLayerFlow(true));
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

  // -------------------------------------------------------------- shortcuts
  // Every shortcut can be changed in Project > Settings > Keyboard shortcuts.
  const SHORTCUTS = [
    ["project-new", "New project", "Ctrl+N"],
    ["project-open", "Open project", "Ctrl+Shift+O"],
    ["project-save", "Save project", "Ctrl+S"],
    ["add-data", "Add data", "Ctrl+O"],
    ["export", "Export findings", "Ctrl+E"],
    ["toolbox", "OVC Toolbox", "Ctrl+T"],
    ["run", "Run the open tool", "F5"],
    ["show-contents", "Show or hide Contents", "F2"],
    ["pan", "Explore", "P"],
    ["select", "Select", "S"],
    ["clear", "Clear selection", "Esc"],
    ["zoom-full", "Full extent", "Home"],
    ["zoom-in", "Zoom in", "+"],
    ["zoom-out", "Zoom out", "-"],
    ["measure-distance", "Measure distance", "M"],
    ["measure-area", "Measure area", "Shift+M"],
    ["edit-toggle", "Start or stop editing", "E"],
    ["edit-save", "Save edits", "Ctrl+Shift+S"],
    ["edit-undo", "Undo edit", "Ctrl+Z"],
    ["edit-redo", "Redo edit", "Ctrl+Y"],
    ["edit-delete", "Delete selected features", "Delete"],
    ["edit-move", "Move", "G"],
    ["edit-rotate", "Rotate", "R"],
    ["edit-reshape", "Edit vertices", "V"],
    ["edit-merge", "Merge", "Ctrl+M"],
    ["edit-split", "Split", "Ctrl+K"],
    ["draw-polygon", "Draw polygon", "Shift+P"],
    ["draw-rectangle", "Draw rectangle", "Shift+R"],
    ["report-bug", "Report a bug", ""],
  ];

  function keyName(e) {
    const parts = [];
    if (e.ctrlKey || e.metaKey) parts.push("Ctrl");
    if (e.altKey) parts.push("Alt");
    let key = e.key;
    if (key === "Escape") key = "Esc";
    else if (key === " ") key = "Space";
    else if (key === "=") key = "+";
    else if (key.length === 1) key = key.toUpperCase();
    if (e.shiftKey && !(key.length === 1 && !/[A-Z0-9]/.test(key))) parts.push("Shift");
    if (["Control", "Shift", "Alt", "Meta"].includes(e.key)) return "";
    parts.push(key);
    return parts.join("+");
  }

  function shortcutMap() {
    const custom = S.settings.shortcuts || {};
    const out = {};
    SHORTCUTS.forEach(([cmd, , key]) => {
      const k = cmd in custom ? custom[cmd] : key;
      if (k) out[k] = cmd;
    });
    return out;
  }

  document.addEventListener("keydown", (e) => {
    if (S.capturingShortcut) return;
    if (e.key === "Escape") {
      if (!$("basemap-list").hidden) { $("basemap-list").hidden = true; return; }
      if (!$("ctx").hidden) return hideContextMenu();
      if (!$("dialog").hidden) return closeDialog(null);
      if (!$("modal").hidden) return $("modal-close").click();
      if (!$("backstage").hidden) return closeBackstage();
      if (S.onEscape && S.onEscape()) return;
      return clearSelection();
    }
    if (e.key === "Enter" && S.onEnter && !/^(INPUT|TEXTAREA|SELECT|BUTTON)$/.test(document.activeElement.tagName) && S.onEnter()) { e.preventDefault(); return; }
    if (!$("dialog").hidden || !$("modal").hidden) return;
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
    const name = keyName(e);
    if (!name) return;
    const cmd = shortcutMap()[name];
    if (!cmd) return;
    // While typing, only the function keys and file shortcuts act (Ctrl+Z stays the field's own undo).
    const global = /^F\d+$/.test(name) || /^Ctrl\+(Shift\+)?[SONET]$/.test(name);
    if (typing && !global) return;
    e.preventDefault();
    if (cmd === "edit-delete" && !(S.editing && S.sel.fids.length)) { deleteItem(); return; }
    runCommand(cmd);
  });

  // ---------------------------------------------------------- project state
  function markDirty() {
    if (S.loadingProject) return;
    S.projectDirty = true;
    updateTitle();
  }
  function updateTitle() {
    const name = S.projectPath ? fileName(S.projectPath).replace(/\.ovcproj$/i, "") : "Untitled";
    $("project-name").textContent = name + (S.projectDirty ? " *" : "");
    document.title = `${name}${S.projectDirty ? "*" : ""} - OVC`;
  }

  // The open page tells OVC it is still there. When OVC stops, it says so
  // and the window closes itself.
  function connectEvents() {
    const events = new EventSource("/api/events?" + qs({ t: TOKEN }));
    events.addEventListener("quit", () => { events.close(); stopped(); });
  }

  window.addEventListener("pagehide", () => navigator.sendBeacon("/api/bye?" + qs({ t: TOKEN })));
  window.addEventListener("beforeunload", (e) => {
    if (S.editing && S.editing.dirty) { e.preventDefault(); e.returnValue = ""; }
  });
  setInterval(() => api("/api/ping").catch(() => {}), 20000);

  $("notice-dismiss").addEventListener("click", () => { $("notice-bar").hidden = true; map.invalidateSize(); });
  $("notice-report").addEventListener("click", () => { $("notice-bar").hidden = true; reportBug(); });

  // Shared with files.js, measure.js and edit.js.
  const core = {
    map, overlays, S, $, el, icon, api, qs, epsg, fileName, dirName, message, showModal,
    layerById, createLayer, loadLayerData, removeLayer, moveLayer, applyStyle, applyOrder, renderContents,
    addFile, pickPath, fitTo, unionBounds, zoomFull, openPane, closePane, setTool, toolHooks,
    selectableLayer, selectFeatures, refreshSelection, clearFeature, drawSelection,
    clearResults, renderToolForm, updateTools, saveSettings, setTheme, setBasemap, BASEMAPS,
    SHORTCUTS, keyName, markDirty, updateTitle, setContents, setLeftTab, closeBackstage, openBackstage,
    commands: COMMANDS, runCommand, layoutDocks, outlineColor, SELECT_COLOR, showRibbonTab, addLayerFlow,
  };
  window.OVC = core;
  window.ovcApp = { map, overlays, state: S, openTool }; // for automated UI tests

  // ---------------------------------------------------- drop files to add
  const MAIN_EXT = [".gpkg", ".geojson", ".json", ".fgb", ".gml", ".kml", ".shp"];
  const SHP_PARTS = [".shp", ".shx", ".dbf", ".prj", ".cpg", ".qix", ".sbn", ".sbx"];
  const ext = (name) => (name.match(/\.[^.]+$/) || [""])[0].toLowerCase();
  const stem = (name) => name.replace(/\.[^.]+$/, "").toLowerCase();
  const hasFiles = (e) => e.dataTransfer && [...e.dataTransfer.types].includes("Files");
  let dragDepth = 0;

  document.addEventListener("dragenter", (e) => { if (!hasFiles(e)) return; dragDepth += 1; $("drop-zone").hidden = false; });
  document.addEventListener("dragleave", (e) => { if (!hasFiles(e)) return; dragDepth = Math.max(0, dragDepth - 1); if (!dragDepth) $("drop-zone").hidden = true; });
  document.addEventListener("dragover", (e) => { if (hasFiles(e)) { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; } });
  document.addEventListener("drop", (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    dragDepth = 0;
    $("drop-zone").hidden = true;
    collectDropped(e.dataTransfer).then(addDropped);
  });

  async function collectDropped(dt) {
    // Folders are read too, so a shapefile's folder can be dropped whole.
    const entries = [...dt.items].map((i) => i.webkitGetAsEntry && i.webkitGetAsEntry()).filter(Boolean);
    if (!entries.length) return [...dt.files];
    const files = [];
    const walk = async (entry, depth) => {
      if (entry.isFile) { files.push(await new Promise((res, rej) => entry.file(res, rej))); return; }
      if (!entry.isDirectory || depth > 2) return;
      const reader = entry.createReader();
      let batch;
      do {
        batch = await new Promise((res, rej) => reader.readEntries(res, rej));
        for (const child of batch) await walk(child, depth + 1);
      } while (batch.length);
    };
    for (const entry of entries) await walk(entry, 0);
    return files;
  }

  async function addDropped(files) {
    const mains = files.filter((f) => MAIN_EXT.includes(ext(f.name)));
    if (!mains.length) {
      showModal("Nothing to add", [el("p", { text: "Drop a GeoPackage, GeoJSON, FlatGeobuf, GML or KML file, or all the files of a shapefile (.shp, .shx, .dbf and .prj)." })], [{ text: "Close", primary: true }]);
      return;
    }
    const names = new Set(files.map((f) => f.name.toLowerCase()));
    const incomplete = mains.filter((f) => ext(f.name) === ".shp" && ![".shx", ".dbf"].every((x) => names.has(stem(f.name) + x)));
    if (incomplete.length) {
      showModal("Shapefile parts missing", [el("p", { text: `${incomplete.map((f) => f.name).join(", ")}: drop the .shp together with its .shx, .dbf and .prj files, or drop the folder that holds them.` })], [{ text: "Close", primary: true }]);
      return;
    }
    const shpStems = new Set(mains.filter((f) => ext(f.name) === ".shp").map((f) => stem(f.name)));
    const upload = files.filter((f) => mains.includes(f) || (shpStems.has(stem(f.name)) && SHP_PARTS.includes(ext(f.name))));
    const drop = Math.random().toString(36).slice(2) + Date.now().toString(36);
    const saved = {};
    let done = 0;
    for (const f of upload) {
      message(`Copying ${f.name} (${done + 1} of ${upload.length})…`);
      try {
        const res = await api("/api/upload?" + qs({ drop, name: f.name }), { raw: f });
        saved[f.name] = res.path;
      } catch (err) {
        showModal("This file could not be added", [el("p", { text: `${f.name}: ${err.message}` })], [{ text: "Close", primary: true }]);
        return;
      }
      done += 1;
    }
    message("");
    for (const f of mains) await addFile(saved[f.name]);
  }

  S.settings = {};
  Promise.all([api("/api/config"), api("/api/settings").catch(() => ({}))]).then(([config, settings]) => {
    S.config = config;
    S.settings = settings || {};
    setTheme(S.settings.theme === "dark" ? "dark" : "light", false);
    const docks = S.settings.docks || {};
    if (docks.left) Object.assign(S.left, docks.left);
    if (docks.right) Object.assign(S.right, docks.right, { collapsed: false });
    layoutDocks();
    S.loadingProject = true;
    setBasemap(S.settings.basemap || "none");
    S.loadingProject = false;
    S.projectDirty = false;
    updateTitle();
    Object.assign(COLORS, config.issue_colors);
    $("splash-version").textContent = "Version " + config.version;
    $("splash-org").textContent = config.app.organization;
    $("splash-founder").textContent = "Founded by " + config.app.founder;
    $("app-org").textContent = config.app.organization;
    if (IN_WINDOW) $("titlebar").hidden = true; // Windows draws the window's own title bar
    if (config.previous_session) {
      const p = config.previous_session;
      $("notice-text").textContent =
        `OVC stopped unexpectedly last time (OVC ${p.version || ""}, started ${p.started || "earlier"}). The log may show why.`;
      $("notice-bar").hidden = false;
    }
    renderContents();
    renderToolTree();
    renderRibbonTools();
    updateTools();
    updateScale();
    connectEvents();
    setTimeout(() => {
      $("splash").classList.add("done");
      document.body.dataset.ready = "1";
      S.ready = true;
      if (IN_WINDOW) api("/api/window-ready", { body: {} }).catch(() => {});
      setTimeout(() => $("splash").remove(), 400);
      checkForUpdate(false);
    }, IN_WINDOW ? 0 : Math.max(0, 1200 - (Date.now() - STARTED)));
  }).catch((e) => {
    document.body.replaceChildren(el("p", { style: "padding:40px;font-size:16px", text: e.message }));
  });
})();
