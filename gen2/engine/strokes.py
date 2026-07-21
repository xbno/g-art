"""L0 of the vocabulary ladder (docs/vocabulary.md): the STROKE.

A stroke is one GESTURE: 1..k pen touches (k small — a broken line, a
cross-tick, a grass tuft are single gestures with lifts). Generators are
`f(length_mm, params, rng) -> list[(N,2) float array]` in a LOCAL frame:
start near the origin, principal direction +x, mm units. L1 arrangements
place gestures with `place()` (rigid transform).

Two doctrines:
- CLEAN of humanize: wobble/overshoot stay a downstream pass. But
  *character* — fBm drift, per-cycle unevenness, entry/exit behavior —
  belongs HERE: it is what a kind IS, not noise on top of it.
- Purity: same (kind, length, params, rng state) → identical points.

Families (review UI groups by these):
  geometric  the analytic references (ruler-and-compass; keep for calm
             passages and as baselines)
  ruled      hatching atoms with hand character (the workhorses)
  curved     single-bend gestures: hooks, commas, lashes, whips
  wave       uneven periodic meanders
  zigzag     angular runs
  bump       scallop kin: scales, clouds, garlands
  loop       trochoid kin: chains, coils, curlicues, knots
  spot       dabs and marks made in place
  organic    noise-native lines: ridges, bark, roots, seismo
"""

import numpy as np

Polyline = np.ndarray

STROKES: dict = {}
FAMILY: dict[str, list[str]] = {}


def _reg(family):
    def deco(fn):
        STROKES[fn.__name__] = fn
        FAMILY.setdefault(family, []).append(fn.__name__)
        return fn
    return deco


def _p(params, key, default):
    return params.get(key, default) if params else default


def _t(length_mm: float, per_mm: float = 3.0, lo: int = 16) -> np.ndarray:
    return np.linspace(0.0, 1.0, max(int(round(length_mm * per_mm)), lo))


def _xy(x, y) -> list:
    return [np.stack([np.asarray(x, float), np.asarray(y, float)], 1)]


def _fbm(n: int, rng, cycles: float = 3.0, octaves: int = 3,
         gain: float = 0.55) -> np.ndarray:
    """1D fractional-Brownian value noise in ~[-1,1] — the organic
    backbone. Smooth at `cycles` features per stroke, detail per octave."""
    x = np.linspace(0, 1, n)
    out = np.zeros(n)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        k = max(int(round(cycles * 2 ** o)) + 1, 2)
        vals = rng.uniform(-1, 1, k)
        xi = x * (k - 1)
        i0 = np.clip(np.floor(xi).astype(int), 0, k - 2)
        f = xi - i0
        f = (1 - np.cos(np.pi * f)) / 2
        out += amp * (vals[i0] * (1 - f) + vals[i0 + 1] * f)
        tot += amp
        amp *= gain
    return out / tot


def _uneven_phase(n: int, cycles: float, rng, ph_jit: float = 0.35):
    """Phase that advances at an fBm-jittered rate — periodic kinds stop
    being metronomes. Returns (phase 0..2πc, amp modulation ~1)."""
    rate = 1 + ph_jit * _fbm(n, rng, cycles=max(cycles / 2, 1), octaves=2)
    ph = np.cumsum(np.clip(rate, 0.2, None))
    ph = ph / ph[-1] * 2 * np.pi * cycles
    amp = 1 + 0.35 * _fbm(n, rng, cycles=max(cycles / 2, 1), octaves=2)
    return ph, amp


def _norm_chord(pts: np.ndarray, length_mm: float) -> np.ndarray:
    """Translate/rotate so the chord points +x, then scale so the x
    EXTENT spans length_mm. Extent, not chord: a curling path (hook,
    knot, scribble) has a short chord and would otherwise explode."""
    pts = pts - pts[0]
    d = pts[-1]
    ang = np.arctan2(d[1], d[0])
    c, s = np.cos(ang), np.sin(ang)
    pts = pts @ np.array([[c, -s], [s, c]])  # row-vectors by -ang
    span = pts[:, 0].max() - pts[:, 0].min()
    if span > 1e-9:
        pts = pts * (length_mm / span)
    return pts - [pts[:, 0].min(), 0]


def _from_heading(dtheta: np.ndarray, length_mm: float) -> np.ndarray:
    """Integrate a heading-change sequence into a path, chord-normalized.
    The natural way to draw whips, knots, bark: curvature is the gene."""
    theta = np.cumsum(dtheta)
    step = np.ones_like(theta)
    pts = np.cumsum(np.stack([step * np.cos(theta),
                              step * np.sin(theta)], 1), 0)
    pts = np.vstack([[0.0, 0.0], pts])
    return _norm_chord(pts, length_mm)


def _roughen(pts, rng, amp_mm=0.1, cycles=6.0):
    """Displace along local normals with fBm — hand texture on any path."""
    d = np.gradient(pts, axis=0)
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9
    return pts + nrm * (_fbm(len(pts), rng, cycles) * amp_mm)[:, None]


def _hand(pts, length_mm, rng, drift=0.014, tremor_mm=0.05):
    """The default hand: one slow drift + faint tremor. Applied INSIDE
    kinds that claim hand character (humanize adds page-space wobble on
    top later — different scale, different job)."""
    pts = _roughen(pts, rng, amp_mm=drift * length_mm, cycles=1.6)
    return _roughen(pts, rng, amp_mm=tremor_mm,
                    cycles=max(length_mm / 1.3, 6))


# ============================================================ geometric ====
@_reg("geometric")
def line(length_mm, params=None, rng=None):
    """Ruled line — the analytic baseline."""
    t = _t(length_mm)
    return _xy(t * length_mm, np.zeros_like(t))


