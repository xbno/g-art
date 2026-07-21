"""Micro-patch fitting: reduce a 10-50-stroke patch of reference penwork
to a compact parametric hatch model, scalelessly.

SCALELESS DOCTRINE: crops arrive at arbitrary zoom, so nothing is in mm.
The measured stroke width w (px) is the unit; every fitted parameter is a
ratio — spacing s/w, length len/w. A style is a set of ratios; pen size
is just another ratio.

Model per FORM (a patch may hold several forms — regions of coherent
hatch direction, split before fitting):

    theta0 + gx·x + gy·y   stroke direction field (linear — captures fans)
    s                      spacing between stroke centerlines (px)
    phi                    phase of the line family
    w                      stroke width (px)

Fit = estimate from measurements (structure tensor, normal-projection
histogram), then coordinate-descent refine against the leak/miss loss:

    miss = ink we failed to cover     (1 - recall  at w/2 tolerance)
    leak = ink we invented on paper   (1 - precision at w/2 tolerance)

Transfer test: a fitted solution applied to ANOTHER patch keeps the
STYLE ratios (s/w, w) and re-estimates only CONTENT (theta field, phi) —
if scores hold, the ratios are the artist's invariant, and we've learned
an expressive behavior, not memorized a patch.
"""

import cv2
import numpy as np

from .measure import coverage_metrics, orientation_field, stroke_width_px


def load_patch(path):
    bgr = cv2.imread(str(path))
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    lo, hi = np.percentile(gray, [8, 92])
    ink = gray < (lo + hi) / 2
    return bgr, gray, ink


def split_forms(gray, ink, w_px, k_max=3, min_frac=0.12):
    """Regions of coherent stroke direction — the 'forms' inside a patch.
    Doubled-angle kmeans over the orientation field; smallest k whose
    within-cluster angular spread is tight. -> label map (0..k-1), k."""
    theta, coh = orientation_field(gray, sigma_px=max(w_px * 1.5, 2.5))
    f = np.stack([np.cos(2 * theta) * coh, np.sin(2 * theta) * coh], -1)
    fs = cv2.GaussianBlur(f, (0, 0), max(w_px, 2.0))
    feats = fs.reshape(-1, 2).astype(np.float32)
    best = None
    for k in range(1, k_max + 1):
        crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
                30, 1e-3)
        comp, lab, ctr = cv2.kmeans(feats, k, None, crit, 4,
                                    cv2.KMEANS_PP_CENTERS)
        lab = lab.reshape(gray.shape)
        # dispersion: mean angular distance to own center
        disp = 0.0
        for i in range(k):
            m = lab == i
            if not m.any():
                continue
            c = ctr[i] / (np.linalg.norm(ctr[i]) + 1e-9)
            v = fs[m] / (np.linalg.norm(fs[m], axis=1,
                                        keepdims=True) + 1e-9)
            disp += (1 - (v @ c)).mean() * m.mean()
        if best is None or disp < best[0] - 0.015:
            best = (disp, k, lab)
    _, k, lab = best
    lab = cv2.medianBlur(lab.astype(np.uint8), 2 * int(w_px) * 2 + 1)
    # absorb tiny regions
    for i in range(k):
        if (lab == i).mean() < min_frac:
            m = (lab == i).astype(np.uint8)
            near = cv2.dilate(m, np.ones((7, 7), np.uint8)) > 0
            vals = lab[near & (lab != i)]
            if vals.size:
                lab[lab == i] = np.bincount(vals).argmax()
    ids = np.unique(lab)
    remap = {v: j for j, v in enumerate(ids)}
    lab = np.vectorize(remap.get)(lab).astype(np.uint8)
    return lab, len(ids)


