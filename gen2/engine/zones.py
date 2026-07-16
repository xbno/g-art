"""Semantic zones: genome-defined object masks (sky vs rock vs snow...).

Tone bands are luminance-only, so a blue sky and a shaded snow face of the
same brightness collapse into one band and get identical marks. Zones let
a genome treat them as different OBJECTS: each zone selects pixels — by
HSV/position rules, or by a polygon the mutator draws from looking at the
photo — and runs its own band stack. Zones claim pixels in order; a
{"type": "rest"} zone (handled in render.py) takes whatever remains.
"""

import cv2
import numpy as np


def _scene_region_match(r: dict, select: dict) -> bool:
    if "names" in select and (r.get("name") or "") not in select["names"]:
        return False
    for key in ("depth_rank", "tone_level"):
        if key in select:
            lo, hi = select[key]
            if not (lo <= r[key] <= hi):
                return False
    return True


def zone_mask(select: dict, ctx: dict) -> np.ndarray:
    """Zone selector -> HxW bool mask. Deterministic."""
    h, w = ctx["gray"].shape
    t = select.get("type")
    if t == "plan_mass":
        pm = ctx.get("plan_masses")
        if pm is None:
            raise ValueError("plan_mass zone outside a compiled plan")
        return pm == select["id"]
    if t == "plan_outline":
        need = ctx.get("plan_outline_mask")
        return (need.copy() if need is not None
                else np.zeros_like(ctx["gray"], dtype=bool))
    if t == "scene":
        # true objects from the frozen decomposition plan: pick regions by
        # explicit id, by hand-assigned name, or by depth_rank/tone_level
        # ranges ([lo, hi] inclusive)
        scene = ctx.get("scene")
        if scene is None:
            raise ValueError(
                "genome uses a scene zone but no .scene.npz plan exists "
                "next to the photo — run: python -m decompose <photo>")
        if "ids" in select:
            ids = list(select["ids"])
        elif {"names", "depth_rank", "tone_level"} & select.keys():
            ids = [r["id"] for r in scene["regions"]
                   if _scene_region_match(r, select)]
        else:
            raise ValueError("scene zone needs ids, names, depth_rank "
                             "or tone_level")
        return np.isin(scene["labels"], ids)
    if t == "poly":
        pts = (np.asarray(select["points"], dtype=float)
               * np.array([w, h])).astype(np.int32)
        m = np.zeros((h, w), np.uint8)
        cv2.fillPoly(m, [pts], 1)
        return m.astype(bool)
    if t == "hsv":
        hsv = ctx["hsv"]
        m = np.ones((h, w), dtype=bool)
        if "hue" in select:  # degrees 0-360, wraparound allowed (lo > hi)
            lo, hi = select["hue"]
            hue = hsv[..., 0]
            m &= ((hue >= lo) & (hue <= hi)) if lo <= hi \
                else ((hue >= lo) | (hue <= hi))
        for key, ch in (("sat", 1), ("val", 2)):
            if key in select:
                lo, hi = select[key]
                m &= (hsv[..., ch] >= lo) & (hsv[..., ch] <= hi)
        if "y" in select:  # image-height fractions, 0 = top
            lo, hi = select["y"]
            ys = np.linspace(0.0, 1.0, h)[:, None]
            m &= (ys >= lo) & (ys <= hi)
        if "coherence" in select:  # structure-tensor anisotropy 0-1:
            lo, hi = select["coherence"]  # high = strongly directional
            m &= (ctx["coherence"] >= lo) & (ctx["coherence"] <= hi)
        if "normal_var" in select:  # surface-normal roughness 0-1: high =
            # trees/rubble (curly texture), low = clean faces (ruled).
            # Needs a frozen <photo>.normals.npz (python -m decompose).
            nv = ctx.get("normal_var")
            if nv is None:
                raise ValueError("zone selects normal_var but no "
                                 ".normals.npz exists next to the photo")
            lo, hi = select["normal_var"]
            m &= (nv >= lo) & (nv <= hi)
        if "orient_deg" in select:  # local structure direction, mod 180
            lo, hi = select["orient_deg"]
            deg = np.degrees(np.mod(ctx["orientation"], np.pi))
            m &= ((deg >= lo) & (deg <= hi)) if lo <= hi \
                else ((deg >= lo) | (deg <= hi))
        page = ctx["page"]
        if "max_edge_density" in select:
            # texture cue: sky/haze is smooth, snow faces and foliage are
            # edge-dense — separates same-colored materials (blue sky vs
            # blue shaded snow)
            k = max(int(round(select.get("edge_window_mm", 8.0)
                              / page.mm_per_px)), 1)
            dens = cv2.boxFilter(ctx["edge_map"].astype(np.float32), -1,
                                 (k, k))
            m &= dens <= float(select["max_edge_density"])
        k = max(int(round(select.get("smooth_mm", 2.0) / page.mm_per_px)),
                1)
        ker = np.ones((k, k), np.uint8)
        mm = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, ker)
        mm = cv2.morphologyEx(mm, cv2.MORPH_OPEN, ker)
        if select.get("top_connected"):  # keep components touching the top
            n, lab = cv2.connectedComponents(mm)
            keep = set(np.unique(lab[0])) - {0}
            mm = np.isin(lab, list(keep)).astype(np.uint8) if keep \
                else np.zeros_like(mm)
        return mm.astype(bool)
    raise ValueError(f"unknown zone select type {t!r}")