@_reg("geometric")
def arc(length_mm, params=None, rng=None):
    """Bowed stroke; bow = sagitta/length, signed."""
    bow = _p(params, "bow", 0.12)
    t = _t(length_mm)
    return _xy(t * length_mm, bow * length_mm * 4 * t * (1 - t))


@_reg("geometric")
def crescent(length_mm, params=None, rng=None):
    """Open C — circular arc spanning sweep_deg, chord = length."""
    sweep = np.deg2rad(_p(params, "sweep_deg", 150.0))
    r = length_mm / (2 * np.sin(sweep / 2))
    a = np.linspace(-sweep / 2, sweep / 2, len(_t(length_mm)))
    return _xy(r * np.sin(a) + length_mm / 2,
               r * np.cos(a) - r * np.cos(sweep / 2))


@_reg("geometric")
def s_curve(length_mm, params=None, rng=None):
    """Symmetric double bend."""
    amp = _p(params, "amp", 0.12)
    t = _t(length_mm)
    return _xy(t * length_mm, amp * length_mm * np.sin(2 * np.pi * t)
               * (0.25 + 0.75 * 4 * t * (1 - t)))


@_reg("geometric")
def sine(length_mm, params=None, rng=None):
    """Pure sine — reference wave."""
    amp = _p(params, "amp_mm", 0.8)
    cycles = _p(params, "cycles", 3.0)
    t = _t(length_mm, per_mm=max(3.0, cycles))
    return _xy(t * length_mm, amp * np.sin(2 * np.pi * cycles * t))


@_reg("geometric")
def zigzag(length_mm, params=None, rng=None):
    """Even triangle wave — reference."""
    amp = _p(params, "amp_mm", 0.8)
    cycles = int(_p(params, "cycles", 4))
    xs = np.linspace(0, length_mm, 2 * cycles + 1)
    ys = np.array([0.0] + [amp if i % 2 else -amp
                           for i in range(1, 2 * cycles)] + [0.0])
    return _xy(xs, ys)


@_reg("geometric")
def spiral(length_mm, params=None, rng=None):
    """Even archimedean coil; length = footprint diameter."""
    turns = _p(params, "turns", 2.5)
    t = np.linspace(0, 2 * np.pi * turns, max(int(24 * turns), 24))
    r = (length_mm / 2) * t / t[-1]
    return _xy(r * np.cos(t) + length_mm / 2, r * np.sin(t))


@_reg("geometric")
def dot(length_mm, params=None, rng=None):
    """Stipple dab — tiny closed loop; length = diameter."""
    d = max(length_mm, 0.15)
    a = np.linspace(0, 2 * np.pi, 9)
    return _xy(d / 2 * np.cos(a) + d / 2, d / 2 * np.sin(a))


# ================================================================ ruled ====
@_reg("ruled")
def hand_line(length_mm, params=None, rng=None):
    """THE hatch atom: a hand-ruled 'straight' — slow drift + tremor."""
    return [_hand(line(length_mm)[0], length_mm, rng)]


@_reg("ruled")
def taper_line(length_mm, params=None, rng=None):
    """Pressure taper read as exit drift: the tail veers and settles."""
    t = _t(length_mm)
    veer = _p(params, "veer", 0.06) * length_mm
    y = veer * np.maximum(t - 0.65, 0) ** 2 / 0.35 ** 2
    return [_hand(_xy(t * length_mm, y)[0], length_mm, rng)]


@_reg("ruled")
def flick_line(length_mm, params=None, rng=None):
    """Fast exit flick — grass, fur, ticking."""
    frac = _p(params, "flick_frac", 0.22)
    ang = np.deg2rad(_p(params, "flick_deg", 38.0))
    t = _t(length_mm)
    y = np.zeros_like(t)
    m = t > 1 - frac
    s = (t[m] - (1 - frac)) / frac
    y[m] = np.tan(ang) * s ** 2 * frac * length_mm
    return [_hand(_xy(t * length_mm, y)[0], length_mm, rng, drift=0.008)]


@_reg("ruled")
def j_entry(length_mm, params=None, rng=None):
    """Entry hook then straight — the hesitation start of a loaded pen."""
    r = _p(params, "hook_frac", 0.09) * length_mm
    a = np.linspace(np.pi * 0.9, 0, 10)
    hook = np.stack([r * np.cos(a) - r * np.cos(np.pi * 0.9),
                     -r * np.sin(a)], 1)
    t = _t(length_mm * 0.9)
    body = np.stack([hook[-1, 0] + t * (length_mm - hook[-1, 0]),
                     np.zeros_like(t)], 1)
    return [_hand(np.vstack([hook, body[1:]]), length_mm, rng)]


@_reg("ruled")
def fishhook(length_mm, params=None, rng=None):
    """Straight body, tail curls back on itself."""
    r = _p(params, "hook_frac", 0.14) * length_mm
    t = _t(length_mm * 0.8)
    body = np.stack([t * (length_mm - r), np.zeros_like(t)], 1)
    a = np.linspace(-np.pi / 2, np.pi * 0.75, 14)
    hook = np.stack([body[-1, 0] + r * np.cos(a),
                     r + r * np.sin(a) - r], 1)
    return [_hand(np.vstack([body, hook[1:]]), length_mm, rng, drift=0.008)]


@_reg("ruled")
def swell_line(length_mm, params=None, rng=None):
    """Engraver's swell: lens-shaped out-and-back path that reads as a
    thick-thin line — width from geometry, since the pen can't press."""
    w = _p(params, "width_mm", 0.55)
    t = _t(length_mm)
    top = np.stack([t * length_mm, w / 2 * np.sin(np.pi * t)], 1)
    bot = np.stack([t[::-1] * length_mm,
                    -w / 2 * np.sin(np.pi * t[::-1])], 1)
    return [_hand(np.vstack([top, bot[1:]]), length_mm, rng,
                  drift=0.006, tremor_mm=0.03)]


