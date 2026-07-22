"""FORMING & ANGLES — the fusion of the two tracks.

July's composition doctrine (engine/plan.py: watershed masses on the
crease+shadow field, Payne-edited by the compose ops, one committed
VALUE per mass) meets the vocabulary arc (aniso patch fills, emergent
fold boundaries, separation slivers, ruled sky). The unit is the FORM:

    form = simplified polygon + committed value level + committed angle

Angle policy (the reference artist's, observed):
  - one angle per form, from the mean normals fall-line, snapped 15°
  - ANGLE SEPARATION: adjacent inked forms may not sit within 12° of
    each other — the ghost-seam invariant promoted to mass level; the
    smaller form rotates away
  - light forms (levels 0-1): bare paper / one calm unbroken sweep
  - dark forms (levels 2-3): faceted — aniso cells at the form angle
    with sparse ±15° micro-commitments (the rock register)
Separation policy: sky always yields a sliver around the land; dark
forms (level >= 2) cast slivers into what lies behind them (depth from
the frozen scene plan); light-against-light butts and welds (Payne:
the whites weld).
"""

import logging

import cv2
import numpy as np
import shapely
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from .hatch import fixed_hatch
from .plan import OPS, _adjacency, _kmeans1d, _masses
from .regions import aniso_mesh, object_scene
from .scene import load_normals, load_scene, load_semantic, normals_field

log = logging.getLogger(__name__)

SPACINGS = [None, 1.9, 1.15, 0.7]  # per level, light -> dark


def _mask_to_poly(mask, s, page_box, eps_mm=1.1):
    m = cv2.dilate(mask.astype(np.uint8), np.ones((3, 3), np.uint8))
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL,
                             cv2.CHAIN_APPROX_SIMPLE)
    parts = []
    for c in cs:
        if cv2.contourArea(c) < (2.5 * s) ** 2:
            continue
        ap = cv2.approxPolyDP(c, eps_mm * s, True)[:, 0, :]
        if len(ap) < 3:
            continue
        p = Polygon(ap / s + 8)
        parts.append(p if p.is_valid else p.buffer(0))
    if not parts:
        return None
    p = unary_union(parts).intersection(page_box)
    return None if p.is_empty else p


def build_form_plan(photo_path: str, w_mm: float = 130.0,
                    h_mm: float = 190.0, k: int = 4,
                    merge: float = 0.14) -> dict:
    """photo (+ frozen normals/semantic/scene) -> the form plan."""
    bgr = cv2.imread(str(photo_path))
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    H, W = gray.shape
    s = max(W / (w_mm - 16), H / (h_mm - 16))  # px per mm
    page_box = box(8, 8, w_mm - 8, h_mm - 8)

    nrm = load_normals(photo_path, gray.shape)
    theta, _coh, _var = normals_field(nrm, 1 / s, smooth_mm=8.0)
    sem = load_semantic(photo_path, gray.shape)
    sky_ids = [i for i, n in sem["names"].items() if "sky" in n.lower()]
    sky_mask = np.isin(sem["labels"], sky_ids)
    scene = load_scene(photo_path, gray.shape)
    land = ~sky_mask

    # --- masses: July's watershed, Payne-edited --------------------------
    ctx = {"gray": gray, "normals": nrm, "page": None}
    labels = _masses(ctx, {"field": "crease+shadow", "merge": merge,
                           "seed_h": 0.01}, land)
    gb = cv2.GaussianBlur(gray, (0, 0), 0.012 * W)
    centers = _kmeans1d(gb[land].reshape(-1)[::5], k)
    lev_map = (k - 1) - np.abs(
        gb[..., None] - centers[None, None, :]).argmin(2)
    ids = [int(i) for i in np.unique(labels) if i != 0]
    state = {"labels": labels, "ids": ids, "k": k, "lev_map": lev_map,
             "level": {}, "focal": None,
             "dark": {i: float(1 - gray[labels == i].mean())
                      for i in ids}}
    for op, prm in (("commit_levels", {}),
                    ("weld_small", {"min_frac": 0.012}),
                    ("force_tone", {"min_gap": 0.04}),
                    ("elect_extremes", {})):
        OPS[op](state, prm, ctx)
    labels = state["labels"]
    # absorb EVERY small mass, from the LABEL MAP itself — plan.py's
    # weld leaves zombie ids (chained welds keep pixels labeled with
    # removed ids) and a stale adjacency; trust only the pixels
    for _pass in range(24):
        ids_now = [int(i) for i in np.unique(labels) if i != 0]
        fr = {i: float((labels == i).mean()) for i in ids_now}
        small = [i for i in ids_now
                 if fr[i] < 0.008 or i not in state["level"]]
        big = [i for i in ids_now if i not in small]
        if not small or not big:
            break
        adj = _adjacency(labels)
        progressed = False
        for i in small:
            nbrs = [(b if a == i else a, c) for (a, b), c in adj.items()
                    if i in (a, b)]
            nbrs = [(j, c) for j, c in nbrs if j in big]
            if not nbrs:
                nbrs = [(j, c) for j, c in
                        [(b if a == i else a, c) for (a, b), c
                         in adj.items() if i in (a, b)] if j != 0]
            if not nbrs:
                continue
            tgt = max(nbrs, key=lambda t: t[1])[0]
            labels[labels == i] = tgt
            progressed = True
        if not progressed:
            break
    ids = [int(i) for i in np.unique(labels)
           if i != 0 and i in state["level"]]

    # --- commit per-form ANGLE + separation ------------------------------
    angle = {}
    for i in ids:
        t2 = 2 * theta[labels == i]
        a = float(np.degrees(0.5 * np.arctan2(np.sin(t2).mean(),
                                              np.cos(t2).mean())))
        angle[i] = round(a / 15) * 15.0
    area = {i: int((labels == i).sum()) for i in ids}
    for (a, b), _n in sorted(_adjacency(labels).items()):
        la = state["level"].get(a, 0)
        lb = state["level"].get(b, 0)
        if la == 0 or lb == 0 or a not in angle or b not in angle:
            continue
        d = abs(((angle[a] - angle[b] + 90) % 180) - 90)
        if d < 12:
            small = a if area[a] < area[b] else b
            angle[small] = angle[small] + \
                (15.0 if (small * 7) % 2 else -15.0)

    # --- geometry + depth ------------------------------------------------
    forms = []
    for i in ids:
        mask = labels == i
        if mask.mean() < 0.004:
            continue
        poly = _mask_to_poly(mask, s, page_box)
        if poly is None:
            continue
        forms.append({
            "id": i, "poly": poly,
            "level": int(state["level"].get(i, 0)),
            "angle": float(angle[i]),
            "depth": float(scene["depth"][mask].mean()),
            "dark": state["dark"].get(i, 0.0)})
    forms.sort(key=lambda f: f["depth"])  # far -> near
    sky_poly = _mask_to_poly(sky_mask, s, page_box, eps_mm=0.9)
    log.info("form plan: %d forms, levels %s", len(forms),
             sorted({f['level'] for f in forms}))
    return {"forms": forms, "sky": sky_poly, "labels": labels,
            "levels": {f["id"]: f["level"] for f in forms},
            "angles": {f["id"]: f["angle"] for f in forms},
            "w_mm": w_mm, "h_mm": h_mm, "px_per_mm": s, "bgr": bgr}