def _theta_field_fit(gray, mask, w_px):
    """Mean direction + linear gradient (the fan term) over a form."""
    theta, coh = orientation_field(gray, sigma_px=max(w_px * 1.5, 2.5))
    m = mask & (coh > np.percentile(coh[mask], 30))
    t2 = 2 * theta[m]
    t0 = 0.5 * np.arctan2(np.sin(t2).mean(), np.cos(t2).mean())
    # unwrap local angles around t0, fit linear field
    d = (theta[m] - t0 + np.pi / 2) % np.pi - np.pi / 2
    ys, xs = np.nonzero(m)
    h, w = gray.shape
    A = np.stack([xs / w - 0.5, ys / h - 0.5, np.ones_like(xs)], 1)
    coef, *_ = np.linalg.lstsq(A, d, rcond=None)
    gx, gy, dc = float(coef[0]), float(coef[1]), float(coef[2])
    return float(t0 + dc), gx, gy


def render_hatch(shape, mask, theta0, gx, gy, s, phi, w_px):
    """Draw the hatch family inside mask. Straight fast path when the
    angle gradient is negligible; streamline march otherwise."""
    h, w = shape
    canvas = np.zeros((h, w), np.uint8)
    t = max(int(round(w_px)), 1)
    diag = int(np.hypot(h, w))
    if abs(gx) + abs(gy) < 0.06:
        n = np.array([-np.sin(theta0), np.cos(theta0)])
        u = np.array([np.cos(theta0), np.sin(theta0)])
        c = np.array([w / 2, h / 2])
        c0 = float(n @ c)
        k0 = int(np.floor((-diag - c0 - phi) / s))
        k1 = int(np.ceil((diag - c0 - phi) / s))
        for k in range(k0, k1 + 1):
            p = c + n * (phi + k * s - c0)
            a, b = p - u * diag, p + u * diag
            cv2.line(canvas, tuple(np.round(a).astype(int)),
                     tuple(np.round(b).astype(int)), 255, t, cv2.LINE_AA)
    else:
        # seeds along the central normal axis, integrate the angle field
        c = np.array([w / 2, h / 2])
        n0 = np.array([-np.sin(theta0), np.cos(theta0)])
        for k in range(-int(diag / s) - 1, int(diag / s) + 2):
            p0 = c + n0 * (phi + k * s - float(n0 @ c))
            for sgn in (1, -1):
                p = p0.copy()
                pts = [p.copy()]
                for _ in range(diag):
                    th = theta0 + gx * (p[0] / w - 0.5) \
                        + gy * (p[1] / h - 0.5)
                    p = p + sgn * np.array([np.cos(th), np.sin(th)]) * 2.0
                    if not (-t <= p[0] < w + t and -t <= p[1] < h + t):
                        break
                    pts.append(p.copy())
                if len(pts) > 1:
                    cv2.polylines(canvas,
                                  [np.round(np.array(pts)).astype(np.int32)],
                                  False, 255, t, cv2.LINE_AA)
    out = canvas > 127
    out &= mask
    return out


def _score(render, ink, mask, w_meas):
    """Tolerance comes from the MEASURED stroke width, never the fitted
    one, and rendered ink fraction must match the reference's — otherwise
    'paint everything' games the miss/leak pair."""
    tol = max(int(round(w_meas / 2)), 1)
    r, p = coverage_metrics(render & mask, ink & mask, tol)
    fr = float((render & mask).sum()) / max(int(mask.sum()), 1)
    fi = float((ink & mask).sum()) / max(int(mask.sum()), 1)
    return {"miss": round(1 - r, 4), "leak": round(1 - p, 4),
            "ink_frac_err": round(abs(fr - fi), 4),
            "loss": round((1 - r) + (1 - p) + 2 * abs(fr - fi), 4)}