@_reg("ruled")
def wedge_dab(length_mm, params=None, rng=None):
    """Back-and-forth shrinking traversals — a dark tapering dab."""
    n = int(_p(params, "passes", 5))
    w = _p(params, "width_mm", 1.1)
    pts = [np.array([0.0, 0.0])]
    for i in range(1, n + 1):
        frac = 1 - i / (n + 1)
        x = length_mm * (1 - frac) if i % 2 else length_mm * frac * 0.06
        pts.append(np.array([length_mm * frac if i % 2 else x,
                             w * frac * (1 if i % 2 else -1) / 2]))
    path = np.array(pts)
    t = np.linspace(0, 1, len(path))
    dense = np.stack([np.interp(np.linspace(0, 1, 40), t, path[:, 0]),
                      np.interp(np.linspace(0, 1, 40), t, path[:, 1])], 1)
    return [_roughen(dense, rng, amp_mm=0.06, cycles=8)]


@_reg("ruled")
def double_line(length_mm, params=None, rng=None):
    """Out and back with a gap — railroad; reads as a confident pair."""
    g = _p(params, "gap_mm", 0.5)
    t = _t(length_mm)
    out = np.stack([t * length_mm, np.full_like(t, g / 2)], 1)
    back = np.stack([t[::-1] * length_mm, np.full_like(t, -g / 2)], 1)
    return [_hand(np.vstack([out, back]), length_mm, rng, drift=0.01)]


@_reg("ruled")
def sketch_line(length_mm, params=None, rng=None):
    """2-3 overlapping retraces, each with fresh drift — the searching
    line of an underdrawing."""
    passes = int(_p(params, "passes", 3))
    t = _t(length_mm)
    segs = []
    for i in range(passes):
        base = np.stack([t * length_mm, np.zeros_like(t)], 1)
        y0 = (rng.uniform(-1, 1) * 0.15) if i else 0.0
        pp = _hand(base + [0, y0], length_mm, rng, drift=0.02)
        segs.append(pp if i % 2 == 0 else pp[::-1])
    return [np.vstack(segs)]


@_reg("ruled")
def broken_line(length_mm, params=None, rng=None):
    """Lost-and-found line: touches with gaps, slightly misaligned."""
    n = int(_p(params, "pieces", 3))
    gap = _p(params, "gap_frac", 0.08)
    edges = np.sort(rng.uniform(0.1, 0.9, n - 1))
    starts = np.concatenate([[0], edges + gap / 2])
    ends = np.concatenate([edges - gap / 2, [1]])
    out = []
    for s, e in zip(starts, ends):
        if e - s < 0.05:
            continue
        t = np.linspace(s, e, max(int((e - s) * length_mm * 3), 6))
        seg = np.stack([t * length_mm,
                        np.full_like(t, rng.uniform(-0.08, 0.08))], 1)
        out.append(_hand(seg, (e - s) * length_mm, rng))
    return out


@_reg("ruled")
def dry_brush(length_mm, params=None, rng=None):
    """Dry-brush skip: ink lands where the fBm says the tooth caught;
    coverage thins toward the tail."""
    t = _t(length_mm, per_mm=4.0)
    keep = _fbm(len(t), rng, cycles=length_mm / 2.2, octaves=2) \
        > (-0.55 + 1.0 * t)
    y = _fbm(len(t), rng, cycles=2.0) * 0.15
    out, run = [], []
    for i, k in enumerate(keep):
        if k:
            run.append([t[i] * length_mm, y[i]])
        elif len(run) > 2:
            out.append(np.array(run)); run = []
        else:
            run = []
    if len(run) > 2:
        out.append(np.array(run))
    return out or [np.array([[0, 0], [length_mm * 0.3, 0]])]


@_reg("ruled")
def stitch_run(length_mm, params=None, rng=None):
    """Short dashes, each at its own slight angle — tailor's stitching."""
    pitch = _p(params, "pitch_mm", 2.2)
    duty = _p(params, "duty", 0.55)
    n = max(int(length_mm / pitch), 2)
    out = []
    for i in range(n):
        x0 = (i + rng.uniform(-0.12, 0.12)) * pitch
        a = rng.uniform(-0.18, 0.18)
        ln = pitch * duty * rng.uniform(0.8, 1.2)
        out.append(np.array([[x0, 0], [x0 + ln * np.cos(a),
                                       ln * np.sin(a)]]))
    return out


# =============================================================== curved ====
@_reg("curved")
def hand_arc(length_mm, params=None, rng=None):
    """Bracelet-shading arc with hand character; bow varies per stroke."""
    bow = _p(params, "bow", 0.12) * rng.uniform(0.75, 1.3)
    return [_hand(arc(length_mm, {"bow": bow})[0], length_mm, rng)]


@_reg("curved")
def hook_tail(length_mm, params=None, rng=None):
    """Deep entry hook melting into a straight tail — a walking cane."""
    t = _t(length_mm, per_mm=5.0)
    total = np.deg2rad(_p(params, "entry_deg", 205.0)
                       * rng.uniform(0.85, 1.15))
    w = np.exp(-((t) / 0.16) ** 2)
    dth = total * w / w.sum()
    return [_hand(_from_heading(dth, length_mm), length_mm, rng,
                  drift=0.008)]


@_reg("curved")
def ogee(length_mm, params=None, rng=None):
    """Asymmetric S — cyma curve; bias shifts the crossing point."""
    bias = _p(params, "bias", 0.36) * (rng.uniform(0.8, 1.25) if rng else 1)
    amp = _p(params, "amp", 0.14) * (rng.uniform(0.8, 1.25) if rng else 1)
    t = _t(length_mm)
    ph = np.where(t < bias, t / bias * np.pi, np.pi
                  + (t - bias) / (1 - bias) * np.pi)
    return [_hand(_xy(t * length_mm,
                      amp * length_mm * np.sin(ph) * 0.8)[0],
                  length_mm, rng, drift=0.008)]


