"""Deterministic synthetic landscape photo for testing the M0 pipeline."""

from pathlib import Path

import numpy as np
from opensimplex import OpenSimplex
from PIL import Image


def make(path: str, w: int = 900, h: int = 1200, seed: int = 7) -> None:
    n = OpenSimplex(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    u, v = xx / w, yy / h

    # sky gradient, brighter near horizon
    img = 0.62 + 0.3 * v

    # cloud puffs (bright blobs in upper half)
    cloud = np.array([[n.noise2(x * 3.2, y * 5.5) for x in row]
                      for row, y in zip(u, v[:, 0])])
    img += np.clip(cloud - 0.25, 0, 1) * 0.5 * (v < 0.45)

    # mountain ridge: dark below a noisy ridgeline
    ridge = 0.42 + 0.13 * np.array(
        [n.noise2(x * 2.1, 0.0) for x in u[0]])
    mtn = v > ridge[None, :].repeat(h, 0)[np.arange(h)][:, :]
    shade = np.array([[n.noise2(x * 6.0, y * 6.0) for x in row]
                      for row, y in zip(u, v[:, 0])])
    img = np.where(mtn, 0.38 + 0.18 * shade, img)

    # foreground dark band with texture
    fg = v > 0.78
    img = np.where(fg, 0.16 + 0.14 * (shade + 1) / 2, img)

    # bright winding path through foreground
    px = 0.5 + 0.22 * np.sin(v * 9) + 0.08 * np.array(
        [n.noise2(0.0, y * 4.0) for y in v[:, 0]])[:, None]
    path_mask = fg & (np.abs(u - px) < 0.05 * (v - 0.7) / 0.3 + 0.01)
    img = np.where(path_mask, 0.85, img)

    img = np.clip(img, 0, 1)
    Image.fromarray((img * 255).astype(np.uint8), "L").save(path)


if __name__ == "__main__":
    out = Path(__file__).parent / "landscape.png"
    make(str(out))
    print(out)
