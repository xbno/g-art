"""100%-capability port of gen1/20250226/hatch_hatch.py (the plotted
2025-02 piece). Geometry ops live in engine/regions.py; this module
carries everything else the original could do:

- the verbatim hatching PATTERN TABLE: single committed angles, angle
  SETS ([0,90], [15,105], ...), and the four line styles — regular,
  exponential spacing, wavy, noisy — including the 'cooler ones' the
  original had commented out (capability, so ported)
- grid shape drop: 50px cells -> cell_mm, 40% skip, size multipliers
  [1x5, 2x4, 3x1], in-bounds rejection, triangle quarter-turns
- 5-material cycling (i % 5) — which means only the first five table
  entries ever fire in random mode, exactly like the original (and
  exactly why the plotted piece is five angles at one spacing)
- the fixed test scenario (create_fixed_shape_scenario, scaled to mm)
- composite bold outline at the original's 10:1 weight ratio — drawn as
  a double pass with the 0.5mm pen (plotter-honest bold)

Deliberate differences, nothing else: mm units, seeded np rng (original
used global `random`), shapely clipping via engine.geom, and irregular
4-7-gon polygons join the primitive set (regions.make_shape "poly").
Scale rule: original px -> mm at 0.38 (500px canvas ≈ 190mm sheet).
"""

import numpy as np

from .geom import clip_lines
from .regions import (composite_outline, effective_regions, make_shape,
                      material_union)

PX2MM = 0.38  # the original's pixel units -> sheet mm

# the original table, verbatim order, spacing scaled; the commented-out
# styled entries restored at the END so the live first-five behavior of
# random mode is unchanged
PATTERNS = [
    {"angles": [-45], "spacing": 3},
    {"angles": [45], "spacing": 3},
    {"angles": [-15], "spacing": 3},
    {"angles": [15], "spacing": 3},
    {"angles": [-30], "spacing": 3},
    {"angles": [30], "spacing": 3},
    {"angles": [-60], "spacing": 3},
    {"angles": [60], "spacing": 3},
    {"angles": [-75], "spacing": 3},
    {"angles": [75], "spacing": 3},
    {"angles": [0], "spacing": 3},
    {"angles": [90], "spacing": 3},
    {"angles": [0, 90], "spacing": 3},
    {"angles": [15, 105], "spacing": 3},
    {"angles": [30, 120], "spacing": 3},
    {"angles": [45, 135], "spacing": 6},
    {"angles": [0, 45], "spacing": 6},
    {"angles": [30, 75], "spacing": 6},
    {"angles": [15, 60], "spacing": 6},
    {"angles": [0, 30, 60, 90], "spacing": 20},
    {"angles": [15, 45, 75], "spacing": 18},
    {"angles": [45], "spacing": 4, "style": "regular"},
    {"angles": [0], "spacing": 2, "style": "exponential",
     "exp_factor": 1.1},
    {"angles": [30], "spacing": 6, "style": "wavy",
     "wave_amplitude": 5, "wave_frequency": 0.1, "num_points": 20},
    {"angles": [60], "spacing": 8, "style": "noisy",
     "noise_scale": 0.1, "noise_amplitude": 10, "num_points": 15},
]


