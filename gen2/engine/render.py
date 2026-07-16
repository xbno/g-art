"""render(genome, seed) — the single pure entry point.

Genome schema (v1):
{
  "name": "blue_mountain",
  "page": {"size": "11x17", "margin_mm": 20},
  "source": {"type": "photo", "path": "optional.jpg", "params": {...photo.DEFAULTS}},
  "humanize": {...humanize.DEFAULTS overrides, global},
  "bands": [                       # index = tone band, 0 = lightest
    {"module": "empty"},
    {"module": "flow_hatch", "pen": "blue03", "params": {...},
     "humanize": {...per-band overrides},
     "region": {...per-band mask_to_region overrides}},
    ...
  ],
  "edges": {"module": "contour_lines", "pen": "black03", "params": {...}},
  "zones": [                       # optional; replaces top-level bands/edges
    {"name": "sky", "select": {"type": "hsv"|"poly", ...},  # zones.py
     "bands": [...], "edges": null},
    {"name": "rest", "select": {"type": "rest"}, "bands": [...], ...}
  ]
}

Pure: same (genome, seed, photo bytes) → identical polylines, forever.
"""

import json
import logging

import cv2
import numpy as np

from .emphasis import emphasis_gate
from .humanize import humanize
from .inkmap import ink_map
from .modules import MODULES
from .photo import (compute_tone_bands, load_structure_ctx, mask_to_region,
                    region_to_mask)
from .plan import compile_plan, plan_outline
from .scene import (load_normals, load_scene, load_semantic, normals_field,
                    relight)

MODULES.setdefault("plan_outline", plan_outline)
from .tonemod import tone_gate
from .zones import zone_mask

log = logging.getLogger(__name__)

_CTX_CACHE: dict = {}


def _structure_ctx(genome: dict, photo_path: str | None) -> dict:
    src = genome.get("source", {})
    page_cfg = genome.get("page", {})
    path = photo_path or src.get("path")
    if not path:
        raise ValueError("no photo path in genome.source.path or argument")
    key = (path, json.dumps(src.get("params", {}), sort_keys=True),
           page_cfg.get("size", "11x17"), page_cfg.get("margin_mm", 20.0))
    if key not in _CTX_CACHE:
        sp = src.get("params", {})
        ctx = load_structure_ctx(
            path, page_size=page_cfg.get("size", "11x17"),
            margin_mm=page_cfg.get("margin_mm", 20.0), params=sp)
        ctx["scene"] = load_scene(path, ctx["gray"].shape)
        ctx["semantic"] = load_semantic(path, ctx["gray"].shape)
        normals = load_normals(path, ctx["gray"].shape)
        ctx["normals"] = normals
        if normals is not None:
            # normals-derived channels are deterministic per src.params,
            # which the cache key already includes
            theta, coh, var = normals_field(
                normals, ctx["page"].mm_per_px,
                smooth_mm=sp.get("normals_smooth_mm", 4.0),
                mode=sp.get("normals_stroke", "downslope"))
            ctx["normal_var"] = var
            if sp.get("orientation_source") == "normals":
                ctx["orientation"], ctx["coherence"] = theta, coh
            ts = sp.get("tone_source")
            if ts and ts.get("type") == "relight":
                shade = relight(normals, ts.get("azimuth_deg", 315.0),
                                ts.get("elevation_deg", 40.0))
                mix = float(ts.get("mix", 0.6))
                g = np.clip((1 - mix) * ctx["gray"] + mix * shade,
                            0.0, 1.0).astype(np.float32)
                ctx["gray"] = g
                ctx["tone_bands"] = compute_tone_bands(
                    g, sp.get("n_bands", 5), sp.get("band_gamma", 1.0),
                    sp.get("band_anchor"))
        _CTX_CACHE[key] = ctx
    return _CTX_CACHE[key]