@_reg("curved")
def comma(length_mm, params=None, rng=None):
    """Sumi comma: the stroke unfurls from a curled head into a tail —
    spiral-out in polar space, no chord tricks."""
    t = _t(length_mm, per_mm=5.0)
    turn = _p(params, "turn", 1.08) * np.pi * rng.uniform(0.85, 1.15)
    theta = turn * (1 - t) ** 1.5
    r = length_mm * (0.14 + 0.86 * t ** 0.9)
    pts = np.stack([r * np.cos(theta), r * np.sin(theta)], 1)
    pts -= pts[0]
    return [_roughen(_norm_chord(pts, length_mm), rng, 0.04, 4)]


@_reg("curved")
def teardrop(length_mm, params=None, rng=None):
    """Closed drop, point toward the origin — rain, leaves, petals.
    Outline traced out along +w and back along -w; no chord tricks."""
    t = np.linspace(0, 1, 20)
    w = 0.62 * length_mm * t ** 0.85 * np.sqrt(np.maximum(1 - t, 0)) \
        * rng.uniform(0.85, 1.15)
    x = t * length_mm
    up = np.stack([x, w / 2], 1)
    down = np.stack([x[::-1], -w[::-1] / 2], 1)
    return [_roughen(np.vstack([up, down[1:]]), rng, 0.03, 3)]


@_reg("curved")
def lash(length_mm, params=None, rng=None):
    """Eyelash: bow peaking early, tail settling flat."""
    t = _t(length_mm)
    amp = _p(params, "amp", 0.16) * length_mm * rng.uniform(0.8, 1.25)
    y = amp * (t ** 0.4) * (1 - t) ** 1.9 * 4.2
    return [_roughen(_xy(t * length_mm, y)[0], rng, 0.04, 5)]


@_reg("curved")
def whip(length_mm, params=None, rng=None):
    """Whip crack: violent entry curl, dead-straight exit."""
    t = _t(length_mm, per_mm=5.0)
    total = np.deg2rad(_p(params, "curve_deg", 300.0)
                       * rng.uniform(0.8, 1.2))
    w = np.exp(-((t) / 0.09) ** 2)
    dth = total * w / w.sum()
    return [_roughen(_from_heading(dth, length_mm), rng, 0.05, 4)]


@_reg("curved")
def catenary(length_mm, params=None, rng=None):
    """Hanging-chain sag — wires, garlands, hammocks."""
    sag = _p(params, "sag", 0.16) * (rng.uniform(0.75, 1.3) if rng else 1)
    t = _t(length_mm)
    y = -sag * length_mm * (np.cosh((t - 0.5) * 2.4) - np.cosh(1.2)) \
        / (1 - np.cosh(1.2))
    return [_hand(_xy(t * length_mm, y - y[0])[0], length_mm, rng,
                  drift=0.006)]


@_reg("curved")
def ribbon_s(length_mm, params=None, rng=None):
    """Deep S nearly closing on itself — drapery, river bends."""
    amp = _p(params, "amp", 0.2) * rng.uniform(0.8, 1.2)
    t = _t(length_mm)
    y = amp * length_mm * np.sin(2 * np.pi * t)
    x = t * length_mm + amp * length_mm * 0.35 * np.sin(4 * np.pi * t + np.pi)
    return [_roughen(_norm_chord(np.stack([x, y], 1), length_mm),
                     rng, 0.05, 3)]


@_reg("curved")
def c_flick(length_mm, params=None, rng=None):
    """Crescent with a straightened exit flick."""
    sweep = 130 * rng.uniform(0.8, 1.2)
    body = crescent(length_mm * 0.8, {"sweep_deg": sweep})[0]
    d = body[-1] - body[-3]
    d /= np.linalg.norm(d) + 1e-9
    tail = body[-1] + np.outer(np.linspace(0, 1, 8) ** 0.7,
                               d) * length_mm * 0.25
    return [_roughen(_norm_chord(np.vstack([body, tail[1:]]), length_mm),
                     rng, 0.04, 4)]


# ================================================================= wave ====
@_reg("wave")
def hand_wave(length_mm, params=None, rng=None):
    """Sine that breathes: fBm-jittered wavelength and amplitude."""
    amp = _p(params, "amp_mm", 0.8)
    cycles = _p(params, "cycles", 3.5)
    t = _t(length_mm, per_mm=max(3.0, cycles))
    ph, am = _uneven_phase(len(t), cycles, rng)
    return [_roughen(_xy(t * length_mm, amp * am * np.sin(ph))[0],
                     rng, 0.04, 6)]


@_reg("wave")
def ripple(length_mm, params=None, rng=None):
    """Disturbance dying out — decaying uneven wave."""
    amp = _p(params, "amp_mm", 1.1)
    cycles = _p(params, "cycles", 4.5)
    t = _t(length_mm, per_mm=max(3.0, cycles))
    ph, am = _uneven_phase(len(t), cycles, rng)
    return _xy(t * length_mm, amp * am * np.exp(-2.6 * t) * np.sin(ph))


@_reg("wave")
def swell_wave(length_mm, params=None, rng=None):
    """Wave rising then settling — mid-stroke energy."""
    amp = _p(params, "amp_mm", 1.0)
    cycles = _p(params, "cycles", 4.0)
    t = _t(length_mm, per_mm=max(3.0, cycles))
    ph, am = _uneven_phase(len(t), cycles, rng)
    return _xy(t * length_mm,
               amp * am * np.sin(np.pi * t) ** 1.5 * np.sin(ph))


