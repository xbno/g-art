"""Post-process raw masks + depth into a scene plan: a non-overlapping
label map plus per-region stats. Pure numpy/cv2 — no torch here."""

import json
import logging
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)

DEFAULTS = {
    "min_frac": 0.004,    # regions smaller than this fraction get merged away
    "tone_edges": (0.25, 0.5, 0.75),  # darkness -> tone_level thresholds
    "sliver_open_frac": 0.02,   # opening kernel as fraction of image width
    "sliver_keep": 0.4,   # region must survive opening at >= this ratio
    "split_frac": 0.35,   # regions bigger than this get split by depth
    "split_bins": 3,      # ...into up to this many depth bands
}


def build_label_map(masks: list[np.ndarray], shape: tuple[int, int],
                    min_frac: float) -> np.ndarray:
    """Overlapping masks -> uint8 label map, 0 = unclaimed (filled later).

    Painted big-first so smaller masks overwrite: SAM nests detail masks
    (rock bands inside a face) inside big ones, and the finer object is
    the one the artist would draw."""
    h, w = shape
    area_min = min_frac * h * w
    keep = [m for m in masks if m.sum() >= area_min]
    keep.sort(key=lambda m: -int(m.sum()))
    labels = np.zeros((h, w), np.uint8)
    for i, m in enumerate(keep[:254], start=1):
        labels[m] = i
    return labels


def fill_unclaimed(labels: np.ndarray) -> np.ndarray:
    """Assign every 0 pixel the label of its nearest claimed pixel."""
    if not (labels == 0).any():
        return labels
    if not (labels != 0).any():
        raise ValueError("no regions survived — lower min_frac")
    unknown = (labels == 0).astype(np.uint8)
    _, idx = cv2.distanceTransformWithLabels(
        unknown, cv2.DIST_L2, 3, labelType=cv2.DIST_LABEL_PIXEL)
    # idx points at the nearest zero pixel of `unknown` = nearest claimed px
    lut = np.zeros(idx.max() + 1, labels.dtype)
    claimed = labels != 0
    lut[idx[claimed]] = labels[claimed]
    out = labels.copy()
    out[~claimed] = lut[idx[~claimed]]
    return out


def merge_small(labels: np.ndarray, min_frac: float) -> np.ndarray:
    """Fold regions below min_frac into the neighbor they touch most."""
    h, w = labels.shape
    area_min = min_frac * h * w
    for _ in range(8):
        ids, counts = np.unique(labels, return_counts=True)
        small = ids[counts < area_min]
        if len(small) == 0:
            break
        for rid in small:
            m = (labels == rid).astype(np.uint8)
            ring = cv2.dilate(m, np.ones((3, 3), np.uint8)).astype(bool) \
                & (labels != rid)
            if not ring.any():
                continue
            nb, nc = np.unique(labels[ring], return_counts=True)
            labels[m.astype(bool)] = nb[nc.argmax()]
    return labels


def merge_slivers(labels: np.ndarray, open_frac: float,
                  keep_ratio: float) -> np.ndarray:
    """Fold ribbon/sliver regions (overlap paint-order artifacts) into the
    neighbor they touch most. A real object survives morphological opening;
    a sliver mostly vanishes."""
    h, w = labels.shape
    k = max(int(round(open_frac * w)), 3)
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    for rid in np.unique(labels):
        m = (labels == rid).astype(np.uint8)
        area = int(m.sum())
        if area == 0:
            continue
        kept = int(cv2.morphologyEx(m, cv2.MORPH_OPEN, ker).sum())
        if kept / area >= keep_ratio:
            continue
        ring = cv2.dilate(m, np.ones((3, 3), np.uint8)).astype(bool) \
            & (labels != rid)
        if not ring.any():
            continue
        nb, nc = np.unique(labels[ring], return_counts=True)
        labels[m.astype(bool)] = nb[nc.argmax()]
    return labels


