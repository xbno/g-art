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


def poly_grid(w_mm: float, h_mm: float, rng: np.random.Generator,
              cell_mm: float = 16.0, pad_mm: float = 10.0,
              jitter: float = 0.32, merge_p: float = 0.22):
    """Gapless polygonal tiling: a vertex lattice jittered with SHARED
    corners -> quads; some neighbors merged into bigger 5-7-gons.
    Returns (cells, neighbors): shapely polys + index-adjacency, so a
    caller can enforce the no-same-angle-for-neighbors invariant."""
    nx = max(int((w_mm - 2 * pad_mm) / cell_mm), 2)
    ny = max(int((h_mm - 2 * pad_mm) / cell_mm), 2)
    cw, ch = (w_mm - 2 * pad_mm) / nx, (h_mm - 2 * pad_mm) / ny
    vx = np.zeros((ny + 1, nx + 1, 2))
    for r in range(ny + 1):
        for c in range(nx + 1):
            jx = 0.0 if c in (0, nx) else rng.uniform(-jitter, jitter) * cw
            jy = 0.0 if r in (0, ny) else rng.uniform(-jitter, jitter) * ch
            vx[r, c] = (pad_mm + c * cw + jx, pad_mm + r * ch + jy)
    owner = {(r, c): (r, c) for r in range(ny) for c in range(nx)}
    for r in range(ny):
        for c in range(nx):
            if owner[(r, c)] != (r, c) or rng.uniform() > merge_p:
                continue
            opts = [(r, c + 1), (r + 1, c)]
            rng.shuffle(opts)
            for q in opts:
                if q in owner and owner[q] == q:
                    owner[q] = (r, c)
                    break
    groups = {}
    for cell, root in owner.items():
        groups.setdefault(root, []).append(cell)
    cells, members = [], []
    for root, cs in groups.items():
        quads = [Polygon([vx[r, c], vx[r, c + 1],
                          vx[r + 1, c + 1], vx[r + 1, c]])
                 for r, c in cs]
        cells.append(unary_union(quads))
        members.append(cs)
    idx_of = {}
    for i, cs in enumerate(members):
        for cell in cs:
            idx_of[cell] = i
    neighbors = [set() for _ in cells]
    for (r, c), i in idx_of.items():
        for q in ((r, c + 1), (r + 1, c), (r, c - 1), (r - 1, c)):
            j = idx_of.get(q)
            if j is not None and j != i:
                neighbors[i].add(j)
                neighbors[j].add(i)
    return cells, neighbors