@_reg("wave")
def chirp(length_mm, params=None, rng=None):
    """Wavelength tightening along the stroke — acceleration."""
    amp = _p(params, "amp_mm", 0.8)
    c0, c1 = _p(params, "cycles0", 1.5), _p(params, "cycles1", 6.0)
    t = _t(length_mm, per_mm=max(3.0, c1))
    ph = 2 * np.pi * (c0 * t + (c1 - c0) * t ** 2 / 2) * 2
    return [_roughen(_xy(t * length_mm, amp * np.sin(ph))[0], rng, 0.05, 4)]


@_reg("wave")
def serpentine(length_mm, params=None, rng=None):
    """One-and-a-bit slow meanders — the lazy river."""
    amp = _p(params, "amp", 0.15)
    t = _t(length_mm)
    ph, am = _uneven_phase(len(t), 1.4, rng, ph_jit=0.25)
    return [_hand(_xy(t * length_mm,
                      amp * length_mm * am * np.sin(ph))[0],
                  length_mm, rng, drift=0.008)]


@_reg("wave")
def crimp(length_mm, params=None, rng=None):
    """Tight irregular crinkle — wool, foliage edges, static."""
    amp = _p(params, "amp_mm", 0.55)
    t = _t(length_mm, per_mm=6.0)
    ph, am = _uneven_phase(len(t), length_mm / 1.15, rng, ph_jit=0.5)
    return _xy(t * length_mm, amp * am * np.sin(ph))


@_reg("wave")
def seismo(length_mm, params=None, rng=None):
    """Calm line with bursts — seismograph, distant tree rows."""
    amp = _p(params, "amp_mm", 1.3)
    t = _t(length_mm, per_mm=6.0)
    env = np.maximum(_fbm(len(t), rng, 2.5, 2), 0) ** 2 * 3
    y = amp * env * _fbm(len(t), rng, length_mm / 0.9, 2)
    return _xy(t * length_mm, y)


@_reg("wave")
def flame_wave(length_mm, params=None, rng=None):
    """Leaning crests via waveshaping — fire, wind-driven water."""
    amp = _p(params, "amp_mm", 1.0)
    cycles = _p(params, "cycles", 3.5)
    lean = _p(params, "lean", 0.6)
    t = _t(length_mm, per_mm=max(4.0, cycles))
    ph, am = _uneven_phase(len(t), cycles, rng)
    return _xy(t * length_mm, amp * am * np.sin(ph + lean * np.sin(ph)))


# =============================================================== zigzag ====
@_reg("zigzag")
def hand_zigzag(length_mm, params=None, rng=None):
    """Zigzag with jittered pitch and peak heights."""
    amp = _p(params, "amp_mm", 0.9)
    cycles = int(_p(params, "cycles", 5))
    n = 2 * cycles + 1
    xs = np.linspace(0, length_mm, n) \
        + rng.uniform(-0.18, 0.18, n) * length_mm / n
    xs[0], xs[-1] = 0, length_mm
    ys = np.array([0.0] + [amp * rng.uniform(0.55, 1.35)
                           * (1 if i % 2 else -1)
                           for i in range(1, n - 1)] + [0.0])
    return _xy(xs, ys)


@_reg("zigzag")
def lightning(length_mm, params=None, rng=None):
    """Few hard segments at random angles — cracks, bolts, branches."""
    n = int(rng.integers(4, 8))
    pts = [np.zeros(2)]
    ang = 0.0
    for i in range(n):
        ang = rng.uniform(0.35, 1.1) * (1 if i % 2 else -1)
        ln = rng.uniform(0.6, 1.5)
        pts.append(pts[-1] + ln * np.array([np.cos(ang), np.sin(ang)]))
    return [_norm_chord(np.array(pts), length_mm)]


@_reg("zigzag")
def sawtooth(length_mm, params=None, rng=None):
    """Slow rise, sharp drop — rooflines, fir silhouettes."""
    amp = _p(params, "amp_mm", 1.1)
    cycles = int(_p(params, "cycles", 4))
    xs, ys = [0.0], [0.0]
    for i in range(cycles):
        p = length_mm / cycles
        j = rng.uniform(0.75, 1.25)
        xs += [xs[-1] + p * 0.8 * j, xs[-1] + p * j]
        ys += [amp * rng.uniform(0.7, 1.3), 0.0]
    return [_norm_chord(_xy(np.array(xs), np.array(ys))[0], length_mm)]


@_reg("zigzag")
def staircase(length_mm, params=None, rng=None):
    """Jittered steps — strata, masonry, terraces."""
    steps = int(_p(params, "steps", 4))
    rise = _p(params, "rise_mm", 1.0)
    xs, ys = [0.0], [0.0]
    for i in range(steps):
        run = length_mm / steps * rng.uniform(0.7, 1.3)
        xs += [xs[-1] + run, xs[-1] + run]
        ys += [ys[-1], ys[-1] + rise * rng.uniform(0.7, 1.3)]
    return [_norm_chord(_xy(np.array(xs), np.array(ys))[0], length_mm)]


@_reg("zigzag")
def crenel(length_mm, params=None, rng=None):
    """Battlement square wave, jittered duty and height."""
    amp = _p(params, "amp_mm", 0.9)
    cycles = int(_p(params, "cycles", 4))
    xs, ys = [0.0], [0.0]
    for i in range(cycles):
        p = length_mm / cycles
        d = rng.uniform(0.35, 0.65)
        h = amp * rng.uniform(0.75, 1.25)
        x0 = xs[-1]
        xs += [x0, x0 + d * p, x0 + d * p, x0 + p]
        ys += [h, h, 0.0, 0.0]
    return _xy(np.array(xs), np.array(ys))


