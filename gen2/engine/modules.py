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
from .hatch import fan_hatch as _fan_lines
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


def fan_hatch(mask, region, ctx, params, rng) -> list[Polyline]:
    """Strokes radiating from a pivot — near-parallel lines that subtly
    converge toward a vanishing point (summit, sun, horizon). Pivot is in
    PAGE fractions and may sit far outside the page: [0.45, -1.2] is high
    above it. Pair with tone_mod for shaded slope fans."""
    page = ctx["page"]
    fx, fy = _p(params, "pivot", [0.5, -1.5])
    pivot = (float(fx) * page.width_mm, float(fy) * page.height_mm)
    return _fan_lines(
        region, pivot,
        spacing_mm=_p(params, "spacing_mm", 1.0),
        rng=rng,
        spacing_jitter=_p(params, "spacing_jitter", 0.12))


def shingle_hatch(mask, region, ctx, params, rng) -> list[Polyline]:
    """Overlapping swatches of straight parallel strokes, each at its own
    angle — the interlocking canopy/rock texture of classic pen-and-ink
    (and gen1's hatch_hatch shape-stack). Swatches are z-ordered and
    OCCLUDE one another, so boundaries read as angle changes: no outlines,
    no white seams, no plaid."""
    from shapely import affinity
    from shapely.geometry import Polygon as ShapelyPolygon

    swatch = _p(params, "swatch_mm", 12.0)       # mean swatch size
    aspect = _p(params, "aspect", 0.65)
    overlap = _p(params, "overlap", 0.5)         # 0 = tiled, ->1 = piled
    spacing = _p(params, "spacing_mm", 0.9)
    sjit = _p(params, "spacing_jitter", 0.1)
    angles = _p(params, "angles", [10, 40, 70, 100, 130, 160])
    max_swatches = _p(params, "max_swatches", 600)

    minx, miny, maxx, maxy = region.bounds
    step = max(swatch * (1.0 - overlap), 1.0)
    seeds = []
    y = miny
    while y <= maxy:
        x = minx
        while x <= maxx:
            seeds.append((x + rng.uniform(-step, step) * 0.4,
                          y + rng.uniform(-step, step) * 0.4))
            x += step
        y += step
    rng.shuffle(seeds)
    seeds = seeds[:max_swatches]

    out: list[Polyline] = []
    covered = None
    for cx, cy in seeds:  # first-processed sits on top of the pile
        w = swatch * rng.uniform(0.7, 1.3)
        h = w * aspect * rng.uniform(0.8, 1.2)
        ang = float(rng.choice(angles)) + rng.uniform(-6, 6)
        corners = np.array([[-w, -h], [w, -h], [w, h], [-w, h]]) / 2
        corners *= rng.uniform(0.85, 1.15, size=(4, 1))  # irregular quad
        quad = affinity.rotate(ShapelyPolygon(corners + [cx, cy]), ang)
        vis = quad.intersection(region)
        if covered is not None:
            vis = vis.difference(covered)
        if not vis.is_empty and vis.area > 0.5:
            out += _parallel_lines(vis, ang, spacing, rng, sjit)
        covered = quad if covered is None else covered.union(quad)
        if covered.covers(region):
            break
    return out


def patch_hatch(mask, region, ctx, params, rng) -> list[Polyline]:
    """Classic pen-and-ink facet hatching. Segments the band into
    orientation-coherent patches (surface planes); each patch is filled
    with STRAIGHT parallel lines at its own angle — optionally snapped to
    a limited angle vocabulary — with white seams between patches and an
    optional cross pass. The core move of the reference style."""
    from .patches import segment_facets
    from .photo import mask_to_region

    page = ctx["page"]
    spacing = _p(params, "spacing_mm", 1.1)
    sjit = _p(params, "spacing_jitter", 0.12)
    offset = _p(params, "angle_offset_deg", 0.0)
    jitter = _p(params, "angle_jitter_deg", 5.0)
    snap = _p(params, "snap_deg", 0.0)          # e.g. 30 -> angle vocabulary
    gap = _p(params, "patch_gap_mm", 0.4)       # white seam between patches
    fallback = _p(params, "fallback_angle_deg", 52.0)
    cross_delta = _p(params, "cross_delta_deg", 0.0)  # >0 adds second pass
    out: list[Polyline] = []
    facets = segment_facets(
        mask, ctx,
        sector_deg=_p(params, "sector_deg", 30.0),
        smooth_mm=_p(params, "smooth_mm", 2.5),
        min_coherence=_p(params, "min_coherence", 0.06))
    for fmask, ang, incoherent in facets:
        sub = mask_to_region(fmask, page,
                             min_area_mm2=_p(params, "min_patch_mm2", 25.0),
                             open_mm=0.8, simplify_mm=0.4)
        if sub.is_empty:
            continue
        base = fallback if incoherent else np.degrees(ang) + offset
        if snap > 0:
            base = round(base / snap) * snap
        for poly in getattr(sub, "geoms", [sub]):
            if gap > 0:
                poly = poly.buffer(-gap / 2)
            if poly.is_empty:
                continue
            a = base + rng.uniform(-jitter, jitter)
            out += _parallel_lines(poly, a, spacing, rng, sjit)
            if cross_delta > 0:
                out += _parallel_lines(
                    poly, a + cross_delta,
                    spacing * _p(params, "cross_spacing_scale", 1.15),
                    rng, sjit)
    return out


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
    "fan_hatch": fan_hatch,
    "shingle_hatch": shingle_hatch,
    "patch_hatch": patch_hatch,
    "contour_hatch": contour_hatch,
    "scribble_fill": scribble_fill,
    "solid_fill": solid_fill,
    "contour_lines": contour_lines,
}
