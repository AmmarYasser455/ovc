"""Local HTTP server behind the OVC map app.

It listens on 127.0.0.1 only, requires a per-launch token on every API call
and reads the analyst's files read-only. All validation goes through
:func:`ovc.api.check_file`, the same entry point as the CLI and Python API.
"""

from __future__ import annotations

import json
import mimetypes
import os
import string
import tempfile
import uuid
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import Point

from ovc import __version__
from ovc.api import check_file
from ovc.app import diagnostics, native, updates
from ovc.app.branding import APP_NAME, APP_TITLE, FOUNDER, ORGANIZATION
from ovc.engine import DEFAULT_DUPLICATE_RATIO, DEFAULT_MIN_AREA_M2, ISSUE_TYPES
from ovc.engine.model import crs_label
from ovc.sample_data import sample_path
from ovc.io import (
    SUPPORTED_EXTENSIONS,
    ExportError,
    LayerReadError,
    export_findings,
    list_layers,
    read_layer,
)

log = diagnostics.get_logger("server")
BUG_REPORT_URL = "https://github.com/AmmarYasser455/ovc/issues/new"
MAX_MAP_FEATURES = 20_000
DISPLAY_VERTEX_BUDGET = 300_000  # above this, the map draws simplified shapes
UPLOAD_ROOT = Path(tempfile.gettempdir()) / "ovc-dropped"


class RawJSON(str):
    """A response body that is already JSON text."""

    meta: dict = {}  # more than this and only finding-related features are drawn


STATIC = resources.files("ovc.app") / "static"


class ApiError(Exception):
    def __init__(self, message, status=HTTPStatus.BAD_REQUEST, code="error"):
        super().__init__(message)
        self.status = status
        self.code = code


def _jsonable(value):
    if value is None or value is pd.NA:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return None if not np.isfinite(value) else float(value)
    return value