@_reg("zigzag")
def needle_run(length_mm, params=None, rng=None):
    """Very tight uneven zigzag — reads as one fat rough line (a
    darkness atom the calibration will love)."""
    amp = _p(params, "amp_mm", 0.5)
    pitch = _p(params, "pitch_mm", 0.65)
    cycles = max(int(length_mm / pitch), 3)
    return hand_zigzag(length_mm, {"amp_mm": amp, "cycles": cycles}, rng)


# ================================================================= bump ====
@_reg("bump")
def hand_scallop(length_mm, params=None, rng=None):
    """Bumps of uneven width and height — tiles, feathers."""
    amp = _p(params, "amp_mm", 0.9)
    bump = _p(params, "bump_mm", 2.4)
    n = max(int(length_mm / bump), 2)
    widths = rng.uniform(0.65, 1.45, n)
    widths *= length_mm / widths.sum()
    pts, x0 = [], 0.0
    for w in widths:
        a = np.linspace(np.pi, 0, 10)
        h = amp * rng.uniform(0.65, 1.3)
        pts.append(np.stack([x0 + (1 - np.cos(a)) / 2 * w,
                             h * np.sin(a)], 1))
        x0 += w
    return [np.concatenate(pts)]


@_reg("bump")
def cloud_run(length_mm, params=None, rng=None):
    """Big soft uneven lobes on a drifting baseline — cumulus edges."""
    amp = _p(params, "amp_mm", 1.7)
    n = max(int(length_mm / _p(params, "bump_mm", 4.5)), 2)
    widths = rng.uniform(0.6, 1.6, n)
    widths *= length_mm / widths.sum()
    base = _fbm(n + 1, rng, 2.0, 2) * amp * 0.35
    pts, x0 = [], 0.0
    for i, w in enumerate(widths):
        a = np.linspace(np.pi * 1.05, -np.pi * 0.05, 14)
        h = amp * rng.uniform(0.6, 1.25)
        y0 = np.interp([0, 1], [0, 1], [base[i], base[i + 1]])
        pts.append(np.stack([x0 + (1 - np.cos(a)) / 2 * w,
                             np.linspace(y0[0], y0[1], 14)
                             + h * np.sin(np.clip(a, 0, np.pi))], 1))
        x0 += w
    return [np.concatenate(pts)]


@_reg("bump")
def fish_scale(length_mm, params=None, rng=None):
    """Leaning bumps, each starting under the last — scales, shingles."""
    amp = _p(params, "amp_mm", 0.9)
    bump = _p(params, "bump_mm", 2.6)
    lean = _p(params, "lean", 1.35)
    n = max(int(length_mm / bump), 2)
    pts, x0 = [], 0.0
    for i in range(n):
        a = np.linspace(np.pi, 0, 12)
        w = bump * rng.uniform(0.8, 1.2)
        pts.append(np.stack([x0 + ((1 - np.cos(a)) / 2) ** lean * w,
                             amp * rng.uniform(0.75, 1.2) * np.sin(a)], 1))
        x0 += w * 0.8
    return [_norm_chord(np.concatenate(pts), length_mm)]


@_reg("bump")
def garland(length_mm, params=None, rng=None):
    """Hanging bumps — swags, drapery, vines."""
    out = hand_scallop(length_mm, params, rng)
    out[0][:, 1] *= -1
    return out


@_reg("bump")
def wave_crest(length_mm, params=None, rng=None):
    """Forward-leaning crests that nearly break — Hokusai foam."""
    amp = _p(params, "amp_mm", 1.3)
    n = max(int(length_mm / _p(params, "bump_mm", 3.6)), 2)
    pts, x0 = [], 0.0
    for i in range(n):
        w = length_mm / n * rng.uniform(0.8, 1.2)
        a = np.linspace(np.pi * 1.25, 0, 14)
        h = amp * rng.uniform(0.7, 1.2)
        pts.append(np.stack(
            [x0 + ((1 - np.cos(np.clip(a, 0, np.pi))) / 2) ** 1.6 * w,
             h * np.sin(a) * np.where(a > np.pi, 0.5, 1.0)], 1))
        x0 += w
    return [np.concatenate(pts)]


# ================================================================= loop ====
@_reg("loop")
def hand_loop(length_mm, params=None, rng=None):
    """Cursive e-loops, each its own size and lean."""
    h = _p(params, "loop_h_mm", 1.7)
    pitch = _p(params, "pitch_mm", 2.3)
    n = max(int(length_mm / pitch), 2)
    pts = []
    x0 = 0.0
    for i in range(n):
        r = h / 2 * rng.uniform(0.7, 1.3)
        p = pitch * rng.uniform(0.8, 1.25)
        t = np.linspace(0, 2 * np.pi, 14)
        lean = rng.uniform(-0.25, 0.4)
        x = x0 + p * t / (2 * np.pi) - r * np.sin(t) + lean * r * np.cos(t)
        y = r * np.cos(t) - r
        pts.append(np.stack([x, y], 1))
        x0 += p
    return [_norm_chord(np.concatenate(pts), length_mm)]


@_reg("loop")
def chain_loop(length_mm, params=None, rng=None):
    """Loops alternating above and below the axis — chains, braids."""
    h = _p(params, "loop_h_mm", 1.6)
    pitch = _p(params, "pitch_mm", 2.4)
    n = max(int(length_mm / pitch), 2)
    pts, x0 = [], 0.0
    for i in range(n):
        r = h / 2 * rng.uniform(0.8, 1.2)
        t = np.linspace(0, 2 * np.pi, 14)
        s = 1 if i % 2 else -1
        x = x0 + pitch * t / (2 * np.pi) - r * np.sin(t)
        y = s * (r * np.cos(t) - r)
        pts.append(np.stack([x, y], 1))
        x0 += pitch
    return [_norm_chord(np.concatenate(pts), length_mm)]


