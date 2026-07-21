"""Comb-cover — the arrangement the annotated rockface exposes.

Dense penwork = OVERLAPPING irregular patches of parallel hatching with
no drawn boundaries. A patch is one gesture (a comb): 5-20 parallel
strokes, fBm length envelope (the ragged footprint IS the boundary),
placed where tone is least served, direction committed from the local
field with a snap and a neighbor-contrast rule (a new comb overlapping a
same-angle comb rotates away — facet edges emerge, never drawn).

Delineation is PER-BOUNDARY, not global (the user's observation): each
comb draws an end-margin from a mixture — mostly slight overshoot into
the neighbors (soft, dark-on-dark), sometimes a hard stop-short that
leaves a sliver of paper (crisp edge, typically against a lighter patch).
"""

import cv2
import numpy as np

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.strokes import _fbm            # noqa: E402

from .measure import coverage_metrics, orientation_field  # noqa: E402


def strip_annotation(bgr):
    """Remove red marker annotation by inpainting."""
    b, g, r = bgr[..., 0].astype(int), bgr[..., 1].astype(int), \
        bgr[..., 2].astype(int)
    red = (r > 120) & (r - g > 50) & (r - b > 50)
    red = cv2.dilate(red.astype(np.uint8), np.ones((5, 5), np.uint8))
    return cv2.inpaint(bgr, red, 5, cv2.INPAINT_TELEA)


def comb_segments(center, theta, n_lines, s, L_base, rng,
                  margin_mode="over"):
    """One comb gesture -> list of (2,2) segments. margin_mode 'over'
    = ends overshoot raggedly; 'stop' = ends pull back uniformly, the
    crisp-delineation case."""
    u = np.array([np.cos(theta), np.sin(theta)])
    nv = np.array([-u[1], u[0]])
    env = 0.62 + 0.38 * (_fbm(n_lines, rng, 2.2, 2) + 1) / 2
    segs = []
    for k in range(n_lines):
        off = (k - (n_lines - 1) / 2) * s * (1 + rng.uniform(-.07, .07))
        Lk = L_base * env[k]
        if margin_mode == "stop":
            Lk *= 0.82
            rag = 0.04
        else:
            rag = 0.16
        c = center + nv * off + u * rng.uniform(-.1, .1) * L_base
        a = c - u * Lk * (0.5 + rng.uniform(-rag, rag))
        b = c + u * Lk * (0.5 + rng.uniform(-rag, rag))
        segs.append(np.stack([a, b]))
    return segs


def comb_cover(ink, theta_field, w_px, rng, s_over_w=2.8,
               snap_deg=15.0, contrast_deg=13.0, stop_frac=0.3,
               budget=700, stop_deficit=0.24):
    """Cover the reference ink with combs. -> (canvas bool, combs, stats)."""
    h, w = ink.shape
    s = s_over_w * w_px
    sigma = max(w_px * 1.8, 2.5)
    target = cv2.GaussianBlur(ink.astype(np.float32), (0, 0), sigma)
    canvas = np.zeros((h, w), np.uint8)
    t = max(int(round(w_px)), 1)
    placed = []          # (x, y, theta, reach)
    deficit = target.copy()
    hot, hot_i, since = np.array([], int), 0, 999
    n = attempts = n_strokes = 0
    while n < budget and attempts < budget * 8:
        attempts += 1
        if since >= 6 or hot_i >= len(hot):
            cov = cv2.GaussianBlur((canvas > 0).astype(np.float32),
                                   (0, 0), sigma)
            deficit = target - cov
            if deficit.max() < stop_deficit:
                break
            flat = np.argpartition(deficit.ravel(), -400)[-400:]
            flat = flat[deficit.ravel()[flat] >= stop_deficit]
            if not len(flat):
                break
            rng.shuffle(flat)
            hot, hot_i, since = flat, 0, 0
        sy, sx = divmod(int(hot[hot_i]), w)
        hot_i += 1
        if deficit[sy, sx] < stop_deficit:
            continue
        th = float(theta_field[sy, sx])
        if snap_deg:
            sn = np.deg2rad(snap_deg)
            th = round(th / sn) * sn
        n_lines = int(rng.integers(4, 11))
        L_base = float(rng.uniform(3.5, 8.5)) * s
        reach = max(L_base, n_lines * s) * 0.6
        # neighbor-contrast: same-angle overlap -> rotate away
        for px, py, pth, pr in placed[-60:]:
            if (px - sx) ** 2 + (py - sy) ** 2 < (reach + pr) ** 2 * 0.35:
                d = abs(((th - pth + np.pi / 2) % np.pi) - np.pi / 2)
                if np.degrees(d) < contrast_deg:
                    th += np.deg2rad(rng.choice([-1, 1])
                                     * rng.uniform(18, 30))
                    break
        mode = "stop" if rng.uniform() < stop_frac else "over"
        segs = comb_segments(np.array([sx, sy], float), th, n_lines, s,
                             L_base, rng, mode)
        for seg in segs:
            a, b = np.round(seg).astype(int)
            cv2.line(canvas, tuple(a), tuple(b), 255, t, cv2.LINE_AA)
        n_strokes += len(segs)
        placed.append((sx, sy, th, reach))
        pad = int(reach + sigma)
        deficit[max(sy - pad, 0):sy + pad,
                max(sx - pad, 0):sx + pad] -= 0.2
        n += 1
        since += 1
    recon = canvas > 127
    tol = max(int(round(w_px)), 2)
    recall, precision = coverage_metrics(recon, ink, tol)
    return recon, placed, {"combs": n, "strokes": n_strokes,
                           "recall": round(recall, 4),
                           "precision": round(precision, 4)}
