"""Straight-line hatching primitives: parallel and fan (vanishing point).

Generates raw polylines clipped to a region. No humanization here —
wobble/jitter/overshoot is the shared post-pass in humanize.py, never baked
into a module.
"""

import numpy as np

from .geom import Polyline, clip_lines


def fixed_hatch(region, angle_deg: float, spacing_mm: float,
                rng: np.random.Generator,
                spacing_jitter: float = 0.12,
                min_len_mm: float = 0.8) -> list[Polyline]:
    """Parallel lines at angle_deg clipped to a shapely region (mm)."""
    if region.is_empty:
        return []
    minx, miny, maxx, maxy = region.bounds
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    th = np.deg2rad(angle_deg)
    d = np.array([np.cos(th), np.sin(th)])    # along-line direction
    nrm = np.array([-np.sin(th), np.cos(th)])  # across-line normal

    # cover the bbox diagonal from the center in both normal directions
    half = float(np.hypot(maxx - minx, maxy - miny)) / 2 + spacing_mm
    lines = []
    off = -half
    while off <= half:
        base = np.array([cx, cy]) + nrm * off
        lines.append(np.array([base - d * half, base + d * half]))
        off += spacing_mm * (1.0 + rng.uniform(-spacing_jitter,
                                               spacing_jitter))
    return clip_lines(lines, region, min_len_mm=min_len_mm)


def fan_hatch(region, pivot_mm, spacing_mm: float,
              rng: np.random.Generator,
              spacing_jitter: float = 0.12,
              min_len_mm: float = 0.8, max_rays: int = 4000
              ) -> list[Polyline]:
    """Rays through a pivot point clipped to a shapely region (mm).

    With the pivot far off-page the strokes read as near-parallel but
    subtly converge toward it — hand hatching toward a vanishing point
    (a summit, the sun, a horizon point). Pivot inside the region gives a
    sunburst. Arc spacing equals spacing_mm at the region-center radius,
    so strokes naturally diverge slightly with distance, like real fans.
    """
    if region.is_empty:
        return []
    minx, miny, maxx, maxy = region.bounds
    p = np.asarray(pivot_mm, dtype=float)
    corners = np.array([[minx, miny], [minx, maxy],
                        [maxx, miny], [maxx, maxy]])
    v = corners - p
    rad = np.hypot(v[:, 0], v[:, 1])
    center = np.array([(minx + maxx) / 2, (miny + maxy) / 2])
    rc = max(float(np.hypot(*(center - p))), spacing_mm)
    dth = spacing_mm / rc
    inside = (minx <= p[0] <= maxx) and (miny <= p[1] <= maxy)
    if inside:
        a0, a1, r0 = -np.pi, np.pi - dth, 0.0
    else:
        ang = np.arctan2(v[:, 1], v[:, 0])
        rel = (ang - ang[0] + np.pi) % (2 * np.pi) - np.pi
        a0 = float(ang[0] + rel.min()) - dth
        a1 = float(ang[0] + rel.max()) + dth
        r0 = max(float(rad.min()) - spacing_mm, 0.0)
    r1 = float(rad.max()) + spacing_mm
    lines = []
    th = a0
    while th <= a1 and len(lines) < max_rays:
        d = np.array([np.cos(th), np.sin(th)])
        lines.append(np.array([p + d * r0, p + d * r1]))
        th += dth * (1.0 + rng.uniform(-spacing_jitter, spacing_jitter))
    return clip_lines(lines, region, min_len_mm=min_len_mm)
