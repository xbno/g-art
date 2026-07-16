"""Reader for frozen scene plans (written offline by the decompose
package). A plan turns zones into true OBJECTS: a non-overlapping label
map plus per-region depth order and quantized tone. The plan file is part
of the source input, exactly like the photo bytes — model inference never
runs in the engine, so render() stays pure and reproducible.

labels  uint8 HxW region ids (1..N, no zeros)
depth   float32 HxW 0..1, higher = nearer
regions list of dicts: id, name, area_frac, depth_rank (0 = farthest),
        tone_level (0 = lightest), tone_mean, centroid, bbox
"""

import json
from pathlib import Path

import cv2
import numpy as np


def load_normals(photo_path: str, shape: tuple[int, int]) -> np.ndarray | None:
    """Frozen Marigold surface normals (<stem>.normals.npz) resized to the
    working resolution. HxWx3 float32 in [-1,1]; None if not decomposed."""
    p = Path(f"{Path(photo_path).with_suffix('')}.normals.npz")
    if not p.exists():
        return None
    n = np.load(p)["normals"].astype(np.float32)
    h, w = shape
    return cv2.resize(n, (w, h), interpolation=cv2.INTER_LINEAR)


def normals_field(n: np.ndarray, mm_per_px: float, smooth_mm: float = 4.0,
                  mode: str = "downslope"):
    """Normal map -> (orientation, coherence, variance).

    orientation: fall-line direction (or +90° for "contour" strokes) from
    the SMOOTHED in-plane normal component — the hand-painted direction
    field of the classic literature, derived instead of painted.
    coherence: in-plane magnitude — surfaces facing the camera have no
    preferred direction and read calm.
    variance: local deviation of raw normals from the smoothed field —
    high on trees/rubble (curly texture), low on clean faces (ruled)."""
    sig = max(smooth_mm / mm_per_px, 0.5)
    ns = cv2.GaussianBlur(n, (0, 0), sig)
    theta = np.arctan2(ns[..., 1], ns[..., 0])
    if mode == "contour":
        theta = theta + np.pi / 2
    coh = np.clip(np.hypot(ns[..., 0], ns[..., 1]) * 1.6, 0, 1)
    dev = np.linalg.norm(n - ns, axis=-1)
    var = cv2.GaussianBlur(dev, (0, 0), max(2.0 / mm_per_px, 0.5))
    var = np.clip(var / 0.35, 0, 1)
    return (theta.astype(np.float32), coh.astype(np.float32),
            var.astype(np.float32))


def relight(n: np.ndarray, azimuth_deg: float = 315.0,
            elevation_deg: float = 40.0) -> np.ndarray:
    """Lambertian shade 0..1 from the normal map and a genome-chosen sun.
    Tone from GEOMETRY, not photo exposure: the artist's 'shadow goes
    here' as a parameter. Azimuth is degrees CCW in the normal map's own
    x/y frame; sweep it — the useful range is found by eye, not compass."""
    az, el = np.deg2rad(azimuth_deg), np.deg2rad(elevation_deg)
    light = np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az),
                      np.sin(el)], np.float32)
    return np.clip(n @ light, 0.0, 1.0)


def load_semantic(photo_path: str, shape: tuple[int, int]) -> dict | None:
    """Frozen semantic labels (<stem>.semantic.npz) at working res."""
    p = Path(f"{Path(photo_path).with_suffix('')}.semantic.npz")
    if not p.exists():
        return None
    d = np.load(p, allow_pickle=True)
    h, w = shape
    labels = cv2.resize(d["labels"].astype(np.int16), (w, h),
                        interpolation=cv2.INTER_NEAREST)
    names = {int(k): v for k, v in json.loads(str(d["names"])).items()}
    return {"labels": labels, "names": names}


def load_scene(photo_path: str, shape: tuple[int, int]) -> dict | None:
    stem = Path(photo_path).with_suffix("")
    npz_p = Path(f"{stem}.scene.npz")
    json_p = Path(f"{stem}.scene.json")
    if not (npz_p.exists() and json_p.exists()):
        return None
    data = np.load(npz_p)
    meta = json.loads(json_p.read_text())
    h, w = shape
    labels = cv2.resize(data["labels"], (w, h),
                        interpolation=cv2.INTER_NEAREST)
    depth = cv2.resize(data["depth"].astype(np.float32), (w, h),
                       interpolation=cv2.INTER_LINEAR)
    return {"labels": labels, "depth": depth, "regions": meta["regions"]}