def fit_form(gray, ink, mask, w_px):
    """Estimate -> refine (theta, s, phi, w). Returns params + scores."""
    theta0, gx, gy = _theta_field_fit(gray, mask, w_px)
    ys, xs = np.nonzero(ink & mask)
    n = np.array([-np.sin(theta0), np.cos(theta0)])
    proj = xs * n[0] + ys * n[1]
    # spacing from the projection's autocorrelation peak
    hist, _ = np.histogram(proj, bins=int(proj.max() - proj.min() + 1))
    hist = hist - hist.mean()
    ac = np.correlate(hist, hist, "full")[len(hist) - 1:]
    lo = max(int(w_px * 1.2), 2)
    s = float(np.argmax(ac[lo:lo + int(w_px * 8)]) + lo) \
        if len(ac) > lo + 4 else w_px * 2.5
    # phase: densest bin of proj mod s
    ph_hist, edges = np.histogram(proj % s, bins=24)
    phi = float(edges[int(ph_hist.argmax())])

    best = dict(theta0=theta0, gx=gx, gy=gy, s=s, phi=phi, w=w_px)
    shape = gray.shape

    def loss_of(p):
        if p["s"] < p["w"] * 1.15:  # hatching, not paint: gaps must exist
            return 9e9
        r = render_hatch(shape, mask, p["theta0"], p["gx"], p["gy"],
                         p["s"], p["phi"], p["w"])
        return _score(r, ink, mask, w_px)["loss"]

    best_l = loss_of(best)
    for _round in range(2):
        for key, deltas in (("phi", np.linspace(-s / 2, s / 2, 9)),
                            ("theta0", np.deg2rad([-6, -3, -1.5, 1.5, 3, 6])),
                            ("s", s * np.array([-.18, -.09, .09, .18])),
                            ("w", w_px * np.array([-.3, -.15, .15, .3]))):
            for d in deltas:
                cand = dict(best)
                cand[key] = best[key] + float(d)
                if cand["s"] < 1.5 or cand["w"] < 0.8:
                    continue
                l_ = loss_of(cand)
                if l_ < best_l:
                    best, best_l = cand, l_
    render = render_hatch(shape, mask, best["theta0"], best["gx"],
                          best["gy"], best["s"], best["phi"], best["w"])
    sc = _score(render, ink, mask, w_px)
    params = {
        "theta_deg": round(float(np.degrees(best["theta0"])) % 180, 1),
        "fan_deg": [round(float(np.degrees(best["gx"])), 1),
                    round(float(np.degrees(best["gy"])), 1)],
        "s_over_w": round(best["s"] / best["w"], 2),
        "w_px": round(best["w"], 2), "s_px": round(best["s"], 2),
        "phi_px": round(best["phi"], 1)}
    return params, best, render, sc


def fit_patch(path):
    """Full pass: forms -> per-form fits -> composite render + scores."""
    bgr, gray, ink = load_patch(path)
    w_px, _sk = stroke_width_px(ink)
    lab, k = split_forms(gray, ink, w_px)
    comp = np.zeros_like(ink)
    forms = []
    raw = []
    for i in range(k):
        mask = lab == i
        params, rawp, render, sc = fit_form(gray, ink, mask, w_px)
        comp |= render
        forms.append({"frac": round(float(mask.mean()), 3),
                      "params": params, "score": sc})
        raw.append((rawp, mask))
    total = _score(comp, ink, ink | ~ink, w_px)
    return {"bgr": bgr, "gray": gray, "ink": ink, "labels": lab, "k": k,
            "w_px": w_px, "render": comp, "forms": forms, "raw": raw,
            "score": total}


def transfer(fit_src, path_dst):
    """Apply a fitted STYLE (s/w ratio, w) to another patch: re-estimate
    only content (theta field, phi). -> composite score on dst."""
    bgr, gray, ink = load_patch(path_dst)
    w_dst, _ = stroke_width_px(ink)
    style_ratio = np.mean([f["params"]["s_over_w"]
                           for f in fit_src["forms"]])
    w_use = float(np.mean([f["params"]["w_px"]
                           for f in fit_src["forms"]]))
    s_use = style_ratio * w_use
    lab, k = split_forms(gray, ink, w_dst)
    comp = np.zeros_like(ink)
    for i in range(k):
        mask = lab == i
        theta0, gx, gy = _theta_field_fit(gray, mask, w_dst)
        ys, xs = np.nonzero(ink & mask)
        n = np.array([-np.sin(theta0), np.cos(theta0)])
        proj = xs * n[0] + ys * n[1]
        ph_hist, edges = np.histogram(proj % s_use, bins=24)
        phi = float(edges[int(ph_hist.argmax())])
        comp |= render_hatch(gray.shape, mask, theta0, gx, gy,
                             s_use, phi, w_use)
    return _score(comp, ink, ink | ~ink, w_use)
