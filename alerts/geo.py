"""Region adjacency and centroids from the geoBoundaries GeoJSON (not from anyone's memory)."""
import json

import numpy as np
from shapely import make_valid
from shapely.geometry import shape

import config
from alerts.data import fetch


def region_geo(buffer_deg=0.02):
    path = fetch(config.GEOJSON_URL, config.DATA_RAW / "ukr_adm1.geojson")
    shapes = {}
    for f in json.loads(path.read_text())["features"]:
        name = config.GEO_NAMES.get(f["properties"]["shapeName"])
        if name:
            shapes[name] = make_valid(shape(f["geometry"]))
    missing = set(config.REGIONS) - set(shapes)
    assert not missing, f"no geometry for {missing}"

    R = config.REGIONS
    # A small buffer closes slivers between simplified borders.
    grown = {r: shapes[r].buffer(buffer_deg) for r in R}
    adj = np.array([[i != j and grown[a].intersects(shapes[b]) for j, b in enumerate(R)]
                    for i, a in enumerate(R)], dtype=float)
    adj = np.maximum(adj, adj.T)
    pts = [shapes[r].representative_point() for r in R]
    lat = np.array([p.y for p in pts])
    lon = np.array([p.x for p in pts])

    config.RESULTS.mkdir(parents=True, exist_ok=True)
    neighbours = {a: [b for j, b in enumerate(R) if adj[i, j]] for i, a in enumerate(R)}
    (config.RESULTS / "adjacency.json").write_text(json.dumps(neighbours, indent=1, ensure_ascii=False))
    return adj, lat, lon
