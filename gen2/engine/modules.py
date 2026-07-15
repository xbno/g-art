"""The renderer module registry.

Contract: fn(mask, region, ctx, params, rng) -> list[Polyline]
  mask    HxW bool, working px (fast membership tests)
  region  shapely (Multi)Polygon of the same area in page mm (exact clipping)
  ctx     structure_ctx (see photo.py)
  params  plain dict from the genome
  rng     np.random.Generator, already seeded per band

Modules emit CLEAN polylines in page mm. Humanization (wobble, jitter,
overshoot, breaks) is a shared post-pass — never bake it in here.
"""

import cv2
import numpy as np
from opensimplex import OpenSimplex

from .field import trace_streamlines
from .geom import Polyline
from .hatch import fixed_hatch as _parallel_lines


def _p(params: dict, key: str, default):
    return params.get(key, default)


def empty(mask, region, ctx, params, rng) -> list[Polyline]:
    return []


def fixed_hatch(mask, region, ctx, params, rng) -> list[Polyline]:
    return _parallel_lines(
        region,
        angle_deg=_p(params, "angle_deg", 52.0),
        spacing_mm=_p(params, "spacing_mm", 1.4),
        rng=rng,
        spacing_jitter=_p(params, "spacing_jitter", 0.12))


def cross_hatch(mask, region, ctx, params, rng) -> list[Polyline]:
    angle = _p(params, "angle_deg", 45.0)
    spacing = _p(params, "spacing_mm", 0.8)
    lines = _parallel_lines(region, angle, spacing, rng,
                            _p(params, "spacing_jitter", 0.12))
    lines += _parallel_lines(
        region, angle + _p(params, "cross_delta_deg", 70.0),
        spacing * _p(params, "cross_spacing_scale", 1.1), rng,
        _p(params, "spacing_jitter", 0.12))
    return lines


def flow_hatch(mask, region, ctx, params, rng) -> list[Polyline]:
    return trace_streamlines(
        mask, ctx,
        spacing_mm=_p(params, "spacing_mm", 1.2),
        rng=rng,
        step_mm=_p(params, "step_mm", 0.8),
        max_len_mm=_p(params, "max_len_mm", 500.0),
        fallback_angle_deg=_p(params, "fallback_angle_deg", 50.0),
        min_coherence=_p(params, "min_coherence", 0.05),
        angle_offset_deg=_p(params, "angle_offset_deg", 0.0))


def contour_hatch(mask, region, ctx, params, rng) -> list[Polyline]:
    """Concentric inward offsets of the region boundary — topo feel."""
    spacing = _p(params, "spacing_mm", 1.2)
    jitter = _p(params, "spacing_jitter", 0.15)
    max_rings = _p(params, "max_rings", 400)
    out: list[Polyline] = []
    depth = spacing * 0.6
    for _ in range(max_rings):
        inner = region.buffer(-depth)
        if inner.is_empty:
            break
        boundary = inner.boundary
        geoms = getattr(boundary, "geoms", [boundary])
        for g in geoms:
            pts = np.asarray(g.coords, dtype=np.float64)
            if len(pts) >= 3:
                out.append(pts)
        depth += spacing * (1.0 + rng.uniform(-jitter, jitter))
    return out


def scribble_fill(mask, region, ctx, params, rng) -> list[Polyline]:
    """Meandering strokes until the region hits a target line density."""
    page = ctx["page"]
    spacing = _p(params, "spacing_mm", 1.5)     # avg line separation
    step = _p(params, "step_mm", 1.3)
    curl = _p(params, "curl", 0.5)              # heading noise strength
    stroke_len = _p(params, "stroke_len_mm", 220.0)
    noise = OpenSimplex(int(rng.integers(2**31)))
    nf = _p(params, "curl_scale", 0.06)         # noise field scale, 1/mm

    h, w = mask.shape
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return []
    area_mm2 = len(xs) * page.mm_per_px ** 2
    target = area_mm2 / spacing

    def inside(p) -> bool:
        x, y = page.mm_to_px(np.asarray(p)[None, :])[0]
        xi, yi = int(x), int(y)
        return 0 <= xi < w and 0 <= yi < h and bool(mask[yi, xi])

    out: list[Polyline] = []
    drawn = 0.0
    fails = 0
    while drawn < target and fails < 200:
        i = rng.integers(len(xs))
        p = page.px_to_mm(np.array([[xs[i] + 0.5, ys[i] + 0.5]], float))[0]
        heading = rng.uniform(0, 2 * np.pi)
        pts = [p.copy()]
        acc = 0.0
        bounces = 0
        while acc < stroke_len and drawn + acc < target and bounces < 30:
            heading += (curl * noise.noise2(p[0] * nf, p[1] * nf)
                        + rng.normal(0, 0.12))
            q = p + step * np.array([np.cos(heading), np.sin(heading)])
            if not inside(q):
                heading += rng.uniform(2.2, 4.0)
                bounces += 1
                continue
            pts.append(q)
            acc += step
            p = q
        if len(pts) > 4:
            out.append(np.array(pts))
            drawn += acc
            fails = 0
        else:
            fails += 1
    return out


def solid_fill(mask, region, ctx, params, rng) -> list[Polyline]:
    """Dense back-and-forth that reads as solid ink. Ends sit within
    linemerge tolerance so vpype serpentines them into few pen-lifts."""
    return _parallel_lines(
        region,
        angle_deg=_p(params, "angle_deg", 48.0),
        spacing_mm=_p(params, "spacing_mm", 0.42),
        rng=rng,
        spacing_jitter=_p(params, "spacing_jitter", 0.08))


def contour_lines(mask, region, ctx, params, rng) -> list[Polyline]:
    """Outline layer traced from the edge map. `mask` selects where edges
    are kept (pass the full-page mask for a global outline layer)."""
    page = ctx["page"]
    em = (ctx["edge_map"] & mask).astype(np.uint8)
    contours, _ = cv2.findContours(em, cv2.RETR_LIST,
                                   cv2.CHAIN_APPROX_TC89_L1)
    min_len = _p(params, "min_len_mm", 3.0)
    out: list[Polyline] = []
    for c in contours:
        pts = page.px_to_mm(c[:, 0, :].astype(np.float64))
        if len(pts) < 2:
            continue
        seg = np.diff(pts, axis=0)
        if float(np.hypot(seg[:, 0], seg[:, 1]).sum()) >= min_len:
            out.append(pts)
    return out


MODULES = {
    "empty": empty,
    "fixed_hatch": fixed_hatch,
    "cross_hatch": cross_hatch,
    "flow_hatch": flow_hatch,
    "contour_hatch": contour_hatch,
    "scribble_fill": scribble_fill,
    "solid_fill": solid_fill,
    "contour_lines": contour_lines,
}
