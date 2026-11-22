"""Many map requests at once on a large layer must not crash OVC.

Adding several layers, or a layer while a check runs, sends several
requests to OVC at the same time; each is served on its own thread. On
Windows, OVC was ended by a native fault (0x80000003) while reading or
drawing a large layer, always while Python was collecting garbage: the
mark of memory corrupted earlier by GEOS or GDAL being used from several
threads at once on the same geometries.
"""

import json
import threading
import urllib.request
from urllib.parse import urlencode

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import Polygon

from ovc.app.server import AppServer, AppState

NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _ring(cx, cy, r, n):
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return Polygon(np.c_[cx + r * np.cos(a), cy + r * np.sin(a)])


@pytest.fixture(scope="module")
def big_layer(tmp_path_factory):
    # 1,600 polygons of 400 vertices: 640,000 vertices, above the display
    # budget, so the map preview is simplified as for large real layers.
    side = 40
    polys = [
        _ring(500_000 + (i % side) * 120, 3_300_000 + (i // side) * 120, 70, 400)
        for i in range(side * side)
    ]
    gdf = gpd.GeoDataFrame({"ref": range(len(polys))}, geometry=polys, crs=32636)
    path = tmp_path_factory.mktemp("big") / "districts.gpkg"
    gdf.to_file(path, layer="districts")
    return str(path)


def test_parallel_requests_on_a_large_layer(big_layer):
    state = AppState("t")
    server = AppServer(0, state)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    def call(url, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(base + url, data=data)
        req.add_header("X-OVC-Token", "t")
        with NO_PROXY.open(req, timeout=300) as resp:
            return json.loads(resp.read())

    query = urlencode({"path": big_layer, "layer": "districts"})
    west, south, east, north = call("/api/preview?" + query)["bounds"]
    failures = []

    def worker(i):
        rng = np.random.default_rng(i)
        for k in range(10):
            try:
                kind = (i + k) % 3
                if kind == 0:
                    state._layers.clear()  # several threads read the file at once
                    call("/api/preview?" + query)
                elif kind == 1:
                    x, y = rng.uniform(west, east), rng.uniform(south, north)
                    call(
                        "/api/select",
                        {
                            "path": big_layer,
                            "layer": "districts",
                            "bbox": [x, y, x + 0.01, y + 0.01],
                        },
                    )
                else:
                    call("/api/preview?" + query)
            except Exception as exc:  # noqa: BLE001 - collected and reported
                failures.append(repr(exc))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    server.shutdown()
    server.server_close()
    assert failures == []
