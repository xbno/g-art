"""Orientation-field sampling and streamline tracing — the core of flow_hatch.

All tracing happens in page mm. The orientation field is sampled bilinearly
in doubled-angle space (cos2θ/sin2θ) so 0/180° wraparound never cancels.
Line spacing is enforced with a Jobard–Lehrer style occupancy grid.
"""

import numpy as np


class FieldSampler:
    def __init__(self, ctx):
        th = ctx["orientation"].astype(np.float64)
        self.c2 = np.cos(2 * th)
        self.s2 = np.sin(2 * th)
        self.coh = ctx["coherence"].astype(np.float64)
        self.h, self.w = th.shape
        self.page = ctx["page"]

    def _bilinear(self, arr, x, y):
        x0 = min(max(int(x), 0), self.w - 2)
        y0 = min(max(int(y), 0), self.h - 2)
        fx = min(max(x - x0, 0.0), 1.0)
        fy = min(max(y - y0, 0.0), 1.0)
        return ((arr[y0, x0] * (1 - fx) + arr[y0, x0 + 1] * fx) * (1 - fy)
                + (arr[y0 + 1, x0] * (1 - fx)
                   + arr[y0 + 1, x0 + 1] * fx) * fy)

    def theta_at(self, pt_mm, fallback_rad: float,
                 min_coherence: float) -> float:
        """Field direction at a page point; falls back to a fixed angle in
        low-coherence (featureless) areas."""
        x, y = self.page.mm_to_px(np.asarray(pt_mm)[None, :])[0]
        if not (0 <= x < self.w - 1 and 0 <= y < self.h - 1):
            return fallback_rad
        if self._bilinear(self.coh, x, y) < min_coherence:
            return fallback_rad
        c = self._bilinear(self.c2, x, y)
        s = self._bilinear(self.s2, x, y)
        return 0.5 * np.arctan2(s, c)


class SpacingGrid:
    """Uniform hash grid rejecting points closer than ~spacing to any
    already-accepted streamline."""

    def __init__(self, spacing_mm: float):
        self.cell = spacing_mm / 2.0
        self.spacing = spacing_mm
        self.pts: dict[tuple[int, int], list[tuple[float, float]]] = {}

    def _key(self, p) -> tuple[int, int]:
        return (int(p[0] // self.cell), int(p[1] // self.cell))

    def too_close(self, p, factor: float = 0.85) -> bool:
        kx, ky = self._key(p)
        r2 = (self.spacing * factor) ** 2
        for i in range(kx - 2, kx + 3):
            for j in range(ky - 2, ky + 3):
                for q in self.pts.get((i, j), ()):
                    dx, dy = q[0] - p[0], q[1] - p[1]
                    if dx * dx + dy * dy < r2:
                        return True
        return False

    def add_line(self, pts) -> None:
        for p in pts:
            self.pts.setdefault(self._key(p), []).append(
                (float(p[0]), float(p[1])))


def trace_streamlines(mask: np.ndarray, ctx: dict, spacing_mm: float,
                      rng: np.random.Generator,
                      step_mm: float = 0.8,
                      max_len_mm: float = 500.0,
                      fallback_angle_deg: float = 50.0,
                      min_coherence: float = 0.05,
                      angle_offset_deg: float = 0.0,
                      min_len_mm: float = 2.0) -> list[np.ndarray]:
    """Evenly-spaced streamlines of the orientation field inside mask."""
    page = ctx["page"]
    sampler = FieldSampler(ctx)
    grid = SpacingGrid(spacing_mm)
    h, w = mask.shape
    fallback = np.deg2rad(fallback_angle_deg)
    offset = np.deg2rad(angle_offset_deg)
    max_steps = int(max_len_mm / step_mm)

    def inside(p_mm) -> bool:
        x, y = page.mm_to_px(np.asarray(p_mm)[None, :])[0]
        xi, yi = int(x), int(y)
        return 0 <= xi < w and 0 <= yi < h and bool(mask[yi, xi])

    def integrate(start, sign: int) -> list[np.ndarray]:
        out = []
        p = np.asarray(start, dtype=np.float64)
        prev_d = None
        for _ in range(max_steps // 2):
            th = sampler.theta_at(p, fallback, min_coherence) + offset
            d = np.array([np.cos(th), np.sin(th)])
            if prev_d is None:
                if sign < 0:
                    d = -d
            elif float(d @ prev_d) < 0:
                d = -d
            q = p + d * step_mm
            if not inside(q) or grid.too_close(q):
                break
            out.append(q)
            prev_d, p = d, q
        return out

    # seed candidates: jittered grid, visited in random order
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return []
    lo = page.px_to_mm(np.array([[xs.min(), ys.min()]], float))[0]
    hi = page.px_to_mm(np.array([[xs.max(), ys.max()]], float))[0]
    s = spacing_mm * 1.5
    gx = np.arange(lo[0], hi[0] + s, s)
    gy = np.arange(lo[1], hi[1] + s, s)
    seeds = np.array(np.meshgrid(gx, gy)).reshape(2, -1).T
    seeds = seeds + rng.uniform(-s / 3, s / 3, seeds.shape)
    seeds = seeds[rng.permutation(len(seeds))]

    lines: list[np.ndarray] = []
    for seed in seeds:
        if not inside(seed) or grid.too_close(seed):
            continue
        back = integrate(seed, -1)
        fwd = integrate(seed, +1)
        pts = back[::-1] + [np.asarray(seed, float)] + fwd
        if len(pts) < 2 or (len(pts) - 1) * step_mm < min_len_mm:
            continue
        line = np.array(pts)
        lines.append(line)
        grid.add_line(line[::2])
    return lines
