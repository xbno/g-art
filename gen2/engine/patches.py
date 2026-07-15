"""Facet segmentation for classic pen-and-ink hatching.

Splits a band mask into orientation-coherent patches — each surface plane
(rock face, roof pitch, foliage clump) becomes its own patch that will be
hatched straight at its own angle. Deterministic: no RNG anywhere here.
"""

import cv2
import numpy as np


def segment_facets(mask: np.ndarray, ctx: dict, sector_deg: float = 30.0,
                   smooth_mm: float = 2.5, min_coherence: float = 0.06
                   ) -> list[tuple[np.ndarray, float, bool]]:
    """-> [(facet_mask, mean_orientation_rad, is_incoherent), ...]

    Quantizes the orientation field (mod pi) into sectors, majority-smooths
    the label map so facets are spatially coherent, and returns one facet
    per sector present in the mask. Pixels with coherence below
    min_coherence land in a separate "incoherent" facet (flat areas — sky,
    haze — where the caller applies a fallback angle).
    """
    theta = ctx["orientation"]
    coh = ctx["coherence"]
    page = ctx["page"]
    n_sec = max(int(round(180.0 / sector_deg)), 1)

    t = np.mod(theta, np.pi)
    sec = (np.floor(t / np.pi * n_sec).astype(np.int32)) % n_sec
    sec[coh < min_coherence] = n_sec  # incoherent bucket

    # majority vote over a window kills per-pixel sector flicker so the
    # label map forms drawable planes instead of confetti
    k = max(int(round(smooth_mm / page.mm_per_px)), 1) * 2 + 1
    votes = [cv2.boxFilter((sec == i).astype(np.float32), -1, (k, k))
             for i in range(n_sec + 1)]
    sec = np.stack(votes).argmax(0)

    out = []
    for i in range(n_sec + 1):
        m = mask & (sec == i)
        if not m.any():
            continue
        tt = theta[m]
        ww = np.maximum(coh[m], 1e-3)
        ang = 0.5 * np.arctan2(float((ww * np.sin(2 * tt)).sum()),
                               float((ww * np.cos(2 * tt)).sum()))
        out.append((m, float(ang), i == n_sec))
    return out
