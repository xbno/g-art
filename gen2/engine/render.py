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

import numpy as np

from .humanize import humanize
from .modules import MODULES
from .photo import load_structure_ctx, mask_to_region, region_to_mask
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
        _CTX_CACHE[key] = load_structure_ctx(
            path, page_size=page_cfg.get("size", "11x17"),
            margin_mm=page_cfg.get("margin_mm", 20.0),
            params=src.get("params", {}))
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
        hp = {**genome.get("humanize", {}), **entry.get("humanize", {})}
        lines = humanize(lines, seed * 1000 + band_i, hp)
        log.info("band %s %s: %d lines", band_i, name, len(lines))
        layers.setdefault(entry.get("pen", "black03"), []).extend(lines)

    def run_stack(bands, edges, zmask, base_i, edges_i):
        for i, entry in enumerate(bands):
            if i >= len(ctx["tone_bands"]):
                break
            run(entry, ctx["tone_bands"][i] & zmask, base_i + i)
        if edges:
            run(edges, zmask.copy(), edges_i)

    full = np.ones_like(ctx["edge_map"], dtype=bool)
    zones = genome.get("zones")
    if zones:
        # zones claim pixels in order; {"type": "rest"} takes the remainder
        claimed = np.zeros_like(full)
        for zi, zone in enumerate(zones):
            sel = zone.get("select", {"type": "rest"})
            zm = (~claimed if sel.get("type") == "rest"
                  else zone_mask(sel, ctx) & ~claimed)
            claimed |= zm
            run_stack(zone.get("bands", []), zone.get("edges"), zm,
                      100 + zi * 20, 100 + zi * 20 + 19)
    else:
        # band/edge indices (i, 99) predate zones — keep the RNG streams
        # of every already-stored genome byte-identical
        run_stack(genome.get("bands", []), genome.get("edges"), full, 0, 99)

    return layers, page
