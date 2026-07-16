"""Plan compiler — the composition pipeline as DATA, not scripture.

A genome may carry a "plan" spec instead of hand-written zones; render()
compiles it into zones at render time, deterministically, from frozen
artifacts only (photo bytes + .normals/.semantic/.scene.npz + marks.json).
Every stage is wigglable: channel SOURCES are swappable, compose OPS are
an ordered list you can add/remove/reorder, and mark ASSIGNMENT is a
lookup against the measured value scale with preferences. The mutator
recombines all of it like any other genome material.

    "plan": {
      "channels": {
        "masses":  {"field": "crease+shadow"|"crease+lum"|"lum",
                    "merge": 0.12, "seed_h": 0.01},
        "levels":  {"k": 4, "sigma_frac": 0.012},
        "texture": {"thresh": 0.5} | null
      },
      "compose": [                    # ordered ops, each optional
        {"op": "commit_levels"},      # majority level per mass
        {"op": "weld_small", "min_frac": 0.01},
        {"op": "force_tone", "min_gap": 0.04},   # Guptill: force apart
        {"op": "elect_extremes"},     # principal light -> paper, dark -> max
        {"op": "focal", "pos": "auto"|[fx,fy], "radius_mm": 60}
      ],
      "assign": {
        "targets": [0.0, 0.18, 0.4, 0.62],  # coverage per level (len k)
        "palette": ["blue03", "black03", "black05"],
        "prefer":  ["fixed_hatch", "cross_hatch", "shingle_hatch"],
        "micro_tone": {"low": 0.04, "high": 0.5, "seg_mm": 3.0} | null,
        "emphasis": {"falloff_mm": 35, "floor": 0.1} | null,
        "keyline_mm": 0.6
      },
      "direction": {"mode": "per_mass"|"flow", "snap_deg": 0},
      "sky_zone": {...ordinary zone dict, select filled in...},
      "outline": {"max_level_gap": 1, "pen": "black03",
                  "min_len_mm": 5} | null
    }

Doctrine sources: docs/composition-order.md (Guptill/Payne/Loomis/W&S).
"""

import itertools
import json
import logging
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)

_MARKS_PATH = Path(__file__).parent.parent / "marks.json"
_MARKS = None


def _marks():
    global _MARKS
    if _MARKS is None:
        _MARKS = json.loads(_MARKS_PATH.read_text())
    return _MARKS


def _kmeans1d(vals, k):
    centers = np.quantile(vals, np.linspace(0.1, 0.9, k))
    for _ in range(25):
        a = np.abs(vals[:, None] - centers[None, :]).argmin(1)
        for i in range(k):
            if (a == i).any():
                centers[i] = vals[a == i].mean()
    return np.sort(centers)


def _sky_mask(ctx):
    sem = ctx.get("semantic")
    if sem is None:
        raise ValueError("plan needs a frozen semantic map — rerun "
                         "python -m decompose <photo>")
    ids = [i for i, n in sem["names"].items() if "sky" in n.lower()]
    return np.isin(sem["labels"], ids)