@_reg("loop")
def figure8_run(length_mm, params=None, rng=None):
    """Advancing figure-eights — basketry, tight scribble texture."""
    h = _p(params, "h_mm", 1.8)
    pitch = _p(params, "pitch_mm", 2.6)
    n = max(int(length_mm / pitch), 2)
    pts, x0 = [], 0.0
    for i in range(n):
        t = np.linspace(0, 2 * np.pi, 18)
        w = pitch * rng.uniform(0.75, 1.2)
        x = x0 + w * (0.5 - 0.5 * np.cos(t)) \
            + 0.18 * w * np.sin(2 * t) * rng.uniform(0.6, 1.4)
        y = h / 2 * np.sin(2 * t) * rng.uniform(0.75, 1.2)
        pts.append(np.stack([x, y], 1))
        x0 += w
    return [_norm_chord(np.concatenate(pts), length_mm)]


@_reg("loop")
def knot_line(length_mm, params=None, rng=None):
    """Mostly-calm line that ties 1-3 little loops — rope, vine knots.
    Built in heading space: a knot is just +2π of turning, briefly."""
    t = _t(length_mm, per_mm=5.0)
    n = len(t)
    dth = _fbm(n, rng, 2.0, 2) * 0.05
    for pos in rng.uniform(0.15, 0.85, int(rng.integers(1, 4))):
        w = 0.04
        window = np.exp(-0.5 * ((t - pos) / w) ** 2)
        dth += 2 * np.pi * window / window.sum()
    return [_roughen(_from_heading(dth, length_mm), rng, 0.04, 5)]


@_reg("loop")
def coil(length_mm, params=None, rng=None):
    """Overlapping spring loops — tight wool, telephone cord."""
    return hand_loop(length_mm, {"loop_h_mm": _p(params, "loop_h_mm", 2.2),
                                 "pitch_mm": _p(params, "pitch_mm", 1.1)},
                     rng)


@_reg("loop")
def curlicue(length_mm, params=None, rng=None):
    """Flourish: loops shrinking into a tail — fern tips, pigtails."""
    h0 = _p(params, "loop_h_mm", 2.6)
    n = int(_p(params, "loops", 3))
    pts, x0 = [], 0.0
    for i in range(n):
        r = h0 / 2 * (1 - i / (n + 0.5)) * rng.uniform(0.85, 1.15)
        pitch = 2.6 * r
        t = np.linspace(0, 2 * np.pi, 14)
        x = x0 + pitch * t / (2 * np.pi) - r * np.sin(t)
        y = r * np.cos(t) - r
        pts.append(np.stack([x, y], 1))
        x0 += pitch
    tail = np.stack([x0 + np.linspace(0, 2.5 * h0 / 2.6, 8),
                     np.zeros(8)], 1)
    pts.append(tail)
    return [_norm_chord(np.concatenate(pts), length_mm)]


@_reg("loop")
def pigtail(length_mm, params=None, rng=None):
    """Line, one loop, line — a single knot in a straight run."""
    t = _t(length_mm, per_mm=5.0)
    dth = _fbm(len(t), rng, 2.0, 2) * 0.03
    pos = rng.uniform(0.35, 0.65)
    window = np.exp(-0.5 * ((t - pos) / 0.05) ** 2)
    dth += 2 * np.pi * window / window.sum()
    return [_roughen(_from_heading(dth, length_mm), rng, 0.04, 4)]


# ================================================================= spot ====
@_reg("spot")
def hand_spiral(length_mm, params=None, rng=None):
    """Uneven squashed coil — wool, foliage dab, rosette."""
    turns = _p(params, "turns", 2.6)
    t = np.linspace(0, 2 * np.pi * turns, max(int(24 * turns), 24))
    r = (length_mm / 2) * t / t[-1] * (1 + 0.16 * _fbm(len(t), rng, 3.0, 2))
    sq = rng.uniform(0.65, 0.95)
    rot = rng.uniform(0, np.pi)
    x, y = r * np.cos(t), r * np.sin(t) * sq
    c, s = np.cos(rot), np.sin(rot)
    return _xy(c * x - s * y + length_mm / 2, s * x + c * y)


@_reg("spot")
def bean(length_mm, params=None, rng=None):
    """Closed uneven blob outline — pebbles, leaves, stones."""
    a = np.linspace(0, 2 * np.pi, 26)
    wob = _fbm(26, rng, 3.0, 2)
    wob = wob - np.linspace(wob[0], wob[-1], 26)  # close the loop
    r = length_mm / 2 * (1 + 0.28 * wob)
    return _xy(r * np.cos(a) * 0.8 + length_mm / 2, r * np.sin(a) * 0.55)


@_reg("spot")
def pebble(length_mm, params=None, rng=None):
    """Rounder, calmer bean."""
    a = np.linspace(0, 2 * np.pi, 22)
    wob = _fbm(22, rng, 2.0, 2)
    wob = wob - np.linspace(wob[0], wob[-1], 22)
    r = length_mm / 2 * (1 + 0.12 * wob)
    return _xy(r * np.cos(a) * 0.9 + length_mm / 2, r * np.sin(a) * 0.75)


@_reg("spot")
def squiggle_dab(length_mm, params=None, rng=None):
    """Two tight random curls in place — moss, gravel, stubble."""
    n = 36
    dth = 0.55 * np.ones(n) * rng.choice([-1, 1]) \
        + _fbm(n, rng, 4.0, 2) * 0.9
    pts = _from_heading(dth, length_mm)
    return [pts]