def render(genome: dict, seed: int, photo_path: str | None = None):
    """→ (layers {pen: [Polyline]}, page). Pure in (genome, seed, photo)."""
    ctx = _structure_ctx(genome, photo_path)
    page = ctx["page"]
    layers: dict[str, list] = {}

    def run(entry: dict, mask, band_i: int):
        name = entry["module"]
        if name == "empty":
            return
        rp = {**ctx.get("region_params", {}), **entry.get("region", {})}
        region = mask_to_region(mask, page, **rp)
        if region.is_empty:
            return
        mask = region_to_mask(region, page, mask.shape)
        rng = np.random.default_rng([seed, band_i])
        lines = MODULES[name](mask, region, ctx, entry.get("params", {}), rng)
        tm = entry.get("tone_mod")
        if tm is not None:
            lines = tone_gate(lines, ctx, tm,
                              np.random.default_rng([seed, band_i, 7]))
        em = entry.get("emphasis")
        if em is not None:
            lines = emphasis_gate(lines, ctx, em,
                                  np.random.default_rng([seed, band_i, 11]))
        hp = {**genome.get("humanize", {}), **entry.get("humanize", {})}
        lines = humanize(lines, seed * 1000 + band_i, hp)
        log.info("band %s %s: %d lines", band_i, name, len(lines))
        layers.setdefault(entry.get("pen", "black03"), []).extend(lines)

    def run_stack(bands, edges, zmask, base_i, edges_i, base=None):
        if base:
            # zone-wide pass(es) over the WHOLE object mask: one committed
            # treatment per surface. A LIST stacks several passes (the
            # plan compiler's calibrated mark stacks).
            entries = base if isinstance(base, list) else [base]
            for j, entry in enumerate(entries):
                run(entry, zmask.copy(), base_i + 12 + j)
        for i, entry in enumerate(bands):
            if i >= len(ctx["tone_bands"]):
                break
            run(entry, ctx["tone_bands"][i] & zmask, base_i + i)
        if edges:
            run(edges, zmask.copy(), edges_i)

    def close_tone(tc: dict):
        """Salisbury's importance loop as a genome stage: measure the ink
        laid so far, top up where the source demands more darkness than
        the page carries, repeat. Output is CONSTRAINED by tone, not
        merely scored after the fact."""
        gamma = float(tc.get("gamma", 1.15))
        max_cov = float(tc.get("max_cov", 0.85))
        target = np.clip(1.0 - ctx["gray"], 0, 1) ** gamma * max_cov
        for pass_i in range(int(tc.get("passes", 1))):
            cov = ink_map(layers, page, ctx["gray"].shape,
                          blur_mm=float(tc.get("blur_mm", 1.4)))
            deficit = np.clip(target - cov, 0.0, 1.0)
            mask = deficit > float(tc.get("min_deficit", 0.1))
            if mask.mean() < 0.002:
                break
            rp = {**ctx.get("region_params", {}),
                  "close_mm": 1.5, "min_area_mm2": 15.0,
                  **tc.get("region", {})}
            reg = mask_to_region(mask, page, **rp)
            if reg.is_empty:
                break
            m = region_to_mask(reg, page, mask.shape)
            rng = np.random.default_rng([seed, 990 + pass_i])
            lines = MODULES[tc.get("module", "flow_hatch")](
                m, reg, ctx, tc.get("params", {}), rng)
            lines = tone_gate(
                lines, ctx, tc.get("tone_mod",
                                   {"low": 0.05, "high": 0.28,
                                    "seg_mm": 2.5}),
                np.random.default_rng([seed, 990 + pass_i, 7]),
                dark_map=deficit)
            hp = {**genome.get("humanize", {}), **tc.get("humanize", {})}
            lines = humanize(lines, seed * 1000 + 990 + pass_i, hp)
            log.info("tone_close pass %d: %d lines (deficit %.1f%%)",
                     pass_i, len(lines), 100 * mask.mean())
            layers.setdefault(tc.get("pen", "black03"), []).extend(lines)

    full = np.ones_like(ctx["edge_map"], dtype=bool)
    zones = genome.get("zones")
    if genome.get("plan"):
        zones = compile_plan(genome["plan"], ctx)
    if zones:
        # zones claim pixels in order; {"type": "rest"} takes the remainder
        claimed = np.zeros_like(full)
        for zi, zone in enumerate(zones):
            sel = zone.get("select", {"type": "rest"})
            zm = (~claimed if sel.get("type") == "rest"
                  else zone_mask(sel, ctx) & ~claimed)
            claimed |= zm
            kl = float(zone.get("keyline_mm", 0.0))
            if kl > 0:
                # engraver's white seam: marks pull back from the object
                # boundary by half the gap on each side, so adjacent zones
                # separate by ~keyline_mm of bare paper. The full zm was
                # already claimed, so the seam can't leak into "rest".
                r = max(int(round(kl / 2 / page.mm_per_px)), 1)
                ker = cv2.getStructuringElement(
                    cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
                zm = cv2.erode(zm.astype(np.uint8), ker).astype(bool)
            run_stack(zone.get("bands", []), zone.get("edges"), zm,
                      100 + zi * 20, 100 + zi * 20 + 19,
                      base=zone.get("base"))
    else:
        # band/edge indices (i, 99) predate zones — keep the RNG streams
        # of every already-stored genome byte-identical
        run_stack(genome.get("bands", []), genome.get("edges"), full, 0, 99)

    tc = genome.get("tone_close")
    if tc:
        close_tone(tc)

    return layers, page
