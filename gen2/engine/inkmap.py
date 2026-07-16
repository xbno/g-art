"""Ink coverage rasterization — the engine measuring its own drawing.

Rasterizes the accumulated polylines at working resolution (pen widths
parsed from the name convention 'blue03' -> 0.3mm) and blurs to a 0..1
coverage map. Used by the tone_close stage to compute the DEFICIT between
the tone the source demands and the ink laid so far — Salisbury's (1997)
importance-driven loop: add strokes where the drawing is still too light,
stop when matched.
"""

import re

import cv2
import numpy as np

from .geom import Polyline


def pen_width_mm(pen: str) -> float:
    m = re.search(r"(\d+)$", pen)
    return int(m.group(1)) / 10.0 if m else 0.3


def ink_map(layers: dict[str, list[Polyline]], page,
            shape: tuple[int, int], blur_mm: float = 1.4) -> np.ndarray:
    """-> HxW float32 coverage 0..1 (1 = solid ink at this blur scale)."""
    canvas = np.zeros(shape, np.uint8)
    for pen, lines in layers.items():
        t = max(int(round(pen_width_mm(pen) / page.mm_per_px)), 1)
        pts = [np.round(page.mm_to_px(np.asarray(ln))).astype(np.int32)
               for ln in lines if len(ln) >= 2]
        if pts:
            cv2.polylines(canvas, pts, False, 255, t)
    k = max(int(round(blur_mm / page.mm_per_px)), 1) * 2 + 1
    cov = cv2.boxFilter(canvas.astype(np.float32) / 255.0, -1, (k, k))
    return np.clip(cov, 0.0, 1.0)