@_reg("spot")
def cross_tick(length_mm, params=None, rng=None):
    """Two short strokes crossing — scrub texture, stitches, stars."""
    a = rng.uniform(0.6, 1.1)
    l1 = length_mm * rng.uniform(0.85, 1.15)
    mk = lambda ang, ln: np.array(
        [[-ln / 2 * np.cos(ang), -ln / 2 * np.sin(ang)],
         [ln / 2 * np.cos(ang), ln / 2 * np.sin(ang)]]) \
        + [length_mm / 2, 0]
    return [mk(0.15 * rng.standard_normal(), length_mm),
            mk(a, l1)]


@_reg("spot")
def asterisk_dab(length_mm, params=None, rng=None):
    """Three crossing ticks — burst, thistle, star."""
    out = []
    for k in range(3):
        ang = k * np.pi / 3 + rng.uniform(-0.15, 0.15)
        ln = length_mm * rng.uniform(0.8, 1.1)
        out.append(np.array(
            [[-ln / 2 * np.cos(ang), -ln / 2 * np.sin(ang)],
             [ln / 2 * np.cos(ang), ln / 2 * np.sin(ang)]])
            + [length_mm / 2, 0])
    return out


@_reg("spot")
def tuft(length_mm, params=None, rng=None):
    """3-5 flicks fanning from one root — grass, lashes, fur clumps."""
    n = int(rng.integers(3, 6))
    out = []
    for i in range(n):
        ang = (i - (n - 1) / 2) * rng.uniform(0.25, 0.4)
        ln = length_mm * rng.uniform(0.6, 1.05)
        t = np.linspace(0, 1, 10)
        x = t * ln
        y = np.sign(ang) * np.abs(ang) * ln * t ** 2 * 0.8
        c, s = np.cos(ang * 0.6), np.sin(ang * 0.6)
        pts = np.stack([c * x - s * y, s * x + c * y], 1)
        out.append(pts)
    return out


# =============================================================== organic ====
@_reg("organic")
def fbm_ridge(length_mm, params=None, rng=None):
    """Pure fBm profile — mountain silhouettes, torn paper, coastlines."""
    amp = _p(params, "amp", 0.12)
    t = _t(length_mm, per_mm=4.0)
    y = _fbm(len(t), rng, _p(params, "cycles", 5.0), 4) * amp * length_mm
    return _xy(t * length_mm, y - y[0])


@_reg("organic")
def jitter_walk(length_mm, params=None, rng=None):
    """Momentum random walk — a wandering, undecided line."""
    t = _t(length_mm, per_mm=4.0)
    n = len(t)
    v = 0.0
    y = np.zeros(n)
    amp = _p(params, "amp_mm", 0.9)
    for i in range(1, n):
        v = 0.86 * v + rng.standard_normal() * 0.3
        y[i] = y[i - 1] + v * amp / n * 6
    return [_norm_chord(_xy(t * length_mm, y)[0], length_mm)]


@_reg("organic")
def bark_line(length_mm, params=None, rng=None):
    """Slow wiggle with occasional knot bumps — tree bark, driftwood."""
    t = _t(length_mm, per_mm=5.0)
    n = len(t)
    dth = _fbm(n, rng, 4.0, 3) * 0.14
    for pos in rng.uniform(0.15, 0.85, int(rng.integers(1, 3))):
        w = 0.03
        window = np.exp(-0.5 * ((t - pos) / w) ** 2)
        dth += np.pi * 0.9 * window / window.sum() \
            * rng.choice([-1, 1])
        window2 = np.exp(-0.5 * ((t - pos - 0.05) / w) ** 2)
        dth -= np.pi * 1.15 * window2 / window2.sum() \
            * rng.choice([-1, 1]) * 0  # bump out, drift back naturally
    return [_roughen(_from_heading(dth, length_mm), rng, 0.05, 8)]


@_reg("organic")
def root_line(length_mm, params=None, rng=None):
    """Drifting line with out-and-back nubs — roots, branching hints."""
    t = _t(length_mm, per_mm=5.0)
    n = len(t)
    dth = _fbm(n, rng, 2.5, 2) * 0.12
    for pos in rng.uniform(0.2, 0.8, 2):
        w = 0.022
        win1 = np.exp(-0.5 * ((t - pos) / w) ** 2)
        win2 = np.exp(-0.5 * ((t - pos - 0.06) / w) ** 2)
        s = rng.choice([-1, 1])
        dth += s * 2.6 * win1 / win1.sum()
        dth -= s * 2.6 * win2 / win2.sum()
    return [_roughen(_from_heading(dth, length_mm), rng, 0.04, 6)]


@_reg("organic")
def hairline(length_mm, params=None, rng=None):
    """Long, barely-curved, faintly trembling — the lightest touch."""
    t = _t(length_mm)
    bow = rng.uniform(-0.045, 0.045)
    y = bow * length_mm * 4 * t * (1 - t)
    return [_roughen(_xy(t * length_mm, y)[0], rng, 0.035,
                     max(length_mm / 2.5, 4))]


@_reg("organic")
def meander_scribble(length_mm, params=None, rng=None):
    """Open wandering scribble advancing +x — energy without pattern."""
    n = 70
    dth = _fbm(n, rng, 8.0, 3) * 1.05
    return [_roughen(_from_heading(dth, length_mm), rng, 0.05, 8)]


# ============================================================== plumbing ===
def stroke(kind: str, length_mm: float, params=None, rng=None):
    rng = rng or np.random.default_rng(0)
    return STROKES[kind](length_mm, params, rng)


def place(gesture, origin, angle_rad: float):
    """Rigid transform local-frame gesture -> page mm. The ONLY way L1
    puts strokes on the page."""
    c, s = np.cos(angle_rad), np.sin(angle_rad)
    R = np.array([[c, s], [-s, c]])
    o = np.asarray(origin, float)
    if isinstance(gesture, np.ndarray):
        gesture = [gesture]
    return [pts @ R + o for pts in gesture]
