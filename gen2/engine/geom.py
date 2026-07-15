"""Polyline helpers. A Polyline is an (N,2) float64 ndarray in page mm."""

import numpy as np
import shapely
from shapely.geometry import LineString, MultiLineString, GeometryCollection

Polyline = np.ndarray  # (N, 2) mm


def resample(line: Polyline, step_mm: float) -> Polyline:
    """Resample to roughly uniform spacing so humanization has vertices
    to displace. Keeps original endpoints exactly."""
    seg = np.diff(line, axis=0)
    seglen = np.hypot(seg[:, 0], seg[:, 1])
    total = float(seglen.sum())
    if total < 1e-9:
        return line
    n = max(int(np.ceil(total / step_mm)), 1)
    t = np.concatenate([[0.0], np.cumsum(seglen)]) / total
    ts = np.linspace(0.0, 1.0, n + 1)
    x = np.interp(ts, t, line[:, 0])
    y = np.interp(ts, t, line[:, 1])
    return np.column_stack([x, y])


def length(line: Polyline) -> float:
    seg = np.diff(line, axis=0)
    return float(np.hypot(seg[:, 0], seg[:, 1]).sum())


def _geoms_to_polylines(geom) -> list[Polyline]:
    if geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [np.asarray(geom.coords, dtype=np.float64)]
    if isinstance(geom, (MultiLineString, GeometryCollection)):
        out = []
        for g in geom.geoms:
            out.extend(_geoms_to_polylines(g))
        return out
    return []  # points etc.


def clip_lines(lines: list[Polyline], region,
               min_len_mm: float = 0.6) -> list[Polyline]:
    """Intersect polylines with a shapely (Multi)Polygon in mm space."""
    shapely.prepare(region)
    out: list[Polyline] = []
    for ln in lines:
        if len(ln) < 2:
            continue
        ls = LineString(ln)
        if not region.intersects(ls):
            continue
        for piece in _geoms_to_polylines(region.intersection(ls)):
            if len(piece) >= 2 and length(piece) >= min_len_mm:
                out.append(piece)
    return out
