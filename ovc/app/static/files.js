/* OVC projects, the Project backstage, the Catalog pane and Settings.
   Uses the core that app.js shares as window.OVC. */
(function () {
  "use strict";
  const C = window.OVC;
  const { S, $, el, api, map } = C;

  // --------------------------------------------------------------- projects
  function collect() {
    const c = map.getCenter();
    return {
      name: S.projectPath ? C.fileName(S.projectPath).replace(/\.ovcproj$/i, "") : "Untitled",
      view: { center: [c.lat, c.lng], zoom: map.getZoom() },
      basemap: S.basemap,
      layers: S.layers.map((l) => ({
        path: l.path, layer: l.info.name, visible: l.visible,
        color: l.color, width: l.width, fill: l.fill, opacity: l.opacity, dash: l.dash,
        auto_outline: !!l.autoOutline, assume_crs: l.assumeCrs || "",
      })),
    };
  }

  // Ask before the current map is replaced or OVC closes. Resolves true to go on.
  async function confirmClose(what) {
    if (S.stopEditingFirst && !(await S.stopEditingFirst())) return false;
    if (!S.projectDirty || !S.layers.length) return true;
    const name = S.projectPath ? C.fileName(S.projectPath) : "this project";
    return new Promise((resolve) => {
      C.showModal("Save the project?", [el("p", { text: `Save the changes to ${name} before ${what}?` })], [
        { text: "Cancel", onclick: () => resolve(false) },
        { text: "Don't save", onclick: () => resolve(true) },
        { text: "Save", primary: true, id: "modal-ok", onclick: async () => resolve(await saveProject(false)) },
      ], () => resolve(false));
    });
  }
  S.beforeQuit = () => confirmClose("closing OVC");

  function clearMap() {
    [...S.layers].forEach((l) => C.removeLayer(l.id));
    C.clearResults();
    C.clearFeature();
    map.setView([20, 10], 2);
    $("map-note").hidden = true;
    C.message("");
  }

  async function newProject() {
    if (!(await confirmClose("starting a new project"))) return;
    S.loadingProject = true;
    clearMap();
    C.setBasemap(S.settings.basemap || "none");
    S.loadingProject = false;
    S.projectPath = null;
    S.projectDirty = false;
    C.updateTitle();
    C.message("New project.");
  }

  async function writeProject(path, overwrite) {
    const res = await api("/api/project/save", { body: { path, overwrite, project: collect() } });
    S.projectPath = res.path;
    S.projectDirty = false;
    S.settings.recent_projects = res.recent;
    C.saveSettings({ last_dir: C.dirName(res.path) });
    C.updateTitle();
    C.message(`Saved the project to ${res.path}.`);
    return res;
  }

  async function saveProject(saveAs) {
    if (S.projectPath && !saveAs) {
      try { await writeProject(S.projectPath, true); return true; } catch (e) { failed("The project was not saved", e); return false; }
    }
    let saved = false;
    const picked = await C.pickPath({
      mode: "save", kind: "project", title: saveAs ? "Save Project As" : "Save Project",
      dir: S.projectPath ? C.dirName(S.projectPath) : S.settings.last_dir || "",
      name: (S.projectPath ? C.fileName(S.projectPath) : "Untitled.ovcproj"),
      saveHint: "An OVC project (.ovcproj) keeps the layers, symbology and map view. The data stays in its own files.",
      onSave: async (path, overwrite) => { await writeProject(path, overwrite); saved = true; },
    });
    if (picked) {
      try { await writeProject(picked.path, true); saved = true; } catch (e) { failed("The project was not saved", e); }
    }
    return saved;
  }

  async function openProject(path) {
    if (!path) {
      const picked = await C.pickPath({ mode: "open", kind: "project", title: "Open Project", dir: S.settings.last_dir || "" });
      if (!picked) return;
      path = picked.path;
    }
    if (!(await confirmClose("opening another project"))) return;
    let data;
    try {
      data = await api("/api/project/open", { body: { path } });
    } catch (e) { failed("The project could not be opened", e); return; }
    S.loadingProject = true;
    clearMap();
    const missing = [...(data.missing || [])];
    const infos = {};
    // Saved top first; each new layer goes on top, so add from the bottom.
    for (const saved of [...(data.layers || [])].reverse()) {
      if (missing.includes(saved.path)) continue;
      try {
        if (!infos[saved.path]) infos[saved.path] = (await api("/api/layers?" + C.qs({ path: saved.path }))).layers;
      } catch (e) { missing.push(saved.path); continue; }
      const info = infos[saved.path].find((i) => i.name === saved.layer) || (infos[saved.path].length === 1 ? infos[saved.path][0] : null);
      if (!info) { missing.push(`${saved.path} (layer ${saved.layer})`); continue; }
      const l = C.createLayer(saved.path, info);
      Object.assign(l, {
        visible: saved.visible !== false, assumeCrs: saved.assume_crs || "", autoOutline: !!saved.auto_outline,
        color: saved.auto_outline ? C.outlineColor() : saved.color || l.color,
        width: saved.width ?? l.width, fill: saved.fill ?? l.fill, opacity: saved.opacity ?? l.opacity, dash: !!saved.dash,
      });
      C.applyStyle(l);
      if (!l.visible) l.group.remove();
    }
    C.setBasemap(data.basemap || "none");
    if (data.view && data.view.center) map.setView(data.view.center, data.view.zoom || 2);
    S.projectPath = data.path;
    S.settings.recent_projects = data.recent;
    C.saveSettings({ last_dir: C.dirName(data.path) });
    C.renderContents();
    await Promise.all(S.layers.map((l) => C.loadLayerData(l, false)));
    if (!(data.view && data.view.center)) C.zoomFull();
    S.loadingProject = false;
    S.projectDirty = false;
    C.updateTitle();
    C.renderToolForm();
    C.updateTools();
    C.message(`Opened ${C.fileName(data.path)}.`);
    document.body.dataset.project = data.path;
    if (missing.length) {
      C.showModal("Some data was not found", [
        el("p", { text: "These layers were left out because their files are missing or have moved:" }),
        el("ul", {}, ...missing.map((m) => el("li", { class: "path", text: m }))),
        el("p", { class: "hint", text: "Add them again with Add Data, then save the project." }),
      ], [{ text: "Close", primary: true }]);
    }
  }

  function failed(title, e) {
    C.showModal(title, [el("p", { text: e.message })], [{ text: "Close", primary: true }]);
  }

  // Keep the project's map view when it is saved; moving the map alone does
  // not count as a change, as in desktop GIS.

  // -------------------------------------------------------------- backstage
  S.renderBackstage = function () {
    const list = $("bs-recent");
    list.replaceChildren();
    const recent = S.settings.recent_projects || [];
    if (!recent.length) {
      list.append(el("li", { class: "empty", text: "Projects you save or open appear here." }));
      return;
    }
    recent.forEach((path) => {
      list.append(el("li", {
        title: path, tabindex: "0",
        onclick: () => { C.closeBackstage(); openProject(path); },
        onkeydown: (e) => { if (e.key === "Enter") { C.closeBackstage(); openProject(path); } },
      }, C.icon("file"), el("span", { class: "rp-text" },
        el("span", { class: "rp-name", text: C.fileName(path).replace(/\.ovcproj$/i, "") }),
        el("span", { class: "rp-path", text: C.dirName(path) }))));
    });
  };

  // ---------------------------------------------------------------- catalog
  const cat = { dir: null, parent: null, loaded: false, selected: null };

  async function catBrowse(dir) {
    let data;
    try {
      data = await api("/api/browse?" + C.qs({ dir }));
    } catch (e) {
      if (dir) return catBrowse("");
      C.message(e.message);
      return;
    }
    cat.dir = data.dir;
    cat.parent = data.parent;
    cat.loaded = true;
    $("cat-dir").value = data.dir;
    $("cat-up").disabled = !data.parent;
    const list = $("cat-list");
    list.replaceChildren();
    data.entries.forEach((entry) => {
      const isDir = entry.type === "dir";
      const li = el("li", {
        role: "treeitem", tabindex: "0", title: entry.path, draggable: isDir ? null : "true",
        "data-path": entry.path,
      }, C.icon(isDir ? "folder" : "layers"), el("span", { class: "cat-name", text: entry.name }),
      el("span", { class: "cat-kind", text: isDir ? "" : (entry.name.match(/\.[^.]+$/) || [""])[0].slice(1).toUpperCase() }));
      const open = () => (isDir ? catBrowse(entry.path) : C.addFile(entry.path));
      li.addEventListener("click", () => {
        list.querySelectorAll(".sel").forEach((n) => n.classList.remove("sel"));
        li.classList.add("sel");
      });
      li.addEventListener("dblclick", open);
      li.addEventListener("keydown", (e) => { if (e.key === "Enter") open(); });
      if (!isDir) li.addEventListener("dragstart", (e) => { e.dataTransfer.setData("text/ovc-path", entry.path); e.dataTransfer.effectAllowed = "copy"; });
      list.append(li);
    });
    if (!data.entries.length) list.append(el("li", { class: "cat-empty", text: "No folders or GIS data here." }));
    C.saveSettings({ last_dir: data.dir });
  }

  S.renderCatalog = function () {
    const places = $("cat-places");
    if (!places.childElementCount) {
      (S.config.places || []).slice(0, 8).forEach((p) => places.append(el("button", { text: p.label, title: p.path, onclick: () => catBrowse(p.path) })));
    }
    if (!cat.loaded) catBrowse(S.settings.last_dir || "");
  };
  $("cat-up").addEventListener("click", () => cat.parent && catBrowse(cat.parent));
  $("cat-dir").addEventListener("keydown", (e) => { if (e.key === "Enter") catBrowse($("cat-dir").value.trim()); });

  // Drag a file from the Catalog onto the map or Contents.
  [document.querySelector(".mapwrap"), $("dock-left")].forEach((target) => {
    target.addEventListener("dragover", (e) => {
      if ([...e.dataTransfer.types].includes("text/ovc-path")) { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; }
    });
    target.addEventListener("drop", (e) => {
      const path = e.dataTransfer.getData("text/ovc-path");
      if (!path) return;
      e.preventDefault();
      e.stopPropagation();
      C.addFile(path);
    });
  });

  // --------------------------------------------------------------- settings
  function settingsPage(name) {
    const page = el("div", { class: "settings-page", id: "settings-page" });
    if (name === "general") {
      const theme = el("select", { id: "set-theme" },
        el("option", { value: "light", text: "Light" }), el("option", { value: "dark", text: "Dark" }));
      theme.value = S.theme;
      theme.addEventListener("change", () => C.setTheme(theme.value));
      const updates = el("input", { type: "checkbox", id: "set-updates" });
      updates.checked = S.settings.check_for_updates !== false;
      updates.addEventListener("change", () => {
        S.settings.check_for_updates = updates.checked;
        api("/api/update/settings", { body: { enabled: updates.checked } }).catch(() => {});
      });
      page.append(
        el("h4", { text: "General" }),
        el("label", { class: "field" }, "Theme", theme),
        el("label", { class: "check" }, updates, "Check for new versions of OVC at start-up"),
        el("small", { text: "The check asks GitHub for the latest release. Nothing about you or your data is sent." }),
      );
    } else if (name === "map") {
      const basemap = el("select", { id: "set-basemap" });
      Object.entries(C.BASEMAPS).forEach(([id, def]) => basemap.append(el("option", { value: id, text: def.name.replace(" (Settings)", "") })));
      basemap.value = S.settings.basemap || "none";
      const url = el("input", { type: "text", id: "set-custom-url", spellcheck: "false", placeholder: "https://tiles.example.com/{z}/{x}/{y}.png" });
      url.value = S.settings.custom_basemap_url || "";
      const urlNote = el("small", { id: "set-url-note" });
      const checkUrl = () => {
        const v = url.value.trim();
        const ok = !v || (/^https?:\/\//i.test(v) && /\{z\}/.test(v) && /\{x\}/.test(v) && /\{-?y\}/.test(v));
        urlNote.textContent = ok ? "An XYZ tile address with {z}, {x} and {y}, such as your organisation's tile server." : "The address needs http(s):// and {z}, {x} and {y}.";
        return ok;
      };
      checkUrl();
      basemap.addEventListener("change", () => C.saveSettings({ basemap: basemap.value }));
      url.addEventListener("input", () => { if (checkUrl()) C.saveSettings({ custom_basemap_url: url.value.trim() }); });
      const useNow = el("button", { text: "Use on this map", onclick: () => C.setBasemap(basemap.value) });
      page.append(
        el("h4", { text: "Map" }),
        el("label", { class: "field" }, "Default basemap for new projects", basemap),
        el("label", { class: "field" }, "Custom tiles address", url, urlNote),
        el("div", {}, useNow),
        el("p", { class: "hint", text: "Basemaps are downloaded from the internet. Checks never depend on them." }),
      );
    } else if (name === "shortcuts") {
      page.append(el("h4", { text: "Keyboard shortcuts" }),
        el("p", { class: "hint", text: "Click a shortcut, then press the new keys. Esc cancels, Backspace removes the shortcut." }));
      const table = el("table", { class: "kbd-table", id: "kbd-table" });
      const custom = Object.assign({}, S.settings.shortcuts || {});
      const current = (cmd, def) => (cmd in custom ? custom[cmd] : def);
      const render = () => {
        table.replaceChildren();
        C.SHORTCUTS.forEach(([cmd, label, def]) => {
          const btn = el("button", { class: "kbd", "data-cmd-key": cmd, text: current(cmd, def) || "None" });
          btn.addEventListener("click", () => capture(btn, cmd, def));
          table.append(el("tr", {}, el("td", { text: label }), el("td", {}, btn)));
        });
      };
      const store = () => {
        const out = {};
        C.SHORTCUTS.forEach(([cmd, , def]) => { if (cmd in custom && custom[cmd] !== def) out[cmd] = custom[cmd]; });
        C.saveSettings({ shortcuts: out });
      };
      const capture = (btn, cmd, def) => {
        S.capturingShortcut = true;
        btn.classList.add("capturing");
        btn.textContent = "Press keys…";
        const onKey = (e) => {
          e.preventDefault();
          e.stopImmediatePropagation();
          if (["Control", "Shift", "Alt", "Meta"].includes(e.key)) return;
          document.removeEventListener("keydown", onKey, true);
          S.capturingShortcut = false;
          if (e.key === "Escape") { render(); return; }
          const key = e.key === "Backspace" ? "" : C.keyName(e);
          if (key) {
            // A key does one thing: take it from any other command.
            C.SHORTCUTS.forEach(([other, , otherDef]) => { if (other !== cmd && current(other, otherDef) === key) custom[other] = ""; });
          }
          custom[cmd] = key;
          store();
          render();
        };
        document.addEventListener("keydown", onKey, true);
      };
      render();
      page.append(table, el("div", { class: "row-end" }, el("button", {
        text: "Restore defaults", onclick: () => { Object.keys(custom).forEach((k) => delete custom[k]); store(); render(); },
      })));
    }
    return page;
  }

  function openSettings(start = "general") {
    const pages = [["general", "General"], ["map", "Map"], ["shortcuts", "Keyboard shortcuts"]];
    const nav = el("div", { class: "settings-nav", role: "tablist" });
    const grid = el("div", { class: "settings-grid" }, nav, settingsPage(start));
    const show = (name) => {
      nav.querySelectorAll("button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.page === name)));
      grid.replaceChild(settingsPage(name), grid.lastChild);
    };
    pages.forEach(([id, label]) => nav.append(el("button", { role: "tab", "data-page": id, text: label, onclick: () => show(id) })));
    nav.querySelectorAll("button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.page === start)));
    C.showModal("Settings", [grid], [{ text: "Close", primary: true }], () => { S.capturingShortcut = false; }, true);
  }

  Object.assign(C.commands, {
    "project-new": newProject,
    "project-open": () => openProject(null),
    "project-save": () => saveProject(false),
    "project-save-as": () => saveProject(true),
    settings: () => openSettings("general"),
    shortcuts: () => openSettings("shortcuts"),
  });
  Object.assign(C, { openProject, saveProject, newProject, openSettings, collectProject: collect });
})();
