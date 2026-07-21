"""Rung 2 — the ceiling: re-ink the crop by tracing its own skeleton.
Not our vocabulary; the control condition. If even this scores poorly the
crop isn't plotter-reproducible at this pen; if it scores well, the gap
between this and the greedy vocabulary rung is OUR deficiency, localized.
"""

import cv2
import numpy as np

from .measure import coverage_metrics


def simplify(path, eps_px=1.2):
    if len(path) < 3:
        return path
    ap = cv2.approxPolyDP(path.astype(np.float32).reshape(-1, 1, 2),
                          eps_px, False)
    return ap.reshape(-1, 2).astype(float)


def trace_replot(m):
    """-> (canvas ink bool, polylines, stats). Draws every skeleton
    segment at the measured pen width."""
    h, w = m["ink"].shape
    t = max(int(round(m["width_px"])), 1)
    canvas = np.zeros((h, w), np.uint8)
    polys = [simplify(p) for p in m["segments"]]
    pts = [np.round(p).astype(np.int32) for p in polys if len(p) >= 2]
    cv2.polylines(canvas, pts, False, 255, t, cv2.LINE_AA)
    recon = canvas > 127
    tol = max(int(round(m["width_px"])), 2)
    recall, precision = coverage_metrics(recon, m["ink"], tol)
    total_mm = sum(
        float(np.hypot(*np.diff(p, axis=0).T).sum()) for p in polys
        if len(p) >= 2) / m["px_per_mm"]
    return recon, polys, {
        "strokes": len(polys), "recall": recall, "precision": precision,
        "path_mm": round(total_mm, 0)}
