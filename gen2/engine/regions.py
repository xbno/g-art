"""L2 REGION machinery — the gen1 hatch_hatch architecture, reborn.

The 2025-02 piece (gen1/20250226/hatch_hatch.py, plotted and verified):
overlapping primitives with z-order occlusion, same-material regions
unioned and hatched as ONE continuous field, one committed hatch angle
per material, composite silhouette outline. Those four ideas are the
region layer of the vocabulary ladder (docs/vocabulary.md L2); this
module is their clean, pure, seeded implementation — plus the primitive
the reference rockfaces demand: irregular 4-7-sided polygons.

All geometry in mm, shapely. Pure: same (params, rng) -> same shapes.
"""

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union


def make_shape(kind: str, center, size_mm: float,
               rng: np.random.Generator, rotation: float | None = None,
               n_sides: int | None = None,
               irregularity: float = 0.35) -> Polygon:
    """circle | square | triangle | poly. `poly` is the rockface facet:
    4-7 sides, convex-ish, radii and angles jittered."""
    cx, cy = center
    r = size_mm / 2
    rot = rng.uniform(0, 2 * np.pi) if rotation is None else rotation
    if kind == "circle":
        a = np.linspace(0, 2 * np.pi, 48, endpoint=False)
        pts = np.stack([cx + r * np.cos(a), cy + r * np.sin(a)], 1)
    elif kind == "square":
        a = np.array([0, .5, 1, 1.5]) * np.pi + np.pi / 4 + rot
        rr = r * np.sqrt(2)
        pts = np.stack([cx + rr * np.cos(a), cy + rr * np.sin(a)], 1)
    elif kind == "triangle":
        a = np.array([0, 2 / 3, 4 / 3]) * np.pi + rot
        pts = np.stack([cx + r * 1.2 * np.cos(a),
                        cy + r * 1.2 * np.sin(a)], 1)
    elif kind == "poly":
        n = int(n_sides or rng.integers(4, 8))
        a = np.sort(rng.uniform(0, 2 * np.pi, n))
        # reject near-duplicate vertex angles (slivers)
        while np.any(np.diff(np.concatenate([a, [a[0] + 2 * np.pi]]))
                     < 0.35):
            a = np.sort(rng.uniform(0, 2 * np.pi, n))
        rr = r * (1 + rng.uniform(-irregularity, irregularity * 0.7, n))
        pts = np.stack([cx + rr * np.cos(a + rot),
                        cy + rr * np.sin(a + rot)], 1)
    else:
        raise ValueError(kind)
    p = Polygon(pts)
    return p if p.is_valid else p.buffer(0)


def effective_regions(polys: list[Polygon]) -> list:
    """gen1 calculate_effective_regions: z = list order (later = nearer);
    each shape minus the union of everything above it. Entries may be
    empty (fully covered)."""
    out = [None] * len(polys)
    cover = None
    for i in range(len(polys) - 1, -1, -1):
        p = polys[i]
        out[i] = p if cover is None else p.difference(cover)
        cover = p if cover is None else unary_union([cover, p])
    return out


def material_union(regions: list, materials: list[int]) -> dict:
    """gen1 calculate_unified_color_regions: same-material effective
    regions merge -> ONE region per material, hatched as one field."""
    by = {}
    for reg, m in zip(regions, materials):
        if reg is not None and not reg.is_empty:
            by.setdefault(m, []).append(reg)
    return {m: unary_union(rs) for m, rs in by.items()}


def _rings(geom):
    polys = getattr(geom, "geoms", [geom])
    out = []
    for p in polys:
        if p.is_empty or not isinstance(p, Polygon):
            continue
        out.append(np.asarray(p.exterior.coords))
        out += [np.asarray(i.coords) for i in p.interiors]
    return out


def composite_outline(polys: list[Polygon]) -> list[np.ndarray]:
    """gen1 find_composite_outline: the UNION silhouette (+ holes),
    never per-shape edges."""
    return _rings(unary_union(polys))


def region_outline(region) -> list[np.ndarray]:
    """Boundary of one effective region — the facet-mode outline."""
    return _rings(region)
