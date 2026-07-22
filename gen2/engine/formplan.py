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


def render_form_plan(plan: dict, rng: np.random.Generator,
                     spacing_scale: float = 1.0) -> dict:
    """Form plan -> layers, in the patch language. spacing_scale < 1 =
    finer pen resolution (user: 'little lines much higher res')."""
    w_mm, h_mm = plan["w_mm"], plan["h_mm"]
    forms = plan["forms"]
    hatch = []

    land_union = unary_union([f["poly"] for f in forms])
    if plan["sky"] is not None:
        sky_fill = plan["sky"].difference(land_union.buffer(1.4))
        hatch += fixed_hatch(sky_fill, 2.0, 1.15 * spacing_scale, rng,
                             spacing_jitter=0.05)

    auras = [1.1 if f["level"] >= 2 else 0.0 for f in forms]
    pairs = object_scene([f["poly"] for f in forms], auras)

    for f, (fill, _vis) in zip(forms, pairs):
        if fill.is_empty:
            continue
        sp = SPACINGS[min(f["level"], len(SPACINGS) - 1)]
        if sp is None:
            continue  # principal light: bare paper
        sp = sp * spacing_scale
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


def build_normal_form_plan(photo_path: str, w_mm: float = 130.0,
                           h_mm: float = 190.0, k: int = 5,
                           blur_mm: float = 5.0,
                           sun=(315.0, 40.0),
                           snap_deg: float = 15.0) -> dict:
    """FORMING v2 — the user's call: the watershed masses were unrelated
    to the image (tossed; kept only as the negative example). The
    Marigold NORMALS are the form signal: posterize surface direction
    (k-means on the smoothed normal vectors), split classes into
    connected regions, absorb slivers. Angle = each form's fall line;
    value = relight (n·L, sun as a knob) quantized — lit snow stays
    paper, shadow faces hatch, exactly the artist's liberty."""
    from scipy import ndimage

    from .scene import relight

    bgr = cv2.imread(str(photo_path))
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    H, W = gray.shape
    s = max(W / (w_mm - 16), H / (h_mm - 16))
    page_box = box(8, 8, w_mm - 8, h_mm - 8)

    nrm = load_normals(photo_path, gray.shape)
    sem = load_semantic(photo_path, gray.shape)
    sky_ids = [i for i, n in sem["names"].items() if "sky" in n.lower()]
    sky_mask = np.isin(sem["labels"], sky_ids)
    scene = load_scene(photo_path, gray.shape)
    land = ~sky_mask

    ns = cv2.GaussianBlur(nrm, (0, 0), max(blur_mm * s, 1.0))
    feats = ns[land].reshape(-1, 3).astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-3)
    _c, lab, _ctr = cv2.kmeans(feats, k, None, crit, 4,
                               cv2.KMEANS_PP_CENTERS)
    cls = np.zeros((H, W), np.int32)
    cls[land] = lab.ravel() + 1
    # light cleanup only — heavy median blobbed the map beyond
    # recognition (user: "doesn't seem like you're using it at all")
    cls = cv2.medianBlur(cls.astype(np.uint8), 5).astype(np.int32)
    cls[~land] = 0
    # connected components PER CLASS so far-apart same-direction faces
    # stay separate forms
    labels = np.zeros((H, W), np.int32)
    nxt = 1
    for c in range(1, k + 1):
        cc, n_cc = ndimage.label(cls == c, structure=np.ones((3, 3)))
        m = cc > 0
        labels[m] = cc[m] + nxt - 1
        nxt += n_cc
    # absorb small fragments into their biggest neighbor
    for _pass in range(20):
        ids_now = [int(i) for i in np.unique(labels) if i != 0]
        fr = {i: float((labels == i).mean()) for i in ids_now}
        small = [i for i in ids_now if fr[i] < 0.006]
        if not small:
            break
        adj = _adjacency(labels)
        prog = False
        for i in small:
            nbrs = [(b if a == i else a, c) for (a, b), c in adj.items()
                    if i in (a, b) and (b if a == i else a) != 0]
            if not nbrs:
                continue
            labels[labels == i] = max(nbrs, key=lambda t: t[1])[0]
            prog = True
        if not prog:
            break

    # sun: fit azimuth to the PHOTO's lighting — the relit shade should
    # agree with what the camera saw (correlate over land)
    best_az, best_c = sun[0], -2.0
    gl = gray[land]
    gl = (gl - gl.mean()) / (gl.std() + 1e-9)
    for az in range(0, 360, 30):
        sh = relight(nrm, float(az), sun[1])[land]
        sh = (sh - sh.mean()) / (sh.std() + 1e-9)
        c = float((sh * gl).mean())
        if c > best_c:
            best_az, best_c = float(az), c
    shade = relight(nrm, best_az, sun[1])
    log.info("sun azimuth fit: %d deg (corr %.2f)", int(best_az), best_c)
    # paper-heavy value distribution like the reference: ~40% bare,
    # ~30% L1, ~20% L2, only the darkest ~10% at L3
    qs = np.quantile(shade[land], [0.10, 0.30, 0.60])
    ids = [int(i) for i in np.unique(labels) if i != 0]
    forms = []
    for i in ids:
        mask = labels == i
        poly = _mask_to_poly(mask, s, page_box)
        if poly is None:
            continue
        nm = nrm[mask].mean(0)
        ang = float(np.degrees(np.arctan2(nm[1], nm[0])))
        if snap_deg > 0:
            ang = round(ang / snap_deg) * snap_deg
        sh = float(shade[mask].mean())
        level = 3 - int(np.digitize(sh, qs))
        forms.append({"id": i, "poly": poly, "angle": ang,
                      "level": level,
                      "depth": float(scene["depth"][mask].mean()),
                      "dark": 1 - sh})
    forms.sort(key=lambda f: f["depth"])
    sky_poly = _mask_to_poly(sky_mask, s, page_box, eps_mm=0.9)
    log.info("normal form plan: %d forms (k=%d blur=%.1f)", len(forms),
             k, blur_mm)
    return {"forms": forms, "sky": sky_poly, "labels": labels,
            "w_mm": w_mm, "h_mm": h_mm, "px_per_mm": s, "bgr": bgr,
            "cls": cls, "shade": shade, "normals": nrm,
            "sun_az": best_az}


def normals_viz(plan: dict, step_px: int = 26) -> np.ndarray:
    """The marigold map with the DERIVED direction field drawn on it —
    short strokes at each grid point along the fall line the render
    will use. Judge downslope-ness directly against the map."""
    nrm = plan["normals"]
    img = ((nrm + 1) / 2 * 255).astype(np.uint8)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    H, W = nrm.shape[:2]
    for y in range(step_px // 2, H, step_px):
        for x in range(step_px // 2, W, step_px):
            nx, ny = float(nrm[y, x, 0]), float(nrm[y, x, 1])
            mag = np.hypot(nx, ny)
            if mag < 0.08:
                continue
            L = step_px * 0.42 * min(mag * 2.5, 1.0)
            dx, dy = nx / mag * L, ny / mag * L
            cv2.line(img, (int(x - dx), int(y - dy)),
                     (int(x + dx), int(y + dy)), (20, 20, 20), 2,
                     cv2.LINE_AA)
    return img


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
