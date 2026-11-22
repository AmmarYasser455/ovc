/* Measure distance and area. Values are geodesic (WGS 84 ellipsoid),
   computed by OVC, so they do not depend on the map's Web Mercator display. */
(function () {
  "use strict";
  const C = window.OVC;
  const { S, $, map } = C;
  const LINE = { color: "#c2410c", weight: 2.5, dashArray: "6 5", interactive: false };

  const m = { kind: null, points: [], done: false, group: L.layerGroup(), live: null, seq: 0, last: null };

  function fmtLength(v) {
    if (v == null) return "-";
    return v >= 1000 ? `${(v / 1000).toLocaleString("en", { maximumFractionDigits: 3 })} km` : `${v.toLocaleString("en", { maximumFractionDigits: 2 })} m`;
  }
  function fmtArea(v) {
    if (v == null) return "-";
    if (v >= 1e6) return `${(v / 1e6).toLocaleString("en", { maximumFractionDigits: 4 })} km²`;
    if (v >= 1e4) return `${(v / 1e4).toLocaleString("en", { maximumFractionDigits: 4 })} ha`;
    return `${v.toLocaleString("en", { maximumFractionDigits: 2 })} m²`;
  }

  function coords(extra) {
    const pts = m.points.map((p) => [p.lng, p.lat]);
    if (extra) pts.push([extra.lng, extra.lat]);
    return pts;
  }

  async function update(extra) {
    const pts = coords(extra);
    const seq = ++m.seq;
    let r = { length_m: 0, segment_m: 0, area_m2: null, perimeter_m: null };
    if (pts.length >= 2) {
      try { r = await C.api("/api/measure", { body: { coords: pts, kind: m.kind } }); } catch (e) { return; }
    }
    if (seq !== m.seq) return; // a newer position is on its way
    m.last = r;
    if (m.kind === "area") {
      $("measure-value").textContent = pts.length >= 3 ? fmtArea(r.area_m2) : "Area: click 3 or more points";
      $("measure-detail").textContent = pts.length >= 3 ? `Perimeter: ${fmtLength(r.perimeter_m)}` : "";
    } else {
      $("measure-value").textContent = pts.length >= 2 ? fmtLength(r.length_m) : "Distance: click the start point";
      $("measure-detail").textContent = pts.length >= 2 ? `Segment: ${fmtLength(r.segment_m)}` : "";
    }
    $("measure-box").dataset.value = String(m.kind === "area" ? r.area_m2 ?? "" : r.length_m ?? "");
  }

  function draw(extra) {
    m.group.clearLayers();
    const pts = extra ? [...m.points, extra] : m.points;
    if (m.kind === "area" && pts.length >= 3) {
      L.polygon(pts, Object.assign({}, LINE, { fillColor: "#c2410c", fillOpacity: 0.12 })).addTo(m.group);
    } else if (pts.length >= 2) {
      L.polyline(pts, LINE).addTo(m.group);
    }
    m.points.forEach((p) => L.circleMarker(p, { radius: 3.5, color: "#c2410c", weight: 2, fillColor: "#fff", fillOpacity: 1, interactive: false }).addTo(m.group));
  }

  function reset() {
    m.points = [];
    m.done = false;
    m.seq++;
    m.group.clearLayers();
    update();
  }

  function finish() {
    if (m.points.length < (m.kind === "area" ? 3 : 2)) return false;
    m.done = true;
    draw();
    update();
    const where = m.kind === "area" ? L.polygon(m.points).getBounds().getCenter() : m.points[m.points.length - 1];
    const text = () => (m.kind === "area" ? fmtArea(m.last && m.last.area_m2) : fmtLength(m.last && m.last.length_m));
    setTimeout(() => {
      if (!m.done) return;
      L.tooltip({ permanent: true, direction: "top", className: "measure-label", interactive: false })
        .setLatLng(where).setContent(text()).addTo(m.group);
    }, 80);
    return true;
  }

  function onClick(e) {
    if (m.done) reset();
    const p = e.latlng;
    const prev = m.points[m.points.length - 1];
    if (prev && map.latLngToContainerPoint(prev).distanceTo(map.latLngToContainerPoint(p)) < 3) return;
    m.points.push(p);
    draw();
    update();
  }
  function onMove(e) {
    if (m.done || !m.points.length) return;
    draw(e.latlng);
    update(e.latlng);
  }
  function onDbl() { finish(); }

  function on(kind) {
    m.kind = kind;
    m.group.addTo(map);
    $("measure-box").hidden = false;
    reset();
    map.on("click", onClick);
    map.on("mousemove", onMove);
    map.on("dblclick", onDbl);
    C.message(kind === "area"
      ? "Measure area: click the corners, double-click or press Enter to finish."
      : "Measure distance: click along the path, double-click or press Enter to finish.");
  }
  function off() {
    map.off("click", onClick);
    map.off("mousemove", onMove);
    map.off("dblclick", onDbl);
    m.group.clearLayers();
    m.group.remove();
    m.kind = null;
    $("measure-box").hidden = true;
  }

  C.toolHooks["measure-distance"] = { on: () => on("line"), off };
  C.toolHooks["measure-area"] = { on: () => on("area"), off };
  const toggle = (tool) => () => C.setTool(S.tool === tool ? "pan" : tool);
  C.commands["measure-distance"] = toggle("measure-distance");
  C.commands["measure-area"] = toggle("measure-area");

  const prevEscape = S.onEscape;
  S.onEscape = () => {
    if (m.kind) {
      if (m.points.length) reset(); else C.setTool("pan");
      return true;
    }
    return prevEscape ? prevEscape() : false;
  };
  const prevEnter = S.onEnter;
  S.onEnter = () => (m.kind && !m.done ? finish() : prevEnter ? prevEnter() : false);
  C.measure = { fmtLength, fmtArea, state: m };
})();
