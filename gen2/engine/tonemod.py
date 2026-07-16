"""Continuous tone modulation — a shared post-pass, like humanize.

Classic pen-and-ink tone is continuous WITHIN a patch: the artist lifts
the pen in light areas and lets strokes run in the darks, so skies breathe
with the clouds and slopes shade smoothly. Band quantization alone cannot
say that. tone_gate chunks each line by arc length and keeps chunks by
local darkness sampled from ctx["gray"]:

    darkness >= high  -> keep
    darkness <= low   -> drop
    in between        -> dithered keep, probability ramping low->high

Opt-in per band entry: {"tone_mod": {"low": .., "high": .., "seg_mm": ..}}.
Gray is sampled in page space via the one px<->mm transform (Page).
"""

import numpy as np

from .geom import Polyline, resample

DEFAULTS = {
    "low": 0.12,     # darkness at/below which chunks vanish (bare paper)
    "high": 0.5,     # darkness at/above which chunks always survive
    "seg_mm": 2.2,   # chunk length; smaller = finer dash grain
    "gamma": 1.0,    # >1 biases toward dropping (lighter overall)
}


def tone_gate(lines: list[Polyline], ctx: dict, params: dict | None,
              rng: np.random.Generator,
              dark_map: np.ndarray | None = None) -> list[Polyline]:
    """dark_map overrides the default darkness source (1 - gray): the
    tone_close stage passes its DEFICIT map so chunks survive exactly
    where the drawing is still too light."""
    p = {**DEFAULTS, **(params or {})}
    gray, page = ctx["gray"], ctx["page"]
    h, w = gray.shape
    lo, hi = float(p["low"]), max(float(p["high"]), float(p["low"]) + 1e-6)

    out: list[Polyline] = []
    for ln in lines:
        ln = resample(ln, 0.7)
        if len(ln) < 2:
            continue
        px = page.mm_to_px(ln)
        xi = np.clip(px[:, 0].astype(int), 0, w - 1)
        yi = np.clip(px[:, 1].astype(int), 0, h - 1)
        dark = (dark_map[yi, xi] if dark_map is not None
                else 1.0 - gray[yi, xi])
        if p["gamma"] != 1.0:
            dark = dark ** p["gamma"]

        seg = np.diff(ln, axis=0)
        cum = np.concatenate([[0.0], np.cumsum(np.hypot(seg[:, 0],
                                                        seg[:, 1]))])
        # jittered chunk boundaries so dash edges never align across lines
        ids = ((cum + rng.uniform(0, p["seg_mm"])) // p["seg_mm"]).astype(int)
        keep = np.zeros(len(ln), dtype=bool)
        for cid in np.unique(ids):
            sel = ids == cid
            d = float(dark[sel].mean())
            if d >= hi or (d > lo and rng.random() < (d - lo) / (hi - lo)):
                keep[sel] = True

        # emit maximal kept runs
        idx = np.flatnonzero(keep)
        if idx.size < 2:
            continue
        splits = np.flatnonzero(np.diff(idx) > 1)
        for run in np.split(idx, splits + 1):
            if len(run) >= 2 and cum[run[-1]] - cum[run[0]] >= 0.6:
                out.append(ln[run])
    return out