def split_by_depth(labels: np.ndarray, depth: np.ndarray, split_frac: float,
                   split_bins: int, min_frac: float) -> np.ndarray:
    """Split oversized regions into depth bands. SAM often sees a whole
    massif as ONE object, but the artist treats far face / mid slope /
    near forest differently — depth is the cue that separates them."""
    h, w = labels.shape
    for rid in np.unique(labels):
        m = labels == rid
        if m.sum() < split_frac * h * w:
            continue
        d = depth[m]
        if float(d.max() - d.min()) < 0.15:  # genuinely flat in depth (sky)
            continue
        edges = np.quantile(d, np.linspace(0, 1, split_bins + 1))[1:-1]
        sub = np.digitize(depth, edges)  # 0..split_bins-1, nearest = high
        nxt = int(labels.max())
        piece = labels.copy()
        for b in range(1, split_bins):
            band = m & (sub == b)
            if band.sum() >= min_frac * h * w:
                piece[band] = nxt + b
        # depth quantiles can interleave with texture; keep each band only
        # if it forms a coherent mass, then let the sliver/merge passes
        # clean the rest
        piece = merge_slivers(piece, 0.02, 0.3)
        labels = piece
    return labels


def compact_labels(labels: np.ndarray) -> np.ndarray:
    ids = np.unique(labels)
    lut = np.zeros(ids.max() + 1, labels.dtype)
    lut[ids] = np.arange(1, len(ids) + 1)
    return lut[labels]


def region_stats(labels: np.ndarray, depth: np.ndarray,
                 gray: np.ndarray, tone_edges) -> list[dict]:
    h, w = labels.shape
    regions = []
    for rid in np.unique(labels):
        m = labels == rid
        area = int(m.sum())
        ys, xs = np.nonzero(m)
        darkness = float(1.0 - gray[m].mean())
        regions.append({
            "id": int(rid),
            "name": None,
            "area_frac": round(area / (h * w), 5),
            "depth_mean": round(float(depth[m].mean()), 4),
            "tone_mean": round(float(gray[m].mean()), 4),
            "tone_level": int(np.digitize(darkness, tone_edges)),
            "centroid": [round(float(xs.mean() / w), 4),
                         round(float(ys.mean() / h), 4)],
            "bbox": [round(float(xs.min() / w), 4),
                     round(float(ys.min() / h), 4),
                     round(float(xs.max() / w), 4),
                     round(float(ys.max() / h), 4)],
        })
    # rank 0 = farthest = drawn first (background-to-foreground)
    for rank, r in enumerate(sorted(regions, key=lambda r: r["depth_mean"])):
        r["depth_rank"] = rank
    return sorted(regions, key=lambda r: r["id"])


def build_plan(rgb: np.ndarray, masks: list[np.ndarray],
               depth: np.ndarray, params: dict | None = None):
    p = {**DEFAULTS, **(params or {})}
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    labels = build_label_map(masks, gray.shape, p["min_frac"])
    labels = fill_unclaimed(labels)
    labels = merge_slivers(labels, p["sliver_open_frac"], p["sliver_keep"])
    labels = split_by_depth(labels, depth, p["split_frac"],
                            p["split_bins"], p["min_frac"])
    labels = merge_small(labels, p["min_frac"])
    labels = compact_labels(labels)
    regions = region_stats(labels, depth, gray, p["tone_edges"])
    log.info("plan: %d regions", len(regions))
    return labels, regions


def save_plan(stem: Path, labels: np.ndarray, depth: np.ndarray,
              regions: list[dict], source: str, generator: str):
    np.savez_compressed(f"{stem}.scene.npz", labels=labels,
                        depth=depth.astype(np.float16))
    meta = {"source": source, "generator": generator,
            "shape": list(labels.shape), "regions": regions}
    Path(f"{stem}.scene.json").write_text(json.dumps(meta, indent=1))
