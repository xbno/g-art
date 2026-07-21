"""L0 of the vocabulary ladder (docs/vocabulary.md): the STROKE — one
continuous pen-down→pen-up path, the atom every arrangement places.

Every generator is `f(length_mm, params, rng) -> (N,2) float array` in a
LOCAL frame: start at the origin, principal direction +x, units mm. L1
arrangements place strokes with `place()` (rigid transform). Generators
emit CLEAN paths — wobble/overshoot belong to humanize, never here.

Purity: same (kind, length, params, rng state) → identical points.
Sampling density ~2 pts/mm so downstream field-bending and humanize have
vertices to work with.
"""

import numpy as np

Polyline = np.ndarray


def _p(params, key, default):
    return params.get(key, default) if params else default


def _t(length_mm: float, per_mm: float = 2.0, lo: int = 8) -> np.ndarray:
    n = max(int(round(length_mm * per_mm)), lo)
    return np.linspace(0.0, 1.0, n)


def line(length_mm, params=None, rng=None) -> Polyline:
    """Ruled hatch atom."""
    t = _t(length_mm)
    return np.stack([t * length_mm, np.zeros_like(t)], 1)


def arc(length_mm, params=None, rng=None) -> Polyline:
    """Bowed stroke; bow = max deviation as a fraction of length (signed)."""
    bow = _p(params, "bow", 0.12)
    t = _t(length_mm)
    y = bow * length_mm * 4 * t * (1 - t)  # parabolic ≈ circular for small bow
    return np.stack([t * length_mm, y], 1)


def crescent(length_mm, params=None, rng=None) -> Polyline:
    """Open C: a true circular arc spanning sweep_deg, chord = length."""
    sweep = np.deg2rad(_p(params, "sweep_deg", 150.0))
    r = length_mm / (2 * np.sin(sweep / 2))
    a = np.linspace(-sweep / 2, sweep / 2, len(_t(length_mm)))
    x = r * np.sin(a) + length_mm / 2
    y = r * np.cos(a) - r * np.cos(sweep / 2)
    return np.stack([x, y], 1)


def s_curve(length_mm, params=None, rng=None) -> Polyline:
    """Calligraphic double bend; amp as fraction of length."""
    amp = _p(params, "amp", 0.12)
    t = _t(length_mm)
    y = amp * length_mm * np.sin(2 * np.pi * t) * (0.25 + 0.75 * 4 * t * (1 - t))
    return np.stack([t * length_mm, y], 1)


def wave(length_mm, params=None, rng=None) -> Polyline:
    """Sine along the length (gen1 'wavy')."""
    amp = _p(params, "amp_mm", 0.8)
    cycles = _p(params, "cycles", 3.0)
    phase = _p(params, "phase", 0.0)
    t = _t(length_mm, per_mm=max(2.0, cycles))
    y = amp * np.sin(2 * np.pi * cycles * t + phase)
    return np.stack([t * length_mm, y], 1)


def zigzag(length_mm, params=None, rng=None) -> Polyline:
    """Triangle wave — nervous fill, dry-brush ancestor."""
    amp = _p(params, "amp_mm", 0.8)
    cycles = int(_p(params, "cycles", 4))
    xs, ys = [0.0], [0.0]
    for i in range(1, 2 * cycles + 1):
        xs.append(length_mm * i / (2 * cycles))
        ys.append(amp if i % 2 else -amp)
    ys[-1] = 0.0
    return np.stack([np.array(xs), np.array(ys)], 1)


def scallop(length_mm, params=None, rng=None) -> Polyline:
    """Repeated one-sided bumps — scales, cloud edges, foliage rims."""
    bump = _p(params, "bump_mm", 2.2)
    amp = _p(params, "amp_mm", 0.9)
    n = max(int(round(length_mm / bump)), 1)
    pts = []
    for i in range(n):
        a = np.linspace(np.pi, 0, 10)
        x = (i + (1 - np.cos(a)) / 2) * (length_mm / n)
        pts.append(np.stack([x, amp * np.sin(a)], 1))
    return np.concatenate(pts)


