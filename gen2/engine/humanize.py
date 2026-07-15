"""Shared humanization post-pass.

Applied to every module's output so all lines get the same hand-feel.
Wobble is sampled in PAGE space (x,y in mm), not per-line parameter space,
so parallel lines never wobble in sync.
"""

import numpy as np
from opensimplex import OpenSimplex

from .geom import Polyline, resample, length

DEFAULTS = {
    "resample_mm": 0.7,
    "wobble_amp_mm": 0.22,
    "wobble_freq": 0.13,        # cycles per mm-ish (simplex input scale)
    "wobble_octave2": 0.45,     # second octave weight at 3x freq
    "end_jitter_mm": 0.5,       # random trim at each end
    "overshoot_prob": 0.28,
    "overshoot_mm": 1.3,
    "break_per_mm": 0.006,      # probability of a gap per mm of length
    "break_gap_mm": 1.1,
}


def _trim_or_extend(line: Polyline, amt_start: float,
                    amt_end: float) -> Polyline:
    """Positive = extend past the endpoint along the tangent,
    negative = trim inward. Amounts in mm."""
    out = line
    if len(out) < 2:
        return out
    for end in (0, 1):
        amt = amt_start if end == 0 else amt_end
        if abs(amt) < 1e-6 or len(out) < 2:
            continue
        if end == 0:
            tan = out[0] - out[1]
        else:
            tan = out[-1] - out[-2]
        n = np.linalg.norm(tan)
        if n < 1e-9:
            continue
        tan = tan / n
        if amt > 0:
            pt = (out[0] if end == 0 else out[-1]) + tan * amt
            out = np.vstack([pt, out]) if end == 0 else np.vstack([out, pt])
        else:
            # walk inward, dropping vertices
            want = -amt
            while len(out) > 2:
                seg = np.linalg.norm(
                    out[0] - out[1] if end == 0 else out[-1] - out[-2])
                if seg > want:
                    break
                out = out[1:] if end == 0 else out[:-1]
                want -= seg
            tan2 = (out[1] - out[0]) if end == 0 else (out[-2] - out[-1])
            n2 = np.linalg.norm(tan2)
            if n2 > 1e-9 and want > 0:
                if end == 0:
                    out = np.vstack([out[0] + tan2 / n2 * want, out[1:]])
                else:
                    out = np.vstack([out[:-1], out[-1] + tan2 / n2 * want])
    return out


def humanize(lines: list[Polyline], seed: int,
             params: dict | None = None) -> list[Polyline]:
    p = {**DEFAULTS, **(params or {})}
    rng = np.random.default_rng(seed)
    nx = OpenSimplex(seed * 2 + 1)
    ny = OpenSimplex(seed * 2 + 2)
    f, f2 = p["wobble_freq"], p["wobble_freq"] * 3.1
    amp, w2 = p["wobble_amp_mm"], p["wobble_octave2"]

    out: list[Polyline] = []
    for ln in lines:
        # endpoint character first (on the clean line)
        s = (rng.uniform(0, p["overshoot_mm"])
             if rng.random() < p["overshoot_prob"]
             else -rng.uniform(0, p["end_jitter_mm"]))
        e = (rng.uniform(0, p["overshoot_mm"])
             if rng.random() < p["overshoot_prob"]
             else -rng.uniform(0, p["end_jitter_mm"]))
        ln = _trim_or_extend(ln, s, e)
        if len(ln) < 2 or length(ln) < 0.4:
            continue

        ln = resample(ln, p["resample_mm"])
        dx = np.array([nx.noise2(x * f, y * f) +
                       w2 * nx.noise2(x * f2, y * f2)
                       for x, y in ln])
        dy = np.array([ny.noise2(x * f, y * f) +
                       w2 * ny.noise2(x * f2, y * f2)
                       for x, y in ln])
        ln = ln + amp * np.column_stack([dx, dy])

        # break long lines with small pen-lift gaps
        total = length(ln)
        n_breaks = rng.poisson(total * p["break_per_mm"])
        if n_breaks == 0:
            out.append(ln)
            continue
        seg = np.diff(ln, axis=0)
        cum = np.concatenate([[0], np.cumsum(np.hypot(seg[:, 0],
                                                      seg[:, 1]))])
        cuts = np.sort(rng.uniform(0.15, 0.85, n_breaks)) * total
        gap = p["break_gap_mm"]
        start = 0.0
        for c in cuts:
            lo, hi = start, max(c - gap / 2, start)
            piece = _slice_by_arclen(ln, cum, lo, hi)
            if piece is not None:
                out.append(piece)
            start = c + gap / 2
        piece = _slice_by_arclen(ln, cum, start, total)
        if piece is not None:
            out.append(piece)
    return out


def _slice_by_arclen(ln: Polyline, cum: np.ndarray,
                     lo: float, hi: float) -> Polyline | None:
    if hi - lo < 0.5:
        return None
    ts = cum
    xs = np.interp([lo, hi], ts, ln[:, 0])
    ys = np.interp([lo, hi], ts, ln[:, 1])
    inner = (ts > lo) & (ts < hi)
    pts = np.vstack([[xs[0], ys[0]], ln[inner], [xs[1], ys[1]]])
    return pts if len(pts) >= 2 else None