def _masses(ctx, spec, land):
    """Watershed over a boundary-strength field + RAG merge -> label map
    (0 outside land), int32."""
    from scipy import ndimage
    from skimage import graph as skgraph
    from skimage.morphology import h_minima
    from skimage.segmentation import watershed

    page = ctx["page"]
    g = ctx["gray"]
    w = g.shape[1]
    n = ctx.get("normals")
    if n is not None:
        ns = cv2.GaussianBlur(n, (0, 0), 0.02 * w)
        cr = (np.abs(cv2.Sobel(ns[..., 0], cv2.CV_32F, 1, 0)) +
              np.abs(cv2.Sobel(ns[..., 1], cv2.CV_32F, 0, 1)))
    else:
        gb = cv2.GaussianBlur(g, (0, 0), 0.02 * w)
        cr = np.hypot(cv2.Sobel(gb, cv2.CV_32F, 1, 0),
                      cv2.Sobel(gb, cv2.CV_32F, 0, 1))
    cr /= cr.max() + 1e-9
    gb = cv2.GaussianBlur(g, (0, 0), 0.01 * w)
    lg = np.hypot(cv2.Sobel(gb, cv2.CV_32F, 1, 0),
                  cv2.Sobel(gb, cv2.CV_32F, 0, 1))
    lg /= lg.max() + 1e-9
    field_name = spec.get("field", "crease+shadow")
    if field_name == "crease+shadow":
        c2 = _kmeans1d(gb[land].reshape(-1)[::5], 2)
        lit = (np.abs(gb - c2[1]) < np.abs(gb - c2[0])).astype(np.uint8)
        lse = cv2.GaussianBlur(
            (cv2.morphologyEx(lit, cv2.MORPH_GRADIENT,
                              np.ones((3, 3), np.uint8)) > 0
             ).astype(np.float32), (0, 0), 2)
        field = np.maximum(cr, lse * 0.8)
    elif field_name == "crease+lum":
        field = np.maximum(cr, lg)
    else:
        field = lg

    def _w(graph, src, dst, nb):
        d = {"weight": 0.0, "count": 0}
        cs = graph[src].get(nb, d)["count"]
        cd = graph[dst].get(nb, d)["count"]
        ws = graph[src].get(nb, d)["weight"]
        wd = graph[dst].get(nb, d)["weight"]
        return {"count": cs + cd,
                "weight": (cs * ws + cd * wd) / max(cs + cd, 1)}

    mk, _ = ndimage.label(h_minima(field, spec.get("seed_h", 0.01)))
    over = watershed(field, mk, mask=land)
    rag = skgraph.rag_boundary(over, field.astype(np.float64))
    labels = skgraph.merge_hierarchical(
        over, rag, spec.get("merge", 0.12), rag_copy=True,
        in_place_merge=True, merge_func=lambda g_, s, d: None,
        weight_func=_w).astype(np.int32)
    labels[~land] = 0
    # compact ids to 1..N
    ids = [i for i in np.unique(labels) if i != 0]
    lut = np.zeros(labels.max() + 1, np.int32)
    for j, i in enumerate(ids, 1):
        lut[i] = j
    return lut[labels]


def _adjacency(labels):
    """{(a, b): boundary_px} for a < b, excluding 0."""
    pairs = {}
    for ax in (0, 1):
        a = labels if ax == 0 else labels.T
        l, r = a[:, :-1].ravel(), a[:, 1:].ravel()
        m = (l != r) & (l > 0) & (r > 0)
        for x, y in zip(l[m], r[m]):
            k = (int(min(x, y)), int(max(x, y)))
            pairs[k] = pairs.get(k, 0) + 1
    return pairs


# ---------------- compose ops (registry — add your own) --------------------
def op_commit_levels(state, params, ctx):
    lev_map, k = state["lev_map"], state["k"]
    for mid in state["ids"]:
        m = state["labels"] == mid
        vals, cts = np.unique(lev_map[m], return_counts=True)
        state["level"][mid] = int(vals[cts.argmax()])


def op_weld_small(state, params, ctx):
    min_px = params.get("min_frac", 0.01) * state["labels"].size
    adj = _adjacency(state["labels"])
    for mid in list(state["ids"]):
        m = state["labels"] == mid
        if m.sum() >= min_px:
            continue
        nbrs = [(b if a == mid else a, c) for (a, b), c in adj.items()
                if mid in (a, b)]
        if not nbrs:
            continue
        tgt = max(nbrs, key=lambda t: t[1])[0]
        state["labels"][m] = tgt
        state["ids"].remove(mid)
        state["level"].pop(mid, None)


def op_force_tone(state, params, ctx):
    """Guptill: adjacent masses must separate — same level + real source
    difference -> push the darker one down a level."""
    gap = params.get("min_gap", 0.04)
    kmax = state["k"] - 1
    for (a, b), _c in sorted(_adjacency(state["labels"]).items()):
        la, lb = state["level"].get(a), state["level"].get(b)
        if la is None or lb is None or la != lb:
            continue
        da, db = state["dark"][a], state["dark"][b]
        if abs(da - db) < gap:
            continue
        darker = a if da > db else b
        state["level"][darker] = min(state["level"][darker] + 1, kmax)


def op_elect_extremes(state, params, ctx):
    """Principal light mass -> bare paper; principal dark -> max level."""
    big = [i for i in state["ids"]
           if (state["labels"] == i).mean() > params.get("min_frac", 0.04)]
    if big:
        state["level"][min(big, key=lambda i: state["dark"][i])] = 0
        state["level"][max(big, key=lambda i: state["dark"][i])] = \
            state["k"] - 1