def loop(length_mm, params=None, rng=None) -> Polyline:
    """Cursive e-loops — prolate trochoid (curl_fill's true atom)."""
    h = _p(params, "loop_h_mm", 1.6)
    pitch = _p(params, "pitch_mm", 2.2)
    n = max(int(round(length_mm / pitch)), 1)
    t = np.linspace(0, 2 * np.pi * n, max(12 * n, 24))
    r = h / 2
    a = pitch / (2 * np.pi)
    x = a * t - r * np.sin(t)
    y = r * np.cos(t) - r
    x = x * (length_mm / max(x[-1], 1e-6))
    return np.stack([x, y], 1)


def spiral(length_mm, params=None, rng=None) -> Polyline:
    """Coiled dab: archimedean spiral whose footprint spans length_mm."""
    turns = _p(params, "turns", 2.5)
    t = np.linspace(0, 2 * np.pi * turns, max(int(24 * turns), 24))
    r = (length_mm / 2) * t / t[-1]
    x = r * np.cos(t) + length_mm / 2
    y = r * np.sin(t)
    return np.stack([x, y], 1)


def tick(length_mm, params=None, rng=None) -> Polyline:
    """Straight body with an end flick — grass, fur, ticking."""
    frac = _p(params, "flick_frac", 0.25)
    ang = np.deg2rad(_p(params, "flick_deg", 35.0))
    t = _t(length_mm)
    x = t * length_mm
    y = np.zeros_like(t)
    m = t > (1 - frac)
    s = (t[m] - (1 - frac)) / frac
    y[m] = np.tan(ang) * s ** 2 * frac * length_mm
    return np.stack([x, y], 1)


def noise_line(length_mm, params=None, rng=None) -> Polyline:
    """Random-walk drift (gen1 'noisy') — the only rng-dependent atom.
    corr_mm sets the drift wavelength; amp_mm the envelope."""
    amp = _p(params, "amp_mm", 0.7)
    corr = _p(params, "corr_mm", 3.0)
    rng = rng or np.random.default_rng(0)
    t = _t(length_mm)
    n = len(t)
    steps = rng.standard_normal(n)
    k = max(min(int(corr / length_mm * n), (n - 1) // 6), 1)
    kern = np.exp(-0.5 * (np.arange(-3 * k, 3 * k + 1) / k) ** 2)
    y = np.convolve(steps, kern / kern.sum(), mode="same")
    y = y / (np.abs(y).max() + 1e-9) * amp
    y -= y[0] + t * (y[-1] - y[0])  # pin both ends to the axis
    return np.stack([t * length_mm, y], 1)


def dot(length_mm, params=None, rng=None) -> Polyline:
    """Stipple dab — a tiny closed loop; length_mm is the dab diameter."""
    d = max(length_mm, 0.15)
    a = np.linspace(0, 2 * np.pi, 9)
    return np.stack([d / 2 * np.cos(a) + d / 2, d / 2 * np.sin(a)], 1)


STROKES = {
    "line": line, "arc": arc, "crescent": crescent, "s_curve": s_curve,
    "wave": wave, "zigzag": zigzag, "scallop": scallop, "loop": loop,
    "spiral": spiral, "tick": tick, "noise_line": noise_line, "dot": dot,
}

# primary sweep parameter per kind, for review sheets and mutation ranges
SWEEP = {
    "line": (None, []),
    "arc": ("bow", [0.05, 0.12, 0.25, -0.12]),
    "crescent": ("sweep_deg", [90, 150, 240, 320]),
    "s_curve": ("amp", [0.06, 0.12, 0.22]),
    "wave": ("amp_mm", [0.4, 0.8, 1.5]),
    "zigzag": ("amp_mm", [0.4, 0.8, 1.5]),
    "scallop": ("amp_mm", [0.5, 0.9, 1.6]),
    "loop": ("loop_h_mm", [1.0, 1.6, 2.6]),
    "spiral": ("turns", [1.5, 2.5, 4.0]),
    "tick": ("flick_deg", [20, 35, 60]),
    "noise_line": ("amp_mm", [0.35, 0.7, 1.3]),
    "dot": (None, []),
}


def stroke(kind: str, length_mm: float, params=None, rng=None) -> Polyline:
    return STROKES[kind](length_mm, params, rng)


def place(pts: Polyline, origin, angle_rad: float) -> Polyline:
    """Rigid transform local-frame stroke -> page mm. The ONLY way L1
    puts a stroke on the page."""
    c, s = np.cos(angle_rad), np.sin(angle_rad)
    return pts @ np.array([[c, s], [-s, c]]) + np.asarray(origin)
