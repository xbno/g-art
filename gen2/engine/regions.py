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
import shapely
from shapely.geometry import Polygon, box
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


def object_scene(objs: list[Polygon], auras: list[float]):
    """OBJECT-level occlusion with separation treatments (the reference
    move: the BACKGROUND yields — a near object projects a white 'aura'
    sliver into everything behind it, while its own fill runs clean to
    its silhouette; the comic outline lives on the same visible edge).

    objs far -> near; auras[i] = white clearance object i casts onto
    objects behind it (0 = butt/overlap directly).
    -> list of (fill_region, visible_region): fill for hatching (with
    aura carved), visible for outlining (true silhouette)."""
    n = len(objs)
    fills, visibles = [None] * n, [None] * n
    cover = None
    cover_buf = None
    for i in range(n - 1, -1, -1):
        visibles[i] = objs[i] if cover is None \
            else objs[i].difference(cover)
        fills[i] = objs[i] if cover_buf is None \
            else objs[i].difference(cover_buf)
        b = objs[i].buffer(auras[i]) if auras[i] > 0 else objs[i]
        cover = objs[i] if cover is None else unary_union([cover, objs[i]])
        cover_buf = b if cover_buf is None else unary_union([cover_buf, b])
    return list(zip(fills, visibles))


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


def aniso_mesh(w_mm: float, h_mm: float, rng: np.random.Generator,
               n_parents: int = 90, pad_mm: float = 8.0):
    """Anisotropic patch field — the reference-artist cell geometry:
    patches ELONGATED ALONG their own stroke direction, directions
    drifting coherently across the sheet (smooth fBm field) but
    committed per patch. Built as Voronoi of collinear seed CLUSTERS
    (sub-cells unioned per parent = stretched cells).
    -> (cells, neighbors, theta_per_cell)."""
    from scipy.ndimage import gaussian_filter

    gh, gw = 20, 28
    ca = gaussian_filter(rng.standard_normal((gh, gw)), 2.5)
    cb = gaussian_filter(rng.standard_normal((gh, gw)), 2.5)

    def field(x, y):
        gx = np.clip(x / w_mm * (gw - 1), 0, gw - 1.001)
        gy = np.clip(y / h_mm * (gh - 1), 0, gh - 1.001)
        x0, y0 = int(gx), int(gy)
        fx, fy = gx - x0, gy - y0
        def bl(m):
            return (m[y0, x0] * (1 - fx) * (1 - fy)
                    + m[y0, x0 + 1] * fx * (1 - fy)
                    + m[y0 + 1, x0] * (1 - fx) * fy
                    + m[y0 + 1, x0 + 1] * fx * fy)
        return 0.5 * np.arctan2(bl(cb), bl(ca))

    parents = np.stack([rng.uniform(pad_mm, w_mm - pad_mm, n_parents),
                        rng.uniform(pad_mm, h_mm - pad_mm, n_parents)], 1)
    thetas = np.array([field(*p) for p in parents])
    subs, owner = [], []
    for i, p in enumerate(parents):
        spread = float(rng.choice([0, 4, 8, 13, 19],
                                  p=[.18, .25, .27, .2, .1]))
        k = 1 + int(spread / 4)
        u = np.array([np.cos(thetas[i]), np.sin(thetas[i])])
        ts = np.linspace(-0.5, 0.5, k) if k > 1 else [0.0]
        for t in ts:
            subs.append(p + u * spread * t)
            owner.append(i)
    sub_cells, sub_nb = voronoi_mesh(w_mm, h_mm, np.array(subs), pad_mm)
    cells = [None] * n_parents
    for j, c in enumerate(sub_cells):
        if c is None:
            continue
        i = owner[j]
        cells[i] = c if cells[i] is None else unary_union([cells[i], c])
    neighbors = [set() for _ in range(n_parents)]
    for j, nbs in enumerate(sub_nb):
        for q in nbs:
            a, b = owner[j], owner[q]
            if a != b and cells[a] is not None and cells[b] is not None:
                neighbors[a].add(b)
                neighbors[b].add(a)
    return cells, neighbors, thetas


def voronoi_mesh(w_mm: float, h_mm: float, seeds: np.ndarray,
                 pad_mm: float = 8.0):
    """Voronoi cells from arbitrary seed points (mm), clipped to the
    page — the MESHIFY primitive: seed density carries image structure,
    so cells are small where detail lives, big where it doesn't.
    Mirror trick makes every cell finite. -> (cells, neighbors)."""
    from scipy.spatial import Voronoi

    n = len(seeds)
    rect = box(pad_mm, pad_mm, w_mm - pad_mm, h_mm - pad_mm)
    mirrored = [seeds]
    for axis, lo, hi in ((0, pad_mm, w_mm - pad_mm),
                         (1, pad_mm, h_mm - pad_mm)):
        for bound in (lo, hi):
            m = seeds.copy()
            m[:, axis] = 2 * bound - m[:, axis]
            mirrored.append(m)
    vor = Voronoi(np.concatenate(mirrored))
    cells = []
    for i in range(n):
        verts = vor.regions[vor.point_region[i]]
        if -1 in verts or not verts:
            cells.append(None)
            continue
        p = Polygon(vor.vertices[verts]).intersection(rect)
        cells.append(p if not p.is_empty else None)
    neighbors = [set() for _ in range(n)]
    for a, b in vor.ridge_points:
        if a < n and b < n and cells[a] is not None \
                and cells[b] is not None:
            neighbors[a].add(int(b))
            neighbors[b].add(int(a))
    return cells, neighbors
