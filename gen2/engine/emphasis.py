"""Indication — the anti-robotic pass. Winkenbach & Salesin (1994) called
it 'indication': a human artist concentrates ink near feature lines
(creases, silhouettes, strong edges) and lets texture dissipate with
distance, implying the rest. Uniform texture allocation is what makes
procedural output read as generated; this post-pass makes allocation
hierarchical.

Opt-in per band entry, after tone_mod:

    "emphasis": {"falloff_mm": 30,   # e-folding distance from features
                 "floor": 0.1,       # survival probability far away
                 "seg_mm": 3.0,
                 "sources": ["crease", "silhouette", "edges"]}

Feature lines come from the frozen normal map (creases), the scene plan
(object silhouettes), and the photo edge map. Deterministic given ctx.
"""

import cv2
import numpy as np

from .geom import Polyline, resample

DEFAULTS = {
    "falloff_mm": 30.0,
    "floor": 0.1,
    "seg_mm": 3.0,
    "sources": ("crease", "silhouette", "edges"),
    # indication prunes MIDTONES away from features; it must never drop
    # the true darks or tone fidelity collapses (evolve/tonecheck.py)
    "protect_dark": 0.55,
}


def _feature_dist_mm(ctx: dict, sources: tuple) -> np.ndarray:
    """Distance (mm) to the nearest feature line. Cached on ctx."""
    key = ("_feature_dist", tuple(sorted(sources)))
    if key in ctx:
        return ctx[key]
    page = ctx["page"]
    h, w = ctx["gray"].shape
    lines = np.zeros((h, w), bool)
    if "crease" in sources and ctx.get("normals") is not None:
        n = ctx["normals"]
        sig = max(1.5 / page.mm_per_px, 0.5)
        ns = cv2.GaussianBlur(n, (0, 0), sig)
        curv = (np.abs(cv2.Sobel(ns[..., 0], cv2.CV_32F, 1, 0)) +
                np.abs(cv2.Sobel(ns[..., 1], cv2.CV_32F, 0, 1)))
        lines |= curv >= np.percentile(curv, 92)
    if "silhouette" in sources and ctx.get("scene") is not None:
        lab = ctx["scene"]["labels"].astype(np.uint8)
        lines |= cv2.Canny(lab * 29 % 251, 0, 0) > 0
    if "edges" in sources:
        lines |= ctx["edge_map"]
    if not lines.any():
        dist = np.full((h, w), 1e6, np.float32)
    else:
        dist = cv2.distanceTransform(
            (~lines).astype(np.uint8), cv2.DIST_L2, 3) * page.mm_per_px
    ctx[key] = dist.astype(np.float32)
    return ctx[key]


def emphasis_gate(lines: list[Polyline], ctx: dict, params: dict | None,
                  rng: np.random.Generator) -> list[Polyline]:
    p = {**DEFAULTS, **(params or {})}
    dist = _feature_dist_mm(ctx, tuple(p["sources"]))
    page = ctx["page"]
    h, w = dist.shape
    falloff = max(float(p["falloff_mm"]), 1e-3)
    floor = float(p["floor"])

    out: list[Polyline] = []
    for ln in lines:
        ln = resample(ln, 0.7)
        if len(ln) < 2:
            continue
        px = page.mm_to_px(ln)
        xi = np.clip(px[:, 0].astype(int), 0, w - 1)
        yi = np.clip(px[:, 1].astype(int), 0, h - 1)
        d = dist[yi, xi]
        darkness = 1.0 - ctx["gray"][yi, xi]

        seg = np.diff(ln, axis=0)
        cum = np.concatenate([[0.0], np.cumsum(np.hypot(seg[:, 0],
                                                        seg[:, 1]))])
        ids = ((cum + rng.uniform(0, p["seg_mm"]))
               // p["seg_mm"]).astype(int)
        keep = np.zeros(len(ln), dtype=bool)
        focal = p.get("focal")  # [x_mm, y_mm, radius_mm]: ONE center of
        # interest (Guptill) — detail concentrates there, fades elsewhere
        if focal:
            df = np.hypot(ln[:, 0] - focal[0], ln[:, 1] - focal[1])
        protect = float(p["protect_dark"])
        for cid in np.unique(ids):
            sel = ids == cid
            if protect > 0 and float(darkness[sel].mean()) >= protect:
                keep[sel] = True
                continue
            weight = floor + (1 - floor) * np.exp(
                -float(d[sel].mean()) / falloff)
            if focal:
                fw = 0.5 + 0.5 * np.exp(-float(df[sel].mean())
                                        / max(focal[2], 1.0))
                weight = min(weight * fw + 0.05, 1.0)
            if rng.random() < weight:
                keep[sel] = True

        idx = np.flatnonzero(keep)
        if idx.size < 2:
            continue
        splits = np.flatnonzero(np.diff(idx) > 1)
        for run in np.split(idx, splits + 1):
            if len(run) >= 2 and cum[run[-1]] - cum[run[0]] >= 0.6:
                out.append(ln[run])
    return out
