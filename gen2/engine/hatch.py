"""Fixed-angle hatching for M0.

Generates raw parallel polylines clipped to a region. No humanization here —
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