class AppState:
    """Everything the app keeps in memory for one launch."""

    def __init__(self, token: str, idle_timeout: float = 900.0):
        self.token = token
        self.idle_timeout = idle_timeout
        self.lock = threading.Lock()
        self.last_seen = time.time()
        self.shutdown = threading.Event()
        self.window_ready = threading.Event()  # the page loaded in the app window
        self.in_window = False  # shown in OVC's own window (set by the launcher)
        self.previous_session = None  # set when the last run did not stop normally
        self.clients = 0  # pages connected to /api/events (open OVC windows)
        self.clients_changed = time.time()
        self.opened_urls: list = []  # with OVC_NO_OPEN_URL set (tests)
        self.update_info = None  # result of the last update check
        self.update_job = {"state": "idle", "fraction": 0.0, "message": ""}
        self._layers: dict = {}  # (path, layer, mtime, size) -> GeoDataFrame
        self.job = {"id": 0, "state": "idle", "stage": "", "fraction": 0.0}
        self.result = None
        self.request = None  # the scan request behind ``result``

    # ---- layers -----------------------------------------------------
    def read(self, path, layer=None) -> gpd.GeoDataFrame:
        p = Path(path)
        try:
            stat = p.stat()
        except OSError:
            raise LayerReadError(f"File not found: {p}")
        key = (str(p), layer, stat.st_mtime_ns, stat.st_size)
        with self.lock:
            cached = self._layers.get(key)
        if cached is not None:
            return cached
        gdf = read_layer(p, layer)
        with self.lock:
            # keep the cache small: the input, coverage and exclusion layers
            while len(self._layers) >= 4:
                self._layers.pop(next(iter(self._layers)))
            self._layers[key] = gdf
        return gdf

    # ---- scan job ---------------------------------------------------
    def start_scan(self, req: dict) -> int:
        with self.lock:
            if self.job["state"] == "running":
                raise ApiError("A check is already running.", HTTPStatus.CONFLICT)
            job_id = self.job["id"] + 1
            self.job = {
                "id": job_id,
                "state": "running",
                "stage": "Starting",
                "fraction": 0.0,
            }
            self.result = None
            self.request = req
        threading.Thread(
            target=self._run_scan, args=(job_id, req), name="ovc-scan", daemon=True
        ).start()
        return job_id

    def _run_scan(self, job_id: int, req: dict) -> None:
        def progress(stage, fraction):
            with self.lock:
                if self.job["id"] == job_id:
                    self.job["stage"] = stage
                    self.job["fraction"] = round(float(fraction), 3)

        coverage = req.get("coverage") or {}
        exclusions = req.get("exclusions") or {}
        try:
            result = check_file(
                req["path"],
                req.get("layer"),
                coverage_path=coverage.get("path"),
                coverage_layer=coverage.get("layer"),
                exclusions_path=exclusions.get("path"),
                exclusions_layer=exclusions.get("layer"),
                progress=progress,
                reader=self.read,
                check_overlaps=bool(req.get("check_overlaps", True)),
                check_gaps=bool(req.get("check_gaps", False)),
                id_field=req.get("id_field") or None,
                min_overlap_area_m2=float(
                    req.get("min_overlap_area_m2", DEFAULT_MIN_AREA_M2)
                ),
                min_gap_area_m2=float(req.get("min_gap_area_m2", DEFAULT_MIN_AREA_M2)),
                duplicate_ratio=float(
                    req.get("duplicate_ratio", DEFAULT_DUPLICATE_RATIO)
                ),
                repair_invalid=bool(req.get("repair_invalid", False)),
                assume_crs=req.get("assume_crs") or None,
            )
        except Exception as exc:  # never leave the job hanging
            from ovc.engine.model import STATUS_FAILED, ScanResult

            message = f"The check stopped with an error: {type(exc).__name__}: {exc}"
            result = ScanResult(status=STATUS_FAILED, message=message, error=message)
            log.exception("Unexpected error")
        with self.lock:
            if self.job["id"] == job_id:
                self.result = result
                self.job.update(state="done", stage="Done", fraction=1.0)

    # ---- updates ----------------------------------------------------
    def check_update(self, force=False) -> dict:
        with self.lock:
            cached = self.update_info
        if cached is not None and not force:
            return cached
        info = updates.check(force=force)
        with self.lock:
            self.update_info = info
        return info

    def start_update_install(self) -> dict:
        info = self.check_update()
        if not info.get("can_install"):
            raise ApiError("This copy of OVC cannot install updates by itself.")
        with self.lock:
            if self.update_job["state"] in ("downloading", "launching"):
                raise ApiError(
                    "The update is already being installed.", HTTPStatus.CONFLICT
                )
            self.update_job = {"state": "downloading", "fraction": 0.0, "message": ""}
        threading.Thread(
            target=self._install_update, args=(info,), name="ovc-update", daemon=True
        ).start()
        return dict(self.update_job)

    def _install_update(self, info) -> None:
        def progress(fraction):
            with self.lock:
                self.update_job["fraction"] = round(float(fraction), 3)

        try:
            path = updates.download_installer(
                info["installer_url"], info["checksum_url"], progress
            )
            with self.lock:
                self.update_job.update(state="launching", fraction=1.0)
            updates.launch_installer(path)
        except Exception as exc:
            with self.lock:
                self.update_job = {
                    "state": "error",
                    "fraction": 0.0,
                    "message": str(exc),
                }
            return
        with self.lock:
            self.update_job.update(state="launched")
        # Close OVC so the installer can replace its files; it reopens OVC.
        threading.Timer(2.0, self.shutdown.set).start()

    # ---- map data ---------------------------------------------------
    def display_crs(self, gdf, assume_crs=None):
        crs = gdf.crs
        if crs is None and assume_crs:
            try:
                crs = gpd.GeoSeries([], crs=assume_crs).crs
            except Exception as exc:
                raise ApiError(f"The declared CRS is not valid: {exc}")
        if crs is None:
            raise ApiError(
                "This layer has no CRS, so it cannot be placed on the map. "
                "Declare the CRS its coordinates are in.",
                code="no_crs",
            )
        return crs

    def features_geojson(self, path, layer, assume_crs=None, fids=None, limit=None):
        """Features of a layer (any geometry type) as WGS 84 GeoJSON for the map.

        Returns a :class:`RawJSON` (sent as is) whose ``meta`` holds the counts.
        Layers with more than ``DISPLAY_VERTEX_BUDGET`` vertices are simplified
        to screen resolution for drawing only; checks always use the exact
        geometry. JSON is written by GEOS, which is many times faster than
        building Python dictionaries for large layers.
        """
        gdf = self.read(path, layer)
        crs = self.display_crs(gdf, assume_crs)
        total = len(gdf)
        geoms = gdf.geometry
        if fids is not None:
            geoms = geoms[geoms.index.isin(fids)]
        geoms = geoms[geoms.notna() & ~geoms.is_empty]
        # The map is 2D; Z or M values (NaN in some files) would break the JSON.
        series = gpd.GeoSeries(
            shapely.force_2d(np.asarray(geoms.values, dtype=object)),
            index=geoms.index,
            crs=crs,
        ).to_crs(4326)
        arr = np.asarray(series.values, dtype=object)
        index = series.index
        if len(arr):
            keep = ~shapely.is_empty(arr) & np.isfinite(shapely.bounds(arr)).all(axis=1)
            arr, index = arr[keep], index[keep]
        bounds = [float(v) for v in shapely.total_bounds(arr)] if len(arr) else None
        truncated = limit is not None and len(arr) > limit
        simplified = False
        if truncated:
            arr, index = arr[:0], index[:0]
        elif fids is None and len(arr):
            vertices = int(shapely.get_num_coordinates(arr).sum())
            if vertices > DISPLAY_VERTEX_BUDGET:
                span = max(bounds[2] - bounds[0], bounds[3] - bounds[1])
                arr = shapely.simplify(arr, span / 4000, preserve_topology=True)
                simplified = True
        texts = shapely.to_geojson(arr) if len(arr) else []
        body = ",".join(
            '{"type":"Feature","properties":{"fid":%d},"geometry":%s}'
            % (int(fid), text)
            for fid, text in zip(index, texts)
        )
        meta = {
            "total": total,
            "shown": len(texts),
            "truncated": truncated,
            "simplified": simplified,
            "bounds": bounds,
        }
        raw = RawJSON(
            '{"type":"FeatureCollection","features":['
            + body
            + "],"
            + json.dumps(meta)[1:]
        )
        raw.meta = meta
        return raw

    def findings_geojson(self):
        result = self.result
        if result is None or result.findings is None:
            raise ApiError("There are no results yet.")
        features = []
        if len(result.findings):
            f = result.findings_in(4326)
            for row in f.itertuples(index=False):
                geom = row.geometry
                has_geom = geom is not None and not geom.is_empty
                props = {
                    c: _jsonable(getattr(row, c)) for c in f.columns if c != "geometry"
                }
                props["label"] = ISSUE_TYPES.get(
                    props["issue_type"], ("", props["issue_type"])
                )[1]
                features.append(
                    {
                        "type": "Feature",
                        "properties": props,
                        "bbox": [float(v) for v in geom.bounds] if has_geom else None,
                        "geometry": geom.__geo_interface__ if has_geom else None,
                    }
                )
        return {"type": "FeatureCollection", "features": features}

    def identify(self, path, layer, assume_crs, lon, lat, tol_deg, edge_only=False):
        """The feature of a layer at a clicked map position, with attributes.

        ``edge_only`` is for polygon layers drawn without fill: only a click
        near an outline selects them, so features under them stay reachable.
        """
        gdf = self.read(path, layer)
        crs = self.display_crs(gdf, assume_crs)
        click = gpd.GeoSeries(
            [Point(lon, lat), Point(lon + tol_deg, lat)], crs=4326
        ).to_crs(crs)
        point = click.iloc[0]
        tolerance = max(point.distance(click.iloc[1]), 0.0)
        hits = gdf.sindex.query(
            point.buffer(tolerance) if tolerance else point, predicate="intersects"
        )
        if not len(hits):
            return {"feature": None}
        candidates = gdf.iloc[np.sort(hits)]
        if edge_only:
            near = candidates.geometry.boundary.distance(point) <= tolerance
            candidates = candidates[near]
            if candidates.empty:
                return {"feature": None}
        # the smallest feature under the cursor is the one the analyst means
        row = candidates.loc[candidates.geometry.area.idxmin()]
        fid = row.name
        geom = gpd.GeoSeries([row.geometry], crs=crs).to_crs(4326).iloc[0]
        attributes = {}
        for key, value in row.drop(labels=[gdf.geometry.name]).items():
            if len(attributes) >= 60:
                break
            value = _jsonable(value)
            if value is not None and not isinstance(value, (int, float, bool, str)):
                value = str(value)
            attributes[str(key)] = value
        return {
            "feature": {
                "type": "Feature",
                "properties": {"fid": int(fid)},
                "geometry": geom.__geo_interface__,
            },
            "fid": int(fid),
            "geometry_type": row.geometry.geom_type,
            "attributes": attributes,
        }

    def export(self, path, issue_types, overwrite, finding_ids=None, notes=None):
        if self.result is None:
            raise ApiError("Run the checks before exporting.")
        req = self.request or {}
        source = req.get("path", "")
        if req.get("layer"):
            source += f" | layer {req['layer']}"
        try:
            return export_findings(
                self.result,
                path,
                issue_types=issue_types,
                finding_ids=finding_ids,
                notes=notes,
                overwrite=overwrite,
                protect=[
                    req.get("path"),
                    (req.get("coverage") or {}).get("path"),
                    (req.get("exclusions") or {}).get("path"),
                ],
                source=source,
            )
        except ExportError as exc:
            code = "exists" if "already exists" in str(exc) else "error"
            raise ApiError(str(exc), code=code)


