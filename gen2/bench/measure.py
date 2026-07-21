"""Rung 1 — measurement. Everything we can read off a reference ink crop
without assuming our vocabulary. All physical scale derives from the
measured stroke width and an assumed pen (PEN_MM): the pen is the ruler.
"""

import cv2
import numpy as np
from scipy import ndimage
from skimage.morphology import skeletonize

PEN_MM = 0.35  # assumed nib of the reference artist


def load_crop(path):
    """-> (bgr, gray 0..1, ink bool). Ink = anything that isn't paper:
    darker than paper OR saturated (a pale-blue pen stroke is barely
    darker than cream paper but is strongly more colorful)."""
    bgr = cv2.imread(str(path))
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    sat = hsv[..., 1].astype(np.float32) / 255
    # paper-relative: estimate local background with a large median, call
    # ink whatever is locally darker OR locally more saturated — robust
    # to cream paper, pale pens, and low-res anti-aliased scans
    k = max(int(min(gray.shape) * 0.08) | 1, 15)
    bg_g = cv2.medianBlur((gray * 255).astype(np.uint8), k) / 255.0
    bg_s = cv2.medianBlur((sat * 255).astype(np.uint8), k) / 255.0
    ink = ((bg_g - gray) > 0.10) | ((sat - bg_s) > 0.10)
    ink = cv2.morphologyEx(ink.astype(np.uint8), cv2.MORPH_OPEN,
                           np.ones((2, 2), np.uint8)) > 0
    return bgr, gray * (1 - sat * 0.7), ink


def stroke_width_px(ink):
    """Median ink thickness via distance transform sampled on the
    skeleton. -> (width_px, skeleton bool)."""
    dt = cv2.distanceTransform(ink.astype(np.uint8), cv2.DIST_L2, 3)
    sk = skeletonize(ink)
    vals = dt[sk]
    w = 2.0 * float(np.median(vals)) if vals.size else 2.0
    return max(w, 1.0), sk


def orientation_field(gray, sigma_px=6.0):
    """Structure tensor -> per-pixel STROKE direction (minor eigenvector)
    and coherence 0..1."""
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1)
    jxx = cv2.GaussianBlur(gx * gx, (0, 0), sigma_px)
    jyy = cv2.GaussianBlur(gy * gy, (0, 0), sigma_px)
    jxy = cv2.GaussianBlur(gx * gy, (0, 0), sigma_px)
    theta = 0.5 * np.arctan2(2 * jxy, jxx - jyy) + np.pi / 2
    coh = np.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2) / (jxx + jyy + 1e-9)
    return theta.astype(np.float32), np.clip(coh, 0, 1).astype(np.float32)


_OFFS = [(-1, -1), (-1, 0), (-1, 1), (0, -1),
         (0, 1), (1, -1), (1, 0), (1, 1)]


def skeleton_segments(sk, min_len=4):
    """Split the skeleton at junctions -> ordered pixel paths.
    Crossings SPLIT strokes, so the count is an upper bound on the
    artist's true stroke count (report it as 'segments')."""
    nb = ndimage.convolve(sk.astype(np.uint8), np.ones((3, 3), np.uint8),
                          mode="constant") - 1
    junction = sk & (nb >= 3)
    body = sk & ~junction
    lab, n = ndimage.label(body, structure=np.ones((3, 3)))
    paths = []
    for sl, idx in zip(ndimage.find_objects(lab), range(1, n + 1)):
        ys, xs = np.nonzero(lab[sl] == idx)
        if len(ys) < min_len:
            continue
        pix = set(zip(ys.tolist(), xs.tolist()))
        deg = {p: sum(((p[0] + dy, p[1] + dx) in pix) for dy, dx in _OFFS)
               for p in pix}
        start = min(pix, key=lambda p: (deg[p], p))
        path, seen, cur = [start], {start}, start
        while True:
            nxt = [q for dy, dx in _OFFS
                   if (q := (cur[0] + dy, cur[1] + dx)) in pix
                   and q not in seen]
            if not nxt:
                break
            cur = min(nxt, key=lambda q: (abs(q[0] - cur[0])
                                          + abs(q[1] - cur[1])))
            path.append(cur)
            seen.add(cur)
        y0, x0 = sl[0].start, sl[1].start
        paths.append(np.array([(x + x0, y + y0) for y, x in path], float))
    return paths


def measure(path):
    """Full measurement pass -> dict of arrays + stats."""
    bgr, gray, ink = load_crop(path)
    width_px, sk = stroke_width_px(ink)
    px_per_mm = width_px / PEN_MM
    theta, coh = orientation_field(gray, sigma_px=max(width_px * 2.5, 4))
    segs = skeleton_segments(sk)
    seg_len_mm = [len(s) / px_per_mm for s in segs]
    return {
        "bgr": bgr, "gray": gray, "ink": ink, "skeleton": sk,
        "theta": theta, "coh": coh, "segments": segs,
        "width_px": width_px, "px_per_mm": px_per_mm,
        "stats": {
            "ink_frac": round(float(ink.mean()), 4),
            "width_px": round(width_px, 2),
            "px_per_mm": round(px_per_mm, 2),
            "size_mm": [round(ink.shape[1] / px_per_mm, 1),
                        round(ink.shape[0] / px_per_mm, 1)],
            "segments": len(segs),
            "seg_len_mm_med": round(float(np.median(seg_len_mm)), 2)
            if seg_len_mm else 0.0,
        },
    }


def coverage_metrics(recon_ink, ref_ink, tol_px):
    """The user's criterion made numeric: black covered (recall), white
    respected (precision), both at pen-width tolerance."""
    k = np.ones((2 * tol_px + 1, 2 * tol_px + 1), np.uint8)
    rd = cv2.dilate(recon_ink.astype(np.uint8), k) > 0
    fd = cv2.dilate(ref_ink.astype(np.uint8), k) > 0
    recall = float((ref_ink & rd).sum() / max(ref_ink.sum(), 1))
    precision = float((recon_ink & fd).sum() / max(recon_ink.sum(), 1))
    return round(recall, 4), round(precision, 4)
