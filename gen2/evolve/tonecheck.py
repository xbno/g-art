"""Tone fidelity check: is every dark part of the SOURCE as dark in the
RENDER? Emphasis/indication passes trade tone accuracy for hierarchy —
this makes the trade visible instead of silent.

Both images are content-cropped, downsampled to a coarse grid, and
normalized to their own 5-95 percentile darkness range; the signed diff
(source_dark - render_dark) is scored and painted: RED = render too
light where the source is dark (the failure the eye catches), BLUE =
render darker than the source.

    .venv/bin/python gen2/evolve/tonecheck.py <render.png> <photo> <out.png>
"""

import sys
from pathlib import Path

import cv2
import numpy as np


def _dark_grid(png: str, grid_w: int = 36) -> np.ndarray:
    g = cv2.imread(str(png), cv2.IMREAD_GRAYSCALE).astype(np.float32)
    paper = max(float(np.percentile(g, 97)), 1.0)
    dark = np.clip((paper - g) / paper, 0.0, 1.0)
    ys, xs = np.nonzero(dark > 0.1)
    if len(xs):
        dark = dark[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    gh = max(int(round(grid_w * dark.shape[0] / dark.shape[1])), 8)
    d = cv2.resize(dark, (grid_w, gh), interpolation=cv2.INTER_AREA)
    lo, hi = np.percentile(d, 5), np.percentile(d, 95)
    return np.clip((d - lo) / max(hi - lo, 1e-6), 0.0, 1.0)


def tone_fidelity(render_png: str, photo: str, grid_w: int = 36):
    """-> (score 0-1, signed diff grid). diff > 0 = render too light."""
    src = _dark_grid(photo, grid_w)
    ren = _dark_grid(render_png, grid_w)
    ren = cv2.resize(ren, (src.shape[1], src.shape[0]))
    diff = src - ren
    # the eye forgives extra ink; it catches missing darks — weight the
    # too-light direction, and only where the source is actually dark
    miss = np.clip(diff, 0, None) * (src > 0.45)
    score = float(1.0 - miss.mean() * 4.0)
    return max(score, 0.0), diff


def heatmap(render_png: str, photo: str, out_png: str,
            grid_w: int = 36) -> float:
    score, diff = tone_fidelity(render_png, photo, grid_w)
    ren = cv2.imread(str(render_png))
    h, w = ren.shape[:2]
    d = cv2.resize(diff, (w, h), interpolation=cv2.INTER_LINEAR)
    overlay = ren.astype(np.float32)
    too_light = np.clip(d, 0, 1)[..., None] * np.array([0, 0, 255])
    too_dark = np.clip(-d, 0, 1)[..., None] * np.array([255, 80, 0])
    overlay = np.clip(overlay * 0.55 + too_light * 1.6 + too_dark * 1.2,
                      0, 255).astype(np.uint8)
    cv2.putText(overlay, f"tone fidelity {score:.2f}", (14, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 6,
                cv2.LINE_AA)
    cv2.putText(overlay, f"tone fidelity {score:.2f}", (14, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 200), 2, cv2.LINE_AA)
    cv2.imwrite(str(out_png), overlay)
    return score


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    s = heatmap(sys.argv[1], sys.argv[2], sys.argv[3])
    print(f"{s:.3f} {sys.argv[3]}")