# ---- file browser ----------------------------------------------------


def places() -> list[dict]:
    home = Path.home()
    out = []

    def add(label, path):
        if path.is_dir() and str(path) not in [p["path"] for p in out]:
            out.append({"label": label, "path": str(path)})

    add("Home", home)
    for name in ("Desktop", "Documents", "Downloads"):
        add(name, home / name)
        add(name, home / "OneDrive" / name)
    if os.name == "nt":
        for letter in string.ascii_uppercase:
            add(f"{letter}:", Path(f"{letter}:\\"))
    else:
        add("/", Path("/"))
    return out


def is_layer_file(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def browse(directory: str | None) -> dict:
    d = Path(directory) if directory else Path.home()
    if not d.is_dir():
        raise ApiError(f"Folder not found: {d}")
    entries = []
    try:
        children = sorted(d.iterdir(), key=lambda p: p.name.lower())
    except OSError as exc:
        raise ApiError(f"Cannot open {d}: {exc.strerror or exc}")
    for child in children:
        if child.name.startswith((".", "$", "~")):
            continue
        try:
            if is_layer_file(child):  # includes .gdb folders
                entries.append({"name": child.name, "path": str(child), "type": "file"})
            elif child.is_dir():
                entries.append({"name": child.name, "path": str(child), "type": "dir"})
        except OSError:
            continue
    entries.sort(key=lambda e: (e["type"] != "dir", e["name"].lower()))
    parent = str(d.parent) if d.parent != d else None
    return {"dir": str(d), "parent": parent, "entries": entries}


# ---- HTTP ---------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    server_version = "OVC"
    protocol_version = "HTTP/1.1"

    @property
    def state(self) -> AppState:
        return self.server.state  # type: ignore[attr-defined]

    def log_message(
        self, format, *args
    ):  # noqa: A002 - quiet, and safe without a console
        pass

    # -- helpers
    def _send(self, status, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload, status=HTTPStatus.OK):
        text = payload if isinstance(payload, RawJSON) else json.dumps(payload)
        self._send(status, text.encode("utf-8"), "application/json")

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def _authorised(self, query) -> bool:
        token = self.headers.get("X-OVC-Token") or (query.get("t") or [""])[0]
        return token == self.state.token

    def _static(self, rel: str):
        rel = rel.lstrip("/") or "index.html"
        target = STATIC
        for part in rel.split("/"):
            if part in ("", ".", ".."):
                return self._send(HTTPStatus.NOT_FOUND, b"Not found", "text/plain")
            target = target / part
        if not target.is_file():
            return self._send(HTTPStatus.NOT_FOUND, b"Not found", "text/plain")
        ctype = mimetypes.guess_type(rel)[0] or "application/octet-stream"
        if rel.endswith(".js"):
            ctype = "text/javascript"
        if ctype.startswith("text/") or ctype == "image/svg+xml":
            ctype += "; charset=utf-8"
        self._send(HTTPStatus.OK, target.read_bytes(), ctype)

    def _dispatch(self, method: str):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if not self._host_ok():
            return self._send(HTTPStatus.FORBIDDEN, b"Forbidden", "text/plain")
        if not url.path.startswith("/api/"):
            if method != "GET":
                return self._send(HTTPStatus.METHOD_NOT_ALLOWED, b"", "text/plain")
            path = "/index.html" if url.path == "/" else url.path
            return self._static(path.removeprefix("/static"))
        if not self._authorised(query):
            return self._json(
                {"error": "This page is not connected to OVC. Open OVC again."},
                HTTPStatus.FORBIDDEN,
            )
        if url.path == "/api/events" and method == "GET":
            return self._events()
        self.state.last_seen = time.time()
        if url.path == "/api/upload" and method == "POST":
            try:
                return self._json(self._upload(query))
            except ApiError as exc:
                return self._json({"error": str(exc), "code": exc.code}, exc.status)
        body = {}
        if method == "POST":
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                try:
                    body = json.loads(self.rfile.read(length).decode("utf-8"))
                except ValueError:
                    return self._json({"error": "Bad request."}, HTTPStatus.BAD_REQUEST)
        try:
            payload = self._route(method, url.path, query, body)
        except ApiError as exc:
            return self._json({"error": str(exc), "code": exc.code}, exc.status)
        except LayerReadError as exc:
            return self._json(
                {"error": str(exc), "code": "read"}, HTTPStatus.BAD_REQUEST
            )
        except Exception as exc:
            log.exception("Unexpected error")
            return self._json(
                {"error": f"Unexpected error: {type(exc).__name__}: {exc}"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        self._json(payload)

    def _events(self):
        """Server-sent events: one long request per open OVC window.

        The launcher counts these connections to know whether a window is
        still open, whichever browser process shows it. When OVC stops, a
        ``quit`` event tells the page to close its window.
        """
        state = self.state
        self.close_connection = True
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        with state.lock:
            state.clients += 1
            state.clients_changed = time.time()
        try:
            self.wfile.write(b"retry: 2000\n\n")
            self.wfile.flush()
            while not state.shutdown.is_set():
                self.wfile.write(b": alive\n\n")
                self.wfile.flush()
                state.shutdown.wait(2.0)
            self.wfile.write(b"event: quit\ndata: {}\n\n")
            self.wfile.flush()
        except OSError:
            pass  # the window went away
        finally:
            with state.lock:
                state.clients -= 1
                state.clients_changed = time.time()

    def _upload(self, query):
        """Save one file dropped on the window; returns where it was saved.

        A browser never tells the page where a dropped file lives, so the
        file is copied into a temporary folder, one folder per drop so the
        parts of a shapefile stay together. The original is not touched.
        """
        drop = "".join(c for c in (query.get("drop") or [""])[0] if c.isalnum())[:40]
        drop = drop or uuid.uuid4().hex
        name = Path((query.get("name") or [""])[0]).name
        if not drop or not name or name in (".", ".."):
            raise ApiError("Bad upload.")
        folder = UPLOAD_ROOT / drop
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / name
        remaining = int(self.headers.get("Content-Length") or 0)
        with open(target, "wb") as out:
            while remaining > 0:
                chunk = self.rfile.read(min(remaining, 1 << 20))
                if not chunk:
                    break
                out.write(chunk)
                remaining -= len(chunk)
        if remaining:
            raise ApiError(f"The copy of {name} was cut off.")
        return {"path": str(target)}

    def _route(self, method, path, query, body):
        state = self.state

        def q(name, default=None):
            return (query.get(name) or [default])[0]

        if method == "GET":
            if path == "/api/ping":
                return {"ok": True, "app": "ovc", "version": __version__}
            if path == "/api/config":
                return {
                    "version": __version__,
                    "app": {
                        "name": APP_NAME,
                        "title": APP_TITLE,
                        "organization": ORGANIZATION,
                        "founder": FOUNDER,
                    },
                    "native_dialog": native.dialogs_enabled(),
                    "in_window": state.in_window,
                    "previous_session": state.previous_session,
                    "sample": str(sample_path()),
                    "places": places(),
                    "extensions": list(SUPPORTED_EXTENSIONS),
                    "issue_types": {k: v[1] for k, v in ISSUE_TYPES.items()},
                    "issue_colors": {k: v[2] for k, v in ISSUE_TYPES.items()},
                    "defaults": {
                        "min_area_m2": DEFAULT_MIN_AREA_M2,
                        "duplicate_ratio": DEFAULT_DUPLICATE_RATIO,
                    },
                    "max_map_features": MAX_MAP_FEATURES,
                }
            if path == "/api/browse":
                return browse(q("dir"))
            if path == "/api/layers":
                if not q("path"):
                    raise ApiError("No file chosen.")
                return {"layers": [i.to_dict() for i in list_layers(q("path"))]}
            if path == "/api/preview":
                return state.features_geojson(
                    q("path"), q("layer"), q("assume_crs"), limit=MAX_MAP_FEATURES
                )
            if path == "/api/features":
                fids = [int(v) for v in (q("fids") or "").split(",") if v.strip()]
                return state.features_geojson(
                    q("path"), q("layer"), q("assume_crs"), fids=fids
                )
            if path == "/api/identify":
                return state.identify(
                    q("path"),
                    q("layer"),
                    q("assume_crs"),
                    float(q("lon")),
                    float(q("lat")),
                    float(q("tol") or 0),
                    edge_only=q("edge") == "1",
                )
            if path == "/api/diagnostics":
                info = diagnostics.environment()
                info["log_path"] = str(diagnostics.log_path())
                info["log"] = diagnostics.tail()
                info["report_url"] = BUG_REPORT_URL
                return info
            if path == "/api/update":
                return state.check_update(force=q("force") == "1")
            if path == "/api/update/status":
                with state.lock:
                    return dict(state.update_job)
            if path == "/api/job":
                with state.lock:
                    job = dict(state.job)
                    result = state.result
                if job["state"] == "done" and result is not None:
                    job["summary"] = result.summary()
                    job["export_default"] = _default_export_path(state.request)
                return job
            if path == "/api/findings":
                return state.findings_geojson()
        if method == "POST":
            if path == "/api/scan":
                if not body.get("path"):
                    raise ApiError("Choose a layer first.")
                return {"job_id": state.start_scan(body)}
            if path == "/api/export":
                if not body.get("path"):
                    raise ApiError("Choose where to save the findings.")
                return state.export(
                    body["path"],
                    body.get("issue_types"),
                    bool(body.get("overwrite")),
                    finding_ids=body.get("finding_ids"),
                    notes=body.get("notes"),
                )
            if path == "/api/pick":
                return native.pick_path(
                    "save" if body.get("mode") == "save" else "open",
                    str(body.get("title") or ""),
                    str(body.get("initial_dir") or ""),
                    str(body.get("initial_name") or ""),
                )
            if path == "/api/open-url":
                target = str(body.get("url") or "")
                if not target.startswith("https://github.com/AmmarYasser455/ovc"):
                    raise ApiError("Only OVC's GitHub pages can be opened from here.")
                if os.environ.get("OVC_NO_OPEN_URL"):
                    state.opened_urls.append(target)
                else:
                    import webbrowser

                    webbrowser.open(target)  # the analyst's own browser, signed in
                return {"opened": True}
            if path == "/api/open-log":
                folder = diagnostics.log_dir()
                folder.mkdir(parents=True, exist_ok=True)
                opened = False
                if os.name == "nt" and not os.environ.get("OVC_NO_OPEN_URL"):
                    os.startfile(folder)  # noqa: S606 - Windows Explorer
                    opened = True
                return {"opened": opened, "path": str(diagnostics.log_path())}
            if path == "/api/update/install":
                return state.start_update_install()
            if path == "/api/update/settings":
                updates.set_checks_enabled(bool(body.get("enabled")))
                with state.lock:
                    state.update_info = None
                return {"enabled": updates.checks_enabled()}
            if path == "/api/window-ready":
                state.window_ready.set()
                return {"ok": True}
            if path == "/api/bye":
                # The page is closing: stop soon unless another page checks in.
                state.last_seen = time.time() - state.idle_timeout + 8
                return {"ok": True}
            if path == "/api/quit":
                state.shutdown.set()
                return {"ok": True}
        raise ApiError("Not found.", HTTPStatus.NOT_FOUND)

    def do_GET(self):  # noqa: N802
        self._dispatch("GET")

    def do_POST(self):  # noqa: N802
        self._dispatch("POST")


def _default_export_path(req) -> str:
    if not req or not req.get("path"):
        return ""
    src = Path(req["path"])
    folder = src.parent
    if UPLOAD_ROOT in src.parents:  # a dropped copy: save next to the user's documents
        docs = Path.home() / "Documents"
        folder = docs if docs.is_dir() else Path.home()
    stem = src.stem + (f"_{req['layer']}" if req.get("layer") else "")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in stem)
    return str(folder / f"{safe}_ovc_findings.gpkg")


class AppServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, port: int, state: AppState):
        super().__init__(("127.0.0.1", port), Handler)
        self.state = state

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}/?t={self.state.token}"


def serve(server: AppServer) -> None:
    """Serve until Quit is pressed or the app has been idle too long."""
    state = server.state
    thread = threading.Thread(target=server.serve_forever, name="ovc-http", daemon=True)
    thread.start()
    try:
        while not state.shutdown.wait(1.0):
            with state.lock:
                running = state.job["state"] == "running"
            if not running and time.time() - state.last_seen > state.idle_timeout:
                log.info("Stopping: no OVC page for %.0f s", state.idle_timeout)
                break
    except KeyboardInterrupt:
        pass
    finally:
        state.shutdown.set()  # pages get a "quit" event and close
        time.sleep(0.6)
        server.shutdown()
        server.server_close()