def styled_lines(region, pattern: dict, rng: np.random.Generator,
                 min_len_mm: float = 0.8) -> list[np.ndarray]:
    """Port of generate_global_hatching_lines_enhanced for ONE region:
    all four styles, every angle in the set, clipped to the region."""
    if region.is_empty:
        return []
    style = pattern.get("style", "regular")
    spacing = pattern["spacing"] * PX2MM
    minx, miny, maxx, maxy = region.bounds
    pad = 5.0
    minx, miny, maxx, maxy = minx - pad, miny - pad, maxx + pad, maxy + pad
    diag = float(np.hypot(maxx - minx, maxy - miny))
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    out = []
    for angle in pattern["angles"]:
        th = np.deg2rad(angle)
        d = np.array([np.cos(th), np.sin(th)])
        n = np.array([-np.sin(th), np.cos(th)])
        if style == "exponential":
            offs, cur, tot = [0.0], spacing, spacing
            while tot < diag:
                offs.append(tot)
                cur *= pattern.get("exp_factor", 1.5)
                tot += cur
            offs = [-o for o in reversed(offs) if o > 0] + offs
        else:
            k = int(np.ceil(diag / spacing))
            offs = [i * spacing - diag / 2 for i in range(2 * k + 1)]
        for off in offs:
            base = np.array([cx, cy]) + n * off
            if style in ("regular", "exponential"):
                ln = np.array([base - d * diag / 2, base + d * diag / 2])
            else:
                npts = pattern.get("num_points", 10)
                t = np.linspace(-0.5, 0.5, npts + 1)
                pts = base[None] + d[None] * (t * diag)[:, None]
                if style == "wavy":
                    amp = pattern.get("wave_amplitude", 5) * PX2MM
                    freq = pattern.get("wave_frequency", 0.1)
                    wob = np.sin((t + .5) * np.pi * 2 * freq * npts) * amp
                else:  # noisy
                    amp = pattern.get("noise_amplitude", 10) * PX2MM \
                        * pattern.get("noise_scale", 0.1) * diag / 10
                    wob = rng.uniform(-1, 1, len(t)) * amp
                ln = pts - n[None] * wob[:, None]
            out.append(ln)
    return clip_lines(out, region, min_len_mm=min_len_mm)


def drop_shapes(w_mm: float, h_mm: float, rng: np.random.Generator,
                kinds=("circle", "square", "triangle"),
                cell_mm: float = 19.0, pad_mm: float = 12.0,
                skip: float = 0.40, n_materials: int = 5):
    """Port of _generate_random_shapes: jittered-free grid placement,
    size multipliers, in-bounds rejection. -> (polys, materials)."""
    mults = [1, 1, 1, 1, 1, 2, 2, 2, 2, 3]
    cols = int((w_mm - 2 * pad_mm) // cell_mm)
    rows = int((h_mm - 2 * pad_mm) // cell_mm)
    polys, mats = [], []
    for r in range(rows):
        for c in range(cols):
            if rng.uniform() < skip:
                continue
            x = pad_mm + (c + 0.5) * cell_mm
            y = pad_mm + (r + 0.5) * cell_mm
            kind = kinds[int(rng.integers(len(kinds)))]
            mult = mults[int(rng.integers(len(mults)))]
            size = cell_mm * 0.8 * mult
            half = size * (1.0 if kind == "triangle" else 0.5)
            if not (x - half >= pad_mm and x + half <= w_mm - pad_mm
                    and y - half >= pad_mm and y + half <= h_mm - pad_mm):
                continue
            rot = (int(rng.integers(0, 4)) * np.pi / 2
                   if kind == "triangle" else 0.0)
            polys.append(make_shape(kind, (x, y), size, rng,
                                    rotation=rot))
            mats.append(len(polys) % n_materials)
    return polys, mats


def fixed_scenario():
    """Port of create_fixed_shape_scenario (1200x1800 px -> mm), incl.
    the same-material overlaps that test continuous hatching."""
    s = PX2MM * 0.28  # original coords were on a larger canvas
    rng = np.random.default_rng(0)
    spec = [("square", 300, 300, 400), ("circle", 800, 300, 200),
            ("circle", 350, 550, 100), ("triangle", 800, 900, 350),
            ("square", 800, 1200, 300), ("square", 500, 500, 200),
            ("circle", 700, 700, 180)]
    polys = [make_shape(k, (x * s + 8, y * s + 8), sz * s, rng,
                        rotation=0.0) for k, x, y, sz in spec]
    return polys, [i % 5 for i in range(len(polys))]


def scene_layers(polys, mats, rng, patterns=None,
                 pattern_of=None) -> dict:
    """Effective regions -> unified material regions -> styled hatching
    -> composite bold outline (double-pass 0.5mm ≈ the original's 10:1).
    pattern_of: optional {material: pattern dict} override."""
    patterns = patterns or PATTERNS
    eff = effective_regions(polys)
    hatch = []
    for m, region in sorted(material_union(eff, mats).items()):
        pat = (pattern_of or {}).get(m, patterns[m % len(patterns)])
        hatch += styled_lines(region, pat, rng)
    outline = composite_outline(polys)
    bold = []
    for ring in outline:
        bold.append(ring)
        bold.append(ring + np.array([0.18, 0.12]))  # double pass = bold
    return {"black03": hatch, "black05": bold}