def op_focal(state, params, ctx):
    pos = params.get("pos", "auto")
    page = ctx["page"]
    if pos == "auto":
        # centroid of the strongest-contrast adjacent boundary
        adj = _adjacency(state["labels"])
        if not adj:
            return
        (a, b), _n = max(
            adj.items(),
            key=lambda kv: abs(state["dark"][kv[0][0]]
                               - state["dark"][kv[0][1]]) * kv[1])
        m = (cv2.dilate((state["labels"] == a).astype(np.uint8),
                        np.ones((3, 3), np.uint8)) > 0) \
            & (state["labels"] == b)
        ys, xs = np.nonzero(m)
        if not len(xs):
            return
        pmm = page.px_to_mm(np.array([[xs.mean(), ys.mean()]]))[0]
    else:
        pmm = (float(pos[0]) * page.width_mm,
               float(pos[1]) * page.height_mm)
    state["focal"] = [float(pmm[0]), float(pmm[1]),
                      float(params.get("radius_mm", 60.0))]


OPS = {"commit_levels": op_commit_levels, "weld_small": op_weld_small,
       "force_tone": op_force_tone, "elect_extremes": op_elect_extremes,
       "focal": op_focal}


# ---------------- mark assignment ------------------------------------------
def _stack_for(target, palette, prefer, modules=None):
    """Pick 1-2 calibrated marks whose combined coverage best matches the
    target (independent-overlap model: 1 - prod(1 - c)). `modules` is a
    hard whitelist — coverage-closeness must never override the style
    vocabulary the user has actually approved."""
    cands = [r for r in _marks() if r["pen"] in palette
             and (modules is None or r["module"] in modules)]
    best, best_err = None, 9e9
    singles = [(r,) for r in cands]
    pairs = [(a, b) for a, b in itertools.combinations(cands, 2)
             if a["module"] != b["module"] or a["pen"] != b["pen"]]
    for stack in singles + pairs:
        est = 1.0
        for r in stack:
            est *= 1.0 - r["coverage"]
        est = 1.0 - est
        pen_rank = sum(prefer.index(r["module"])
                       if r["module"] in prefer else len(prefer)
                       for r in stack)
        err = abs(est - target) + 0.004 * pen_rank + 0.01 * (len(stack) - 1)
        if err < best_err:
            best, best_err = stack, err
    return best