def render_form_plan(plan: dict, rng: np.random.Generator) -> dict:
    """Form plan -> layers, in the patch language."""
    w_mm, h_mm = plan["w_mm"], plan["h_mm"]
    forms = plan["forms"]
    hatch = []

    land_union = unary_union([f["poly"] for f in forms])
    if plan["sky"] is not None:
        sky_fill = plan["sky"].difference(land_union.buffer(1.4))
        hatch += fixed_hatch(sky_fill, 2.0, 1.15, rng,
                             spacing_jitter=0.05)

    auras = [1.1 if f["level"] >= 2 else 0.0 for f in forms]
    pairs = object_scene([f["poly"] for f in forms], auras)

    for f, (fill, _vis) in zip(forms, pairs):
        if fill.is_empty:
            continue
        sp = SPACINGS[min(f["level"], len(SPACINGS) - 1)]
        if sp is None:
            continue  # principal light: bare paper
        if f["level"] <= 1:
            # calm register: one unbroken sweep at the committed angle
            hatch += fixed_hatch(fill, f["angle"], sp, rng,
                                 spacing_jitter=0.05)
            continue
        # rock register: faceted fill, micro-commitments around the angle
        cells, _nb, _th = aniso_mesh(
            w_mm, h_mm, rng,
            n_parents=int(np.clip(fill.area / 110, 10, 90)))
        covered = None
        for cell in cells:
            if cell is None:
                continue
            cc = cell.intersection(fill)
            if cc.is_empty:
                continue
            ang = f["angle"] + float(rng.choice(
                [-15.0, 0.0, 0.0, 0.0, 15.0]))
            hatch += fixed_hatch(cc, ang, sp, rng, spacing_jitter=0.05)
            covered = cc if covered is None else covered.union(cc)
        rest = (fill if covered is None
                else fill.difference(covered)).buffer(-0.55).buffer(0.5)
        for part in getattr(rest, "geoms", [rest]):
            if not part.is_empty and part.area > 3.0:
                hatch += fixed_hatch(part, f["angle"], sp, rng,
                                     spacing_jitter=0.05)
    return {"black03": hatch}


def plan_viz(plan: dict) -> np.ndarray:
    """The form plan as its own reviewable artifact: each form colored,
    labeled with its committed level and angle."""
    labels = plan["labels"]
    h, w = labels.shape
    img = np.full((h, w, 3), 245, np.uint8)
    for f in plan["forms"]:
        m = labels == f["id"]
        hue = int((f["id"] * 0.618 % 1) * 179)
        col = cv2.cvtColor(np.uint8([[[hue, 120, 225]]]),
                           cv2.COLOR_HSV2BGR)[0, 0]
        img[m] = col
        ys, xs = np.nonzero(m)
        if len(xs) > 400:
            cv2.putText(img, f"L{f['level']} {int(f['angle'])%180}",
                        (int(xs.mean()) - 24, int(ys.mean()) + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (255, 255, 255), 3, cv2.LINE_AA)
            cv2.putText(img, f"L{f['level']} {int(f['angle'])%180}",
                        (int(xs.mean()) - 24, int(ys.mean()) + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1,
                        cv2.LINE_AA)
    k3 = np.ones((3, 3), np.uint8)
    edges = cv2.morphologyEx(labels.astype(np.float32),
                             cv2.MORPH_GRADIENT, k3) > 0
    img[edges] = (255, 255, 255)
    return img
