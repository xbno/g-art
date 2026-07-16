"""Overlay panel so humans (and the mutator) can see the plan and cite
region ids when writing genomes."""

import cv2
import numpy as np


def plan_overlay(rgb: np.ndarray, labels: np.ndarray, depth: np.ndarray,
                 regions: list[dict]) -> np.ndarray:
    h, w = labels.shape
    rng = np.random.default_rng(7)
    colors = {r["id"]: rng.uniform(50, 255, 3) for r in regions}
    vis = np.zeros((h, w, 3), np.float32)
    for rid, c in colors.items():
        vis[labels == rid] = c
    blend = (0.4 * rgb.astype(np.float32) + 0.6 * vis).astype(np.uint8)

    # region boundaries + id/rank/tone tags at centroids
    edges = cv2.Canny(labels.astype(np.uint8), 0, 0) > 0
    blend[cv2.dilate(edges.astype(np.uint8),
                     np.ones((2, 2), np.uint8)).astype(bool)] = 0
    for r in regions:
        cx, cy = int(r["centroid"][0] * w), int(r["centroid"][1] * h)
        tag = f'{r["id"]}:d{r["depth_rank"]}t{r["tone_level"]}'
        for th, col in ((4, (255, 255, 255)), (1, (0, 0, 0))):
            cv2.putText(blend, tag, (cx - 20, cy), cv2.FONT_HERSHEY_SIMPLEX,
                        0.55, col, th, cv2.LINE_AA)

    d8 = (depth / (depth.max() + 1e-9) * 255).astype(np.uint8)
    panel = np.concatenate(
        [rgb, np.stack([d8] * 3, -1), blend], axis=1)
    return panel