# ---------------- compilation ----------------------------------------------
def compile_plan(spec: dict, ctx: dict) -> list[dict]:
    ch = spec.get("channels", {})
    sky = _sky_mask(ctx)
    land = ~sky
    g = ctx["gray"]
    w = g.shape[1]

    labels = _masses(ctx, ch.get("masses", {}), land)
    k = ch.get("levels", {}).get("k", 4)
    sig = ch.get("levels", {}).get("sigma_frac", 0.012)
    gb = cv2.GaussianBlur(g, (0, 0), sig * w)
    centers = _kmeans1d(gb[land].reshape(-1)[::5], k)
    lev_map = (k - 1) - np.abs(
        gb[..., None] - centers[None, None, :]).argmin(2)
    # level 0 = LIGHTEST (bare paper), k-1 = darkest

    ids = [int(i) for i in np.unique(labels) if i != 0]
    state = {"labels": labels, "ids": ids, "k": k, "lev_map": lev_map,
             "level": {}, "focal": None,
             "dark": {i: float(1 - g[labels == i].mean()) for i in ids}}
    for step in spec.get("compose", [{"op": "commit_levels"}]):
        OPS[step["op"]](state, step, ctx)
    state["dark"] = {i: float(1 - g[state["labels"] == i].mean())
                     for i in state["ids"]}

    ctx["plan_masses"] = state["labels"]
    ctx["plan_levels"] = {i: state["level"].get(i, 0)
                          for i in state["ids"]}
    ctx["plan_focal"] = state["focal"]

    asg = spec.get("assign", {})
    targets = asg.get("targets",
                      list(np.linspace(0, 0.62, k)))
    palette = asg.get("palette", ["blue03", "black03", "black05"])
    prefer = asg.get("prefer", ["fixed_hatch", "cross_hatch",
                                "shingle_hatch"])
    dirspec = spec.get("direction", {})
    theta = ctx["orientation"]

    zones = []
    if spec.get("sky_zone"):
        zones.append(spec["sky_zone"])
    if ch.get("texture") and spec.get("texture_zone"):
        tz = json.loads(json.dumps(spec["texture_zone"]))
        tz["select"] = {"type": "hsv",
                        "normal_var": [ch["texture"]["thresh"], 1.0],
                        "smooth_mm": 2.5}
        zones.append(tz)

    for mid in sorted(state["ids"],
                      key=lambda i: state["level"].get(i, 0)):
        level = state["level"].get(mid, 0)
        if level == 0 or targets[level] <= 0.01:
            continue  # principal lights stay bare paper
        stack = _stack_for(targets[level], palette, prefer,
                           asg.get("modules"))
        m = state["labels"] == mid
        t = theta[m]
        ang = float(np.degrees(0.5 * np.arctan2(
            np.sin(2 * t).mean(), np.cos(2 * t).mean())))
        snap = dirspec.get("snap_deg", 0)
        if snap:
            ang = round(ang / snap) * snap
        base = []
        for j, r in enumerate(stack):
            entry = {"module": r["module"], "pen": r["pen"],
                     "params": json.loads(json.dumps(r["params"]))}
            if dirspec.get("mode", "per_mass") == "per_mass" and \
                    "angle_deg" in entry["params"]:
                entry["params"]["angle_deg"] = ang + 18.0 * j
            if asg.get("micro_tone") and j == 0:
                entry["tone_mod"] = dict(asg["micro_tone"])
            em = asg.get("emphasis")
            if em:
                entry["emphasis"] = dict(em)
                if state["focal"]:
                    entry["emphasis"]["focal"] = state["focal"]
            base.append(entry)
        zones.append({"name": f"mass{mid}L{level}",
                      "select": {"type": "plan_mass", "id": mid},
                      "keyline_mm": asg.get("keyline_mm", 0.0),
                      "base": base, "bands": []})

    ol = spec.get("outline")
    if ol is not None:
        # Guptill/W&S: outline ONLY where adjacent values fail to separate
        need = np.zeros_like(land, dtype=bool)
        adj = _adjacency(state["labels"])
        for (a, b), _n in adj.items():
            la, lb = state["level"].get(a, 0), state["level"].get(b, 0)
            # outline only where INKED masses fail to separate — paper
            # against paper needs no line (the whites weld, per Payne)
            if min(la, lb) >= 1 and abs(la - lb) \
                    <= ol.get("max_level_gap", 0):
                ma = cv2.dilate((state["labels"] == a).astype(np.uint8),
                                np.ones((3, 3), np.uint8)) > 0
                need |= ma & (state["labels"] == b)
        ctx["plan_outline_mask"] = cv2.dilate(
            need.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
        zones.append({"name": "outline",
                      "select": {"type": "plan_outline"},
                      "bands": [],
                      "base": [{"module": "plan_outline",
                                "pen": ol.get("pen", "black03"),
                                "params": {"min_len_mm":
                                           ol.get("min_len_mm", 5.0)}}]})
    log.info("plan: %d masses -> %d zones, focal=%s",
             len(state["ids"]), len(zones), state["focal"])
    return zones


# ---------------- plan-specific modules -------------------------------------
def plan_outline(mask, region, ctx, params, rng):
    page = ctx["page"]
    need = ctx.get("plan_outline_mask")
    if need is None:
        return []
    contours, _ = cv2.findContours(need.astype(np.uint8), cv2.RETR_LIST,
                                   cv2.CHAIN_APPROX_TC89_L1)
    out = []
    min_len = params.get("min_len_mm", 5.0)
    for c in contours:
        pts = page.px_to_mm(c[:, 0, :].astype(np.float64))
        if len(pts) < 2:
            continue
        seg = np.diff(pts, axis=0)
        if float(np.hypot(seg[:, 0], seg[:, 1]).sum()) >= min_len:
            out.append(pts)
    return out


def arrangement_score(layers, ctx) -> float:
    """Tonecheck v2, the Guptill doctrine: fraction of adjacent mass
    pairs whose rendered-ink ORDER agrees with the source-darkness order
    (weighted by boundary length; pairs the source calls equal are
    ignored). Requires a compiled plan in ctx."""
    from .inkmap import ink_map
    labels = ctx.get("plan_masses")
    if labels is None:
        return -1.0
    cov = ink_map(layers, ctx["page"], ctx["gray"].shape)
    g = ctx["gray"]
    ids = [i for i in np.unique(labels) if i != 0]
    src = {i: float(1 - g[labels == i].mean()) for i in ids}
    ink = {i: float(cov[labels == i].mean()) for i in ids}
    good = tot = 0.0
    for (a, b), n in _adjacency(labels).items():
        ds = src[a] - src[b]
        if abs(ds) < 0.05:
            continue
        di = ink[a] - ink[b]
        tot += n
        if ds * di > 0:
            good += n
    return good / tot if tot else 1.0
