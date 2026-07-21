"""Rung 3 — the honest one: re-ink the crop with OUR strokes.

Salisbury's importance loop against the crop itself: place a stroke from
the vocabulary where the ink deficit is greatest, oriented by the crop's
measured orientation field, grown as long as the deficit supports it;
repeat until the deficit closes or the budget dies. v0 places hand_line
only — straight hatching is the workhorse of every reference crop; where
straight-only scores badly (curved water, loop canopies) the bench is
MEASURING the missing arrangement, which is the point.
"""

import numpy as np
import cv2

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.strokes import place, stroke  # noqa: E402

from .measure import coverage_metrics     # noqa: E402


def _grow_ray(deficit, seed, ang, step, lo, max_steps):
    """March from seed both ways along ang while deficit stays hot.
    -> (p0, p1) endpoints in px."""
    h, w = deficit.shape
    d = np.array([np.cos(ang), np.sin(ang)])
    ends = []
    for s in (-1, 1):
        p = np.array(seed, float)
        n = 0
        while n < max_steps:
            q = p + s * d * step
            xi, yi = int(round(q[0])), int(round(q[1]))
            if not (0 <= xi < w and 0 <= yi < h) or deficit[yi, xi] < lo:
                break
            p = q
            n += 1
        ends.append(p)
    return ends[0], ends[1]


def greedy_reink(m, rng=None, kind="hand_line",
                 stop_deficit=0.22, budget_ratio=3.0):
    """-> (canvas bool, stats). Budget = budget_ratio x the reference
    segment count — past that, economy has already lost."""
    rng = rng or np.random.default_rng(7)
    ink, theta = m["ink"], m["theta"]
    h, w = ink.shape
    wpx = m["width_px"]
    ppm = m["px_per_mm"]
    sigma = max(wpx * 1.6, 2.0)
    target = cv2.GaussianBlur(ink.astype(np.float32), (0, 0), sigma)
    canvas = np.zeros((h, w), np.uint8)
    t = max(int(round(wpx)), 1)
    budget = int(max(len(m["segments"]) * budget_ratio, 400))
    n = 0
    attempts = 0
    max_attempts = budget * 8
    hot: np.ndarray = np.array([], int)
    hot_i = 0
    placed_since = 999
    deficit = target.copy()
    while n < budget and attempts < max_attempts:
        attempts += 1
        if placed_since >= 25 or hot_i >= len(hot):
            cov = cv2.GaussianBlur((canvas > 0).astype(np.float32),
                                   (0, 0), sigma)
            deficit = target - cov
            if deficit.max() < stop_deficit:
                break
            flat = np.argpartition(deficit.ravel(), -800)[-800:]
            flat = flat[deficit.ravel()[flat] >= stop_deficit]
            if not len(flat):
                break
            rng.shuffle(flat)
            hot, hot_i, placed_since = flat, 0, 0
        pick = int(hot[hot_i])
        hot_i += 1
        sy, sx = divmod(pick, w)
        if deficit[sy, sx] < stop_deficit:
            continue
        ang = float(theta[sy, sx])
        p0, p1 = _grow_ray(deficit, (sx, sy), ang, step=wpx,
                           lo=stop_deficit * 0.6,
                           max_steps=int(45 / 0.35))
        length_px = float(np.hypot(*(p1 - p0)))
        if length_px < wpx * 2.5:
            continue
        g = stroke(kind, length_px / ppm, {},
                   np.random.default_rng(int(rng.integers(1 << 30))))
        ang2 = float(np.arctan2(p1[1] - p0[1], p1[0] - p0[0]))
        placed = place([p * ppm for p in g], p0, ang2)
        pts = [np.round(pp).astype(np.int32) for pp in placed]
        cv2.polylines(canvas, pts, False, 255, t, cv2.LINE_AA)
        # local deficit update so the next seeds move elsewhere
        x0, x1 = sorted((int(p0[0]), int(p1[0])))
        y0, y1 = sorted((int(p0[1]), int(p1[1])))
        pad = int(sigma * 2)
        deficit[max(y0 - pad, 0):y1 + pad, max(x0 - pad, 0):x1 + pad] \
            -= 0.15
        n += 1
        placed_since += 1
    recon = canvas > 127
    tol = max(int(round(wpx)), 2)
    recall, precision = coverage_metrics(recon, ink, tol)
    return recon, {
        "strokes": n, "recall": recall, "precision": precision,
        "budget": budget, "ref_segments": len(m["segments"]),
        "economy": round(n / max(len(m["segments"]), 1), 2),
        "residual_max": round(float(deficit.max()), 3)}
