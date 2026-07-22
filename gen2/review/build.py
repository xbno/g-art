"""Section builders for the review site. Each builder writes PNGs under
runs/review/imgs/ and returns a JSON-able dict that index.html renders.

Sections:
    marks        every mark module at calibrated settings — flat swatch,
                 gradient (tone_gate) response, measured coverage, and the
                 sorted Guptill value scale
    pipeline     the active (genome, photo) pair stage by stage: photo →
                 tone / orientation / normals → scene → plan masses →
                 committed levels (the promise) → assigned stacks →
                 per-pen layers → final render → ink delivered vs promised
    translation  the translation test made visual: per-mass verdict map,
                 target-vs-achieved table
    iterations   content-hash archive of every state the active genomes
                 pass through — a permanent timeline with genome diffs

Heavy artifacts are cached by sha1(genome + photo + seed): rebuilding with
an unchanged genome is instant, editing the genome rebuilds only its pair.
"""

import hashlib
import json
import logging
import re
import shutil
import tempfile
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
import sys  # noqa: E402

sys.path.insert(0, str(ROOT))

from engine.inkmap import ink_map, pen_width_mm    # noqa: E402
from engine.modules import MODULES                 # noqa: E402
from engine.humanize import humanize               # noqa: E402
from engine.tonemod import tone_gate               # noqa: E402

log = logging.getLogger("review")

OUT = ROOT / "runs" / "review"
IMG = OUT / "imgs"

# The active hand loop: (genome, photo, seed). One deliberate pair at a
# time — this list IS the "what's new" answer.
ACTIVE = [
    ("genomes/hand_peak.json", "tests/fixtures/peak_src.png", 42),
]

PENS = tomllib.loads((ROOT / "pens.toml").read_text())


def _hex_bgr(h):
    h = h.lstrip("#")
    return (int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16))


def _save(name: str, img: np.ndarray) -> str:
    IMG.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(IMG / name), img)
    return f"imgs/{name}"


def _gray_png(a: np.ndarray) -> np.ndarray:
    return np.clip(a * 255.0, 0, 255).astype(np.uint8)


def _raster(layers: dict, page, width_px: int) -> np.ndarray:
    """Rasterize polyline layers in pen colors on white (fast preview —
    the pipeline's final render uses the real SVG->PNG path instead)."""
    s = width_px / page.width_mm
    h = int(round(page.height_mm * s))
    img = np.full((h, width_px, 3), 255, np.uint8)
    for pen, lines in layers.items():
        col = _hex_bgr(PENS.get(pen, {"color": "#000"})["color"])
        t = max(int(round(pen_width_mm(pen) * s)), 1)
        pts = [np.round(np.asarray(ln) * s).astype(np.int32)
               for ln in lines if len(ln) >= 2]
        if pts:
            cv2.polylines(img, pts, False, col, t, cv2.LINE_AA)
    return img


def _mass_colors(ids):
    cols = {}
    for i in ids:
        hue = int((i * 0.61803398875 % 1.0) * 179)
        c = cv2.cvtColor(np.uint8([[[hue, 150, 220]]]),
                         cv2.COLOR_HSV2BGR)[0, 0]
        cols[i] = tuple(int(v) for v in c)
    return cols


def _label_at_centroid(img, mask, text, scale=0.55):
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return
    cv2.putText(img, text, (int(xs.mean()) - 18, int(ys.mean()) + 4),
                cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 3,
                cv2.LINE_AA)
    cv2.putText(img, text, (int(xs.mean()) - 18, int(ys.mean()) + 4),
                cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 1, cv2.LINE_AA)


def _boundaries(labels):
    k = np.ones((3, 3), np.uint8)
    return (cv2.morphologyEx(labels.astype(np.int32).astype(np.float32),
                             cv2.MORPH_GRADIENT, k) > 0)


# -------------------------------------------------------------- strokes ----
STROKE_SPOT_MM = 3.5  # footprint for spot/dab kinds


def build_strokes() -> dict:
    """L0 of the vocabulary ladder: the full stroke alphabet grouped by
    family. Each cell shows THREE seeds of the same kind — intrinsic
    variation is part of what a kind is. Drawn clean at real pen scale
    (humanize is a downstream pass and deliberately absent here)."""
    from engine.strokes import FAMILY, STROKES, stroke as mk

    scale = 12.0  # px per mm
    ink = (26, 26, 26)

    def draw(img, gesture, x_mm, y_mm):
        for pts in gesture:
            pp = np.stack([pts[:, 0] * scale + x_mm * scale,
                           y_mm * scale - pts[:, 1] * scale], 1)
            cv2.polylines(img, [np.round(pp).astype(np.int32)], False,
                          ink, 2, cv2.LINE_AA)

    families = []
    for fam, kinds in FAMILY.items():
        cells = []
        for kind in kinds:
            ln = STROKE_SPOT_MM if fam == "spot" \
                or kind in ("dot", "spiral") else 18.0
            gs = [mk(kind, ln, {}, np.random.default_rng(100 + k))
                  for k in range(3)]
            # auto row layout from real extents — kinds keep true mm
            # scale but tall gestures get the room they need
            his, los = [], []
            for g in gs:
                ys = np.concatenate([p[:, 1] for p in g])
                his.append(ys.max()); los.append(ys.min())
            y = 1.2
            h_rows = []
            for hi, lo in zip(his, los):
                y += hi + 0.8
                h_rows.append(y)
                y += -lo + 0.8
            img = np.full((int((y + 1.2) * scale), 300, 3), 255, np.uint8)
            for g, ry in zip(gs, h_rows):
                draw(img, g, 3.0, ry)
            cells.append({"kind": kind,
                          "doc": (STROKES[kind].__doc__ or ""
                                  ).split("\n")[0],
                          "img": _save(f"stroke_{kind}.png", img)})
        families.append({"family": fam, "kinds": cells})
    total = sum(len(f["kinds"]) for f in families)
    return {"families": families, "total": total}


# ---------------------------------------------------------------- marks ----
SWATCH_MM = 40.0
CELL = 300


def _swatch_ctx(gray):
    from engine.page import Page
    n = gray.shape[0]
    page = Page(SWATCH_MM, SWATCH_MM, 0.0, SWATCH_MM / n, 0.0, 0.0)
    return {"gray": gray, "orientation":
            np.full_like(gray, np.deg2rad(52.0)),
            "coherence": np.ones_like(gray),
            "edge_map": np.zeros(gray.shape, bool),
            "tone_bands": [np.ones(gray.shape, bool)],
            "page": page, "normals": None}


def _swatch_render(lines, page, pen="black03") -> np.ndarray:
    img = np.full((CELL, CELL, 3), 255, np.uint8)
    s = CELL / SWATCH_MM
    t = max(int(round(pen_width_mm(pen) * s)), 1)
    col = _hex_bgr(PENS[pen]["color"])
    pts = [np.round(np.asarray(ln) * s).astype(np.int32)
           for ln in lines if len(ln) >= 2]
    if pts:
        cv2.polylines(img, pts, False, col, t, cv2.LINE_AA)
    return img


def build_marks() -> dict:
    """Flat swatch + measured coverage + gradient tone_gate response for
    every calibrated spec, plus a few uncalibrated modules for the eye."""
    import calibrate
    from shapely.geometry import Polygon

    specs = list(calibrate.SPECS)
    for extra in (("fan_hatch", {"spacing_mm": 0.8}),
                  ("fan_hatch", {"spacing_mm": 0.55}),
                  ("patch_hatch", {"spacing_mm": 0.8}),
                  ("contour_hatch", {"spacing_mm": 0.8})):
        if not any(m == extra[0] and p == extra[1] for m, p in specs):
            specs.append(extra)

    n = int(SWATCH_MM * 4)
    flat = _swatch_ctx(np.full((n, n), 0.35, np.float32))
    grad_gray = np.tile(np.linspace(0.06, 0.94, n,
                                    dtype=np.float32), (n, 1))
    grad = _swatch_ctx(grad_gray)
    page = flat["page"]
    mask = np.ones((n, n), bool)
    pad = 8
    corners = np.array([[pad, pad], [n - pad, pad],
                        [n - pad, n - pad], [pad, n - pad]], float)
    region = Polygon(page.px_to_mm(corners))

    rows = []
    for i, (module, params) in enumerate(specs):
        try:
            rng = np.random.default_rng(7)
            lines = MODULES[module](mask, region, flat, params, rng)
            lines = humanize(lines, 7, {"wobble_amp_mm": 0.12})
            cov = ink_map({"black03": lines}, page, (n, n), blur_mm=1.4)
            inner = float(cov[n // 6:-n // 6, n // 6:-n // 6].mean())
            img = _save(f"mark_{module}_{i}.png",
                        _swatch_render(lines, page))
            rng = np.random.default_rng(7)
            glines = MODULES[module](mask, region, grad, params, rng)
            glines = tone_gate(glines, grad,
                               {"low": 0.06, "high": 0.9, "seg_mm": 3.0},
                               np.random.default_rng(11))
            glines = humanize(glines, 7, {"wobble_amp_mm": 0.12})
            gimg = _save(f"mark_{module}_{i}_grad.png",
                         _swatch_render(glines, page))
            rows.append({"module": module, "params": params,
                         "coverage": round(inner, 3),
                         "img": img, "img_grad": gimg})
        except Exception as e:  # a module that can't run on synthetic ctx
            log.warning("marks: %s %s failed: %s", module, params, e)
            rows.append({"module": module, "params": params,
                         "coverage": None, "img": None, "img_grad": None,
                         "error": str(e)})

    table = []
    mp = ROOT / "marks.json"
    if mp.exists():
        table = json.loads(mp.read_text())
    return {"rows": rows, "calibration_table": table}


# ------------------------------------------------------------- pipeline ----
_CACHE_VER = "2"  # bump to invalidate cached pair builds after code changes


def build_pair(genome_path: str, photo: str, seed: int) -> dict:
    gp = ROOT / genome_path
    return build_pair_from(json.loads(gp.read_text()), gp.stem, photo,
                           seed, src=genome_path)


def build_pair_from(genome: dict, name: str, photo: str, seed: int,
                    src: str | None = None) -> dict:
    """Pipeline stages + translation check for one (genome, photo, seed).
    Cached by content hash — unchanged pairs cost one JSON read."""
    pp = ROOT / photo
    h = hashlib.sha1()
    h.update(_CACHE_VER.encode())
    h.update(json.dumps(genome, sort_keys=True).encode())
    h.update(str(photo).encode())
    h.update(str(seed).encode())
    tag = h.hexdigest()[:12]
    cache = IMG / f"pair_{name}_{tag}.json"
    if cache.exists():
        return json.loads(cache.read_text())

    log.info("pipeline: rendering %s x %s (seed %d)", name, pp.name, seed)
    from engine.render import _structure_ctx, render
    from engine.svgout import render_png, write_svg
    layers, page = render(genome, seed, photo_path=str(pp))
    ctx = _structure_ctx(genome, str(pp))
    shape = ctx["gray"].shape

    stages = []

    def stage(key, title, note, img_path):
        stages.append({"key": key, "title": title, "note": note,
                       "img": img_path})

    # 1. source photo (+ paired target ink if present)
    ph = cv2.imread(str(pp))
    ph = cv2.resize(ph, (900, int(900 * ph.shape[0] / ph.shape[1])))
    stage("photo", "source photo", "what we are translating",
          _save(f"{tag}_photo.png", ph))
    ink_ref = pp.with_name(pp.name.replace("_src", "_ink"))
    if ink_ref.exists() and ink_ref != pp:
        ik = cv2.imread(str(ink_ref))
        ik = cv2.resize(ik, (900, int(900 * ik.shape[0] / ik.shape[1])))
        stage("ink_ref", "target ink (reference)",
              "the paired human ink drawing — the bar to clear",
              _save(f"{tag}_inkref.png", ik))

    # 2. working tone (post tone_source/relight)
    stage("gray", "working tone", "ctx['gray'] after any relight mix — "
          "the value field every module reads",
          _save(f"{tag}_gray.png", _gray_png(ctx["gray"])))

    # 3. tone bands
    tb = ctx["tone_bands"]
    bands = np.zeros(shape, np.uint8)
    for i, b in enumerate(tb):
        bands[b] = int(255 - i * (215 / max(len(tb) - 1, 1)))
    stage("bands", f"tone bands (n={len(tb)})",
          "quantized value steps, band 0 lightest",
          _save(f"{tag}_bands.png", bands))

    # 4. orientation field (hue = angle, brightness = coherence)
    th, coh = ctx["orientation"], ctx["coherence"]
    hsv = np.stack([((th % np.pi) / np.pi * 179).astype(np.uint8),
                    np.full(shape, 200, np.uint8),
                    (80 + coh * 175).astype(np.uint8)], -1)
    stage("orient", "orientation field",
          "stroke direction (hue = angle, bright = coherent); source: "
          + str(genome.get("source", {}).get("params", {})
                .get("orientation_source", "tone gradients")),
          _save(f"{tag}_orient.png", cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)))

    # 5. normals + variance
    if ctx.get("normals") is not None:
        nrm = ((ctx["normals"] + 1) / 2 * 255).astype(np.uint8)
        stage("normals", "surface normals (Marigold, frozen)",
              "geometry the strokes hang on",
              _save(f"{tag}_normals.png",
                    cv2.cvtColor(nrm, cv2.COLOR_RGB2BGR)))
        if ctx.get("normal_var") is not None:
            vv = cv2.applyColorMap(_gray_png(ctx["normal_var"]),
                                   cv2.COLORMAP_VIRIDIS)
            stage("nvar", "normal variance",
                  "rough (trees/rubble) vs clean faces — texture gate",
                  _save(f"{tag}_nvar.png", vv))

    # 6. scene plan overlay (frozen decomposition)
    sc = pp.with_name(pp.stem + ".scene.png")
    if sc.exists():
        stage("scene", "scene plan (SAM + depth, frozen)",
              "true object regions; tags are id:d<depth>t<tone>",
              f"imgs/{sc.name}" if shutil.copy(sc, IMG / sc.name) else "")

    plan = genome.get("plan")
    rows = []
    zones_table = []
    if plan:
        from engine.plan import compile_plan
        zones = compile_plan(plan, ctx)
        masses, levels = ctx["plan_masses"], ctx["plan_levels"]
        targets = plan.get("assign", {}).get("targets", [])
        ids = [i for i in np.unique(masses) if i != 0]
        cols = _mass_colors(ids)

        # 7. masses
        mimg = np.full((*shape, 3), 245, np.uint8)
        for i in ids:
            mimg[masses == i] = cols[i]
        mimg[_boundaries(masses)] = (255, 255, 255)
        for i in ids:
            _label_at_centroid(mimg, masses == i,
                               f"{i}:L{levels.get(i, 0)}")
        stage("masses", f"plan masses ({len(ids)})",
              "watershed + RAG merge over the crease field; the shapes "
              "we commit to. label = mass_id:Level",
              _save(f"{tag}_masses.png", mimg))

        # 8. the promise — each mass filled with its level's target value
        prom = np.full(shape, 255, np.uint8)
        for i in ids:
            lvl = levels.get(i, 0)
            t = targets[lvl] if lvl < len(targets) else 0.0
            prom[masses == i] = int(255 * (1 - t))
        stage("promise", "committed levels (the plan's promise)",
              f"each mass at its target coverage {targets} — compare "
              "directly against the final render at thumbnail size",
              _save(f"{tag}_promise.png", prom))

        for z in zones:
            zones_table.append({
                "zone": z.get("name"),
                "keyline_mm": z.get("keyline_mm", 0),
                "stack": [{"module": b.get("module"),
                           "pen": b.get("pen"),
                           "params": b.get("params", {})}
                          for b in (z.get("base") or [])] or "(band stack)"})

    # 9. per-pen layers
    for pen, lines in layers.items():
        stage(f"pen_{pen}", f"layer: {pen} ({len(lines)} strokes)",
              "one plotter pass", _save(f"{tag}_pen_{pen}.png",
                                        _raster({pen: lines}, page, 900)))

    # 10. final render — the real SVG->PNG path
    final_png = IMG / f"{tag}_final.png"
    with tempfile.NamedTemporaryFile(suffix=".svg") as tf:
        write_svg(layers, PENS, page, tf.name)
        render_png(tf.name, str(final_png), width_px=1400)
    stage("final", "final render", "SVG exactly as the plotter sees it",
          f"imgs/{final_png.name}")

    # 11. ink delivered vs promised (translation)
    cov = ink_map(layers, page, shape)
    heat = cv2.applyColorMap(_gray_png(cov), cv2.COLORMAP_INFERNO)
    stage("ink", "ink delivered (coverage map)",
          "engine measuring its own drawing (inkmap)",
          _save(f"{tag}_ink.png", heat))

    if plan:
        verd = np.full((*shape, 3), 245, np.uint8)
        vcol = {"ok": (90, 170, 60), "UNDER": (60, 160, 240),
                "OVER": (60, 60, 220), "INK ON PAPER-LEVEL": (200, 60, 200)}
        for mid, lvl in sorted(levels.items(), key=lambda kv: kv[1]):
            m = masses == mid
            if m.sum() < 200:
                continue
            t = targets[lvl] if lvl < len(targets) else 0.0
            a = float(cov[m].mean())
            ratio = a / t if t > 0.01 else float("nan")
            verdict = "ok"
            if t > 0.01 and not 0.6 <= ratio <= 1.6:
                verdict = "UNDER" if ratio < 0.6 else "OVER"
            if t <= 0.01 and a > 0.08:
                verdict = "INK ON PAPER-LEVEL"
            rows.append({"mass": int(mid), "level": int(lvl),
                         "target": round(float(t), 3),
                         "achieved": round(a, 3),
                         "ratio": None if t <= 0.01 else round(ratio, 2),
                         "verdict": verdict})
            verd[m] = vcol[verdict]
            _label_at_centroid(verd, m, f"{mid}:{verdict}", 0.5)
        verd[_boundaries(masses)] = (255, 255, 255)
        stage("verdict", "translation verdict map",
              "green ok / amber UNDER / red OVER / magenta ink-on-paper",
              _save(f"{tag}_verdict.png", verd))

    data = {"name": name, "genome_path": src, "photo": photo,
            "seed": seed, "hash": tag, "stages": stages,
            "zones": zones_table, "translation": rows,
            "genome": genome,
            "final_img": f"imgs/{final_png.name}"}
    cache.write_text(json.dumps(data, indent=1))
    return data


# ------------------------------------------------------------- abstract ----
def _grid_sheet(seed: int, w_mm=190.0, h_mm=130.0, outline=True):
    """Polygonal tiling, every cell a random committed angle, honoring
    the invariant the ghost-square bug taught: ADJACENT CELLS NEVER
    SHARE AN ANGLE (same angle + shifted phase = fake seam)."""
    from engine.hatch import fixed_hatch
    from engine.regions import poly_grid, region_outline

    rng = np.random.default_rng(seed)
    cells, neighbors = poly_grid(w_mm, h_mm, rng)
    ANGLES = [-75, -60, -45, -30, -15, 0, 15, 30, 45, 60, 75, 90]
    angle = [None] * len(cells)
    for i in range(len(cells)):
        banned = {angle[j] for j in neighbors[i] if angle[j] is not None}
        pool = [a for a in ANGLES if a not in banned]
        angle[i] = float(pool[int(rng.integers(len(pool)))])
    hatch, rings = [], []
    for i, cell in enumerate(cells):
        hatch += fixed_hatch(cell, angle[i], 1.15, rng,
                             spacing_jitter=0.04)
        if outline:
            rings += region_outline(cell)
    return {"black03": hatch + rings}


def _aniso_sheet(seed: int, mix: bool, w_mm=190.0, h_mm=130.0):
    """The reference-artist patch geometry: elongated-along-direction
    cells over a coherent drifting field, committed angles, NO outlines.
    mix=True adds sparse tonal variety (occasional bare / tight cells)."""
    from engine.hatch import fixed_hatch
    from engine.regions import aniso_mesh

    rng = np.random.default_rng(seed)
    cells, neighbors, thetas = aniso_mesh(w_mm, h_mm, rng)
    angle = [None] * len(cells)
    hatch = []
    for i, c in enumerate(cells):
        if c is None or c.is_empty:
            continue
        ang = round(np.degrees(thetas[i]) / 15) * 15.0
        for j in neighbors[i]:
            if angle[j] is not None and \
                    abs(((ang - angle[j] + 90) % 180) - 90) < 10:
                ang += float(rng.choice([-1, 1])) * 15.0
                break
        angle[i] = ang
        sp = 1.15
        if mix:
            sp = float(rng.choice([0.0, 0.8, 1.15, 1.15, 1.7],
                                  p=[.07, .16, .38, .25, .14]))
            if sp == 0.0:
                continue
        hatch += fixed_hatch(c, ang, sp, rng, spacing_jitter=0.05)
    return {"black03": hatch}


def _objects_sheet(seed: int, w_mm=190.0, h_mm=130.0):
    """Grouping: patches -> OBJECTS -> separation treatments. A sky-like
    background field plus overlapping objects, each filled with its own
    aniso patch field (interior boundaries stay emergent), each carrying
    one separation gene at its silhouette:
      sliver          near object casts a white aura into the background
      outline         comic bold edge on the visible silhouette
      sliver+outline  both
      none            butts directly (control)"""
    from shapely.geometry import box

    from engine.hatch import fixed_hatch
    from engine.regions import (aniso_mesh, make_shape, object_scene,
                                region_outline)

    rng = np.random.default_rng(seed)
    objs = [box(8, 8, w_mm - 8, h_mm - 8)]   # background sky
    genes = [("none", 0.0)]
    # objects ALWAYS separate (user: bare butting reads as a bug at the
    # object level — that register belongs to interior patches only)
    GENES = [("sliver", 1.4), ("sliver", 1.4), ("outline", 0.0),
             ("sliver+outline", 1.4), ("sliver", 1.4), ("outline", 0.0)]
    page_box = box(8, 8, w_mm - 8, h_mm - 8)
    for gi in range(6):
        c = (rng.uniform(30, w_mm - 30), rng.uniform(28, h_mm - 28))
        p = make_shape("poly", c, rng.uniform(45, 92), rng,
                       irregularity=0.45).intersection(page_box)
        objs.append(p)
        genes.append(GENES[gi])
    pairs = object_scene(objs, [a for _g, a in genes])

    hatch, bold = [], []
    # background: the artist's sky — long near-horizontal rules
    hatch += fixed_hatch(pairs[0][0], 2.0, 1.15, rng, spacing_jitter=0.05)
    for i in range(1, len(objs)):
        fill, visible = pairs[i]
        if fill.is_empty:
            continue
        bias = rng.uniform(0, 180)
        cells, neighbors, thetas = aniso_mesh(w_mm, h_mm, rng,
                                              n_parents=60)
        angle = [None] * len(cells)
        covered = None
        for ci, cell in enumerate(cells):
            if cell is None:
                continue
            cc = cell.intersection(fill)
            if cc.is_empty:
                continue
            ang = round((np.degrees(thetas[ci]) + bias) / 15) * 15.0
            for j in neighbors[ci]:
                if angle[j] is not None and \
                        abs(((ang - angle[j] + 90) % 180) - 90) < 10:
                    ang += float(rng.choice([-1, 1])) * 15.0
                    break
            angle[ci] = ang
            hatch += fixed_hatch(cc, ang, 1.15, rng, spacing_jitter=0.05)
            covered = cc if covered is None \
                else covered.union(cc)
        # catch-all: mesh cells lost to clipping leave bare holes.
        # ERODE first — hairline slivers between cells otherwise hatch
        # into errant single strokes (user-spotted bug)
        rest = fill if covered is None else fill.difference(covered)
        rest = rest.buffer(-0.55).buffer(0.5)
        for part in getattr(rest, "geoms", [rest]):
            if not part.is_empty and part.area > 3.0:
                hatch += fixed_hatch(part, round(bias / 15) * 15.0, 1.15,
                                     rng, spacing_jitter=0.05)
        # outline follows the FILL edge (aura pullback included) — an
        # outline at the raw occlusion edge floats in the white sliver
        if "outline" in genes[i][0] and not fill.is_empty:
            for ring in region_outline(fill):
                bold.append(ring)
                bold.append(ring + np.array([0.16, 0.11]))
    layers = {"black03": hatch}
    if bold:
        layers["black05"] = bold
    return layers


def _mesh_sheet(photo: str, seed: int, outline: bool,
                w_mm=130.0, h_mm=190.0, n_seeds=230):
    """MESHIFY: Voronoi mesh over a photo as if it were a 3D surface —
    seed density from detail (edges + darkness), per-cell hatch ANGLE
    from the normals field (fall line — the 3D shading), per-cell
    SPACING from tone (lightest cells stay bare paper). Neighbor cells
    are nudged apart when angles nearly collide (ghost-seam invariant)."""
    import shapely

    from engine.hatch import fixed_hatch
    from engine.regions import region_outline, voronoi_mesh
    from engine.scene import load_normals, normals_field

    rng = np.random.default_rng(seed)
    pp = ROOT / photo
    bgr = cv2.imread(str(pp))
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    H, W = gray.shape
    # cover-fit page mm -> image px
    s = max(W / (w_mm - 16), H / (h_mm - 16))

    def to_px(xy):
        return (np.clip((xy[..., 0] - 8) * s, 0, W - 1),
                np.clip((xy[..., 1] - 8) * s, 0, H - 1))

    nrm = load_normals(str(pp), gray.shape)
    if nrm is not None:
        theta, _coh, _var = normals_field(nrm, 1 / s, smooth_mm=6.0)
    else:
        from bench.measure import orientation_field
        theta, _ = orientation_field(gray, sigma_px=8)
    from engine.scene import load_semantic
    sem = load_semantic(str(pp), gray.shape)
    sky = None
    if sem is not None:
        ids = [i for i, n in sem["names"].items() if "sky" in n.lower()]
        sky = np.isin(sem["labels"], ids)
    edge = cv2.GaussianBlur(np.hypot(
        cv2.Sobel(cv2.GaussianBlur(gray, (0, 0), 3), cv2.CV_32F, 1, 0),
        cv2.Sobel(cv2.GaussianBlur(gray, (0, 0), 3), cv2.CV_32F, 0, 1)),
        (0, 0), 4)
    edge /= edge.max() + 1e-9

    seeds = []
    while len(seeds) < n_seeds:
        p = np.array([rng.uniform(8, w_mm - 8), rng.uniform(8, h_mm - 8)])
        xi, yi = to_px(p)
        d = 0.25 + 1.4 * edge[int(yi), int(xi)] \
            + 0.55 * (1 - gray[int(yi), int(xi)])
        if rng.uniform() < d / 2.2:
            seeds.append(p)
    cells, neighbors = voronoi_mesh(w_mm, h_mm, np.array(seeds))

    SPACINGS = [None, 2.3, 1.5, 1.0]  # tone levels light -> dark
    angle = [None] * len(cells)
    hatch, rings = [], []
    order = [i for i in range(len(cells)) if cells[i] is not None]
    for i in order:
        c = cells[i]
        k = 22
        minx, miny, maxx, maxy = c.bounds
        xs = rng.uniform(minx, maxx, k)
        ys = rng.uniform(miny, maxy, k)
        inside = shapely.contains_xy(c, xs, ys)
        if not inside.any():
            continue
        px, py = to_px(np.stack([xs[inside], ys[inside]], 1))
        if sky is not None and \
                sky[py.astype(int), px.astype(int)].mean() > 0.5:
            continue  # sky stays bare paper — the surface is the subject
        g = float(gray[py.astype(int), px.astype(int)].mean())
        t2 = 2 * theta[py.astype(int), px.astype(int)]
        ang = float(np.degrees(0.5 * np.arctan2(np.sin(t2).mean(),
                                                np.cos(t2).mean())))
        ang = round(ang / 15) * 15.0
        for j in neighbors[i]:
            if angle[j] is not None and \
                    abs(((ang - angle[j] + 90) % 180) - 90) < 10:
                ang += float(rng.choice([-1, 1])) * 15.0
                break
        angle[i] = ang
        lvl = int(np.clip(np.digitize(1 - g, [0.32, 0.55, 0.75]), 0, 3))
        sp = SPACINGS[lvl]
        if sp is not None:
            hatch += fixed_hatch(c, ang, sp, rng, spacing_jitter=0.05)
        if outline:
            rings += region_outline(c)
    layers = {"black03": hatch + rings}
    return layers, bgr


def _mesh_objects_sheet(photo: str, seed: int, w_mm=130.0, h_mm=190.0):
    """mesh_peak with the FULL grammar: objects from the frozen scene
    plan (depth-ordered SAM regions, silhouettes simplified to committed
    polygons), sky as a ruled field that YIELDS a sliver around the
    land (the reference edge), per-object aniso fills clipped at form
    boundaries, per-cell angle from normals, tone-motivated density
    (bare lights / tight darks)."""
    import shapely
    from shapely.geometry import Polygon, box

    from engine.hatch import fixed_hatch
    from engine.regions import aniso_mesh, object_scene
    from engine.scene import (load_normals, load_scene, load_semantic,
                              normals_field)

    rng = np.random.default_rng(seed)
    pp = ROOT / photo
    bgr = cv2.imread(str(pp))
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    H, W = gray.shape
    s = max(W / (w_mm - 16), H / (h_mm - 16))  # px per mm

    def to_px(xy):
        return (np.clip((xy[..., 0] - 8) * s, 0, W - 1),
                np.clip((xy[..., 1] - 8) * s, 0, H - 1))

    nrm = load_normals(str(pp), gray.shape)
    theta, _c, _v = normals_field(nrm, 1 / s, smooth_mm=6.0)
    sem = load_semantic(str(pp), gray.shape)
    sky_ids = [i for i, n in sem["names"].items() if "sky" in n.lower()]
    sky_mask = np.isin(sem["labels"], sky_ids)
    scene = load_scene(str(pp), gray.shape)

    page_box = box(8, 8, w_mm - 8, h_mm - 8)

    def mask_to_poly(mask, eps_mm=1.1):
        m = cv2.dilate(mask.astype(np.uint8), np.ones((3, 3), np.uint8))
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL,
                                 cv2.CHAIN_APPROX_SIMPLE)
        parts = []
        for c in cs:
            if cv2.contourArea(c) < (2.5 * s) ** 2:
                continue
            ap = cv2.approxPolyDP(c, eps_mm * s, True)[:, 0, :]
            if len(ap) < 3:
                continue
            p = Polygon(ap / s + 8)
            if not p.is_valid:
                p = p.buffer(0)
            parts.append(p)
        if not parts:
            return None
        from shapely.ops import unary_union
        return unary_union(parts).intersection(page_box)

    # objects: sky first (farthest), then scene regions far -> near
    regs = sorted(scene["regions"], key=lambda r: r["depth_rank"])
    objs, auras, kinds = [], [], []
    skyp = mask_to_poly(sky_mask)
    if skyp is not None:
        objs.append(skyp)
        auras.append(0.0)
        kinds.append("sky")
    for r in regs:
        if r["area_frac"] < 0.02:
            continue
        mask = (scene["labels"] == r["id"]) & ~sky_mask
        if mask.mean() < 0.01:
            continue
        p = mask_to_poly(mask)
        if p is None or p.is_empty:
            continue
        objs.append(p)
        auras.append(1.2)
        kinds.append("land")
    pairs = object_scene(objs, auras)

    hatch = []
    for i, (fill, _vis) in enumerate(pairs):
        if fill.is_empty:
            continue
        if kinds[i] == "sky":
            hatch += fixed_hatch(fill, 2.0, 1.15, rng,
                                 spacing_jitter=0.05)
            continue
        cells, neighbors, _th = aniso_mesh(
            w_mm, h_mm, rng,
            n_parents=int(np.clip(fill.area / 130, 14, 110)))
        angle = [None] * len(cells)
        covered = None
        for ci, cell in enumerate(cells):
            if cell is None:
                continue
            cc = cell.intersection(fill)
            if cc.is_empty:
                continue
            minx, miny, maxx, maxy = cc.bounds
            xs = rng.uniform(minx, maxx, 20)
            ys = rng.uniform(miny, maxy, 20)
            ins = shapely.contains_xy(cc, xs, ys)
            if not ins.any():
                continue
            px, py = to_px(np.stack([xs[ins], ys[ins]], 1))
            g = float(gray[py.astype(int), px.astype(int)].mean())
            t2 = 2 * theta[py.astype(int), px.astype(int)]
            ang = float(np.degrees(0.5 * np.arctan2(
                np.sin(t2).mean(), np.cos(t2).mean())))
            ang = round(ang / 15) * 15.0
            for j in neighbors[ci]:
                if angle[j] is not None and \
                        abs(((ang - angle[j] + 90) % 180) - 90) < 10:
                    ang += float(rng.choice([-1, 1])) * 15.0
                    break
            angle[ci] = ang
            if g > 0.80:
                covered = cc if covered is None else covered.union(cc)
                continue  # lit snow stays paper
            sp = 0.8 if g < 0.38 else 1.15
            hatch += fixed_hatch(cc, ang, sp, rng, spacing_jitter=0.05)
            covered = cc if covered is None else covered.union(cc)
        rest = fill if covered is None else fill.difference(covered)
        rest = rest.buffer(-0.55).buffer(0.5)
        for part in getattr(rest, "geoms", [rest]):
            if not part.is_empty and part.area > 3.0:
                hatch += fixed_hatch(part, 45.0, 1.15, rng,
                                     spacing_jitter=0.05)
    return {"black03": hatch}, bgr


def build_abstract() -> dict:
    """The faithful-migration test suite (engine/gen1.py + regions.py):
    prove gen1's full capability in gen2 before building past it."""
    from engine.gen1 import drop_shapes, fixed_scenario, scene_layers
    from engine.page import Page
    from engine.svgout import write_svg

    svg_dir = OUT / "svg"
    svg_dir.mkdir(parents=True, exist_ok=True)
    sheets = []

    def emit(name, layers, w_mm, h_mm, note):
        page = Page(w_mm, h_mm, 0.0, w_mm / 1600, 0.0, 0.0)
        img = _raster(layers, page, 1600)
        write_svg(layers, PENS, page, str(svg_dir / f"{name}.svg"))
        sheets.append({"name": name, "note": note,
                       "paths": sum(len(v) for v in layers.values()),
                       "svg": f"svg/{name}.svg",
                       "img": _save(f"abstract_{name}.png", img)})

    # 1. fixed scenario — the original's own regression test, ported
    polys, mats = fixed_scenario()
    emit("fixed_scenario", scene_layers(polys, mats,
                                        np.random.default_rng(0)),
         115.0, 162.0, "gen1 create_fixed_shape_scenario verbatim — "
         "incl. same-material overlaps hatching continuously")

    # 2-3. random drop, original primitives — five materials, five
    # distinct committed angles, one spacing, bold union outline
    for seed in (1, 2):
        rng = np.random.default_rng(seed)
        polys, mats = drop_shapes(190.0, 130.0, rng)
        emit(f"drop_s{seed}", scene_layers(polys, mats, rng),
             190.0, 130.0, "gen1 random mode faithful: grid drop, "
             "size multipliers, materials 0-4 = distinct single angles")

    # 4. drop with polygons joining the primitive set
    rng = np.random.default_rng(3)
    polys, mats = drop_shapes(
        190.0, 130.0, rng,
        kinds=("circle", "square", "triangle", "poly", "poly"))
    emit("drop_poly", scene_layers(polys, mats, rng),
         190.0, 130.0, "same machinery, irregular 4-7-gons added")

    # 5-6. polygon grid, per-cell random angles, no-neighbor-repeat
    for seed in (1, 2):
        emit(f"grid_s{seed}", _grid_sheet(seed), 190.0, 130.0,
             "gapless jittered tiling + merges; adjacent cells never "
             "share an angle")
    for seed in (1, 2):
        emit(f"grid_noline_s{seed}", _grid_sheet(seed, outline=False),
             190.0, 130.0, "the same tiling, NO outlines — cells "
             "separate by angle contrast alone")

    # anisotropic patch fields — the reference cell geometry: patches
    # elongated along their own stroke direction, coherent drift
    # NOTE (user, 2026-07-21): random per-cell spacing mix reads
    # terrible — density must be MOTIVATED (form/shadow), not sprinkled.
    # Uniform density is this style's baseline; mix mode stays off.
    for seed in (1, 2):
        emit(f"aniso_s{seed}", _aniso_sheet(seed, mix=False),
             190.0, 130.0, "cells stretched ALONG their hatch direction "
             "over a drifting field; emergent fold lines, no outlines")

    # objects: patch groups + separation treatments (sliver / outline)
    for seed in (1, 2):
        emit(f"objects_s{seed}", _objects_sheet(seed), 190.0, 130.0,
             "patch-filled OBJECTS over a sky field; per-object edge "
             "gene: white sliver (background yields), comic outline, "
             "both, or none")

    # 7. no-outline drop — like the original prints: overlapping objects
    # separate purely by angle contrast, zero outlines
    rng = np.random.default_rng(5)
    polys, mats = drop_shapes(
        190.0, 130.0, rng,
        kinds=("circle", "square", "triangle", "poly"))
    lay = scene_layers(polys, mats, rng)
    lay = {"black03": lay["black03"]}
    emit("drop_noline", lay, 190.0, 130.0,
         "no outline anywhere — separation by angle contrast alone")

    # 8-10. MESHIFY: image -> adaptive polygonal mesh -> shaded by the
    # surface; the _objects variant adds the full grammar (scene-plan
    # objects, sky sliver, form-clipped fills)
    variants = [("mesh_peak_clean", lambda: _mesh_sheet(
        "tests/fixtures/peak_src.png", 7, False)),
        ("mesh_peak_lines", lambda: _mesh_sheet(
            "tests/fixtures/peak_src.png", 7, True)),
        ("mesh_peak_objects", lambda: _mesh_objects_sheet(
            "tests/fixtures/peak_src.png", 7))]
    for name, fn in variants:
        layers, photo_bgr = fn()
        page = Page(130.0, 190.0, 0.0, 130.0 / 900, 0.0, 0.0)
        img = _raster(layers, page, 900)
        ph = cv2.resize(photo_bgr,
                        (int(img.shape[0] * photo_bgr.shape[1]
                             / photo_bgr.shape[0]), img.shape[0]))
        gapc = np.full((img.shape[0], 10, 3), 255, np.uint8)
        panel = np.concatenate([ph, gapc, img], 1)
        write_svg(layers, PENS, page, str(svg_dir / f"{name}.svg"))
        note = ("full grammar: scene-plan objects in depth order, ruled "
                "sky yielding a sliver, form-clipped aniso fills"
                if name.endswith("objects") else
                "meshify: Voronoi cells dense where detail lives; angle "
                "= normals fall-line, spacing = tone, lightest bare")
        sheets.append({"name": name, "note": note,
                       "paths": sum(len(v) for v in layers.values()),
                       "svg": f"svg/{name}.svg",
                       "img": _save(f"abstract_{name}.png", panel)})
    return {"sheets": sheets}


# ---------------------------------------------------------------- forms ----
def _raw_normal_sheet(photo: str, K: int = 10,
                      value_qs=(0.10, 0.30, 0.60),
                      angle_mode: str = "center",
                      dark_speckle: bool = False,
                      amp: float = 1.0,
                      curve_amp: float = 0.0):
    """PIXEL-TRUE posterize render — zero geometry cleanup, so the
    marigold's character (couloirs, jagged tree texture) survives.
    Per class: exact fall-line angle; value level from relit shade
    (paper-heavy); fine lines via 2x supersample."""
    from engine.scene import load_normals, load_semantic, relight

    pp = ROOT / photo
    bgr = cv2.imread(str(pp))
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    H, W = gray.shape
    nrm = load_normals(str(pp), (H, W))
    sem = load_semantic(str(pp), (H, W))
    sky = np.isin(sem["labels"],
                  [i for i, n in sem["names"].items()
                   if "sky" in n.lower()])
    land = ~sky
    ns = cv2.GaussianBlur(nrm, (0, 0), 3)
    feats = ns[land].reshape(-1, 3).astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-3)
    cv2.setRNGSeed(7)  # global-rng kmeans — seed per call (purity)
    _c, lab, ctr = cv2.kmeans(feats, K, None, crit, 4,
                              cv2.KMEANS_PP_CENTERS)
    cls = np.full((H, W), -1, np.int32)
    cls[land] = lab.ravel()

    best_az, best_c = 315.0, -2.0
    gl = gray[land]
    gl = (gl - gl.mean()) / (gl.std() + 1e-9)
    for az in range(0, 360, 30):
        sh = relight(nrm, float(az), 40.0)[land]
        sh = (sh - sh.mean()) / (sh.std() + 1e-9)
        c = float((sh * gl).mean())
        if c > best_c:
            best_az, best_c = float(az), c
    shade = relight(nrm, best_az, 40.0)
    qs = np.quantile(shade[land], list(value_qs))

    fx = -nrm[..., 0] * nrm[..., 1]   # gravity projected on surface:
    fy = 1.0 - nrm[..., 1] ** 2       # f = g - (g.n)n, g = (0,1,0)
    S = 2  # supersample
    out = np.full((H * S, W * S), 255, np.uint8)
    diag = int(np.hypot(H, W)) * S
    SP = {1: 15, 2: 10, 3: 6}  # spacing px at 2x, per level

    disp = None
    if curve_amp > 0:
        # shared low-frequency displacement field: every line in every
        # family bends the SAME gentle way, so curves flow while spacing
        # and quasi-parallelism survive (the artist's breathing lines)
        rng_d = np.random.default_rng(11)
        coarse = rng_d.standard_normal((H // 24 + 2, W // 24 + 2))
        coarse = cv2.GaussianBlur(coarse.astype(np.float32), (0, 0), 2.2)
        disp = cv2.resize(coarse, (W * S, H * S),
                          interpolation=cv2.INTER_CUBIC)
        disp *= curve_amp * S / (np.abs(disp).max() + 1e-9)

    def hatch_mask(mask, th, level):
        d = np.array([np.cos(th), np.sin(th)])
        nv = np.array([-d[1], d[0]])
        canvas = np.zeros((H * S, W * S), np.uint8)
        c0 = np.array([W * S / 2, H * S / 2])
        for off in range(-diag // 2, diag // 2, SP[level]):
            p = c0 + nv * off
            if disp is None:
                a = (p - d * diag).astype(int)
                b = (p + d * diag).astype(int)
                cv2.line(canvas, tuple(a), tuple(b), 255, 2, cv2.LINE_AA)
            else:
                ts = np.arange(-diag, diag, 14)
                pts = p[None] + d[None] * ts[:, None]
                xi = np.clip(pts[:, 0], 0, W * S - 1).astype(int)
                yi = np.clip(pts[:, 1], 0, H * S - 1).astype(int)
                pts = pts + nv[None] * disp[yi, xi][:, None]
                cv2.polylines(canvas, [np.round(pts).astype(np.int32)],
                              False, 255, 2, cv2.LINE_AA)
        mbig = cv2.resize(mask.astype(np.uint8), (W * S, H * S),
                          interpolation=cv2.INTER_NEAREST)
        out[(canvas > 127) & (mbig > 0)] = 0

    ang_of = {}
    if angle_mode == "shadow1":
        # the artist's move (user hypothesis): the WHOLE shadow face is
        # one committed plunge; the lit side is washed out to paper and
        # carries only rock speckle
        shadow = (shade < np.quantile(shade[land], 0.35)) & land
        t2 = 2 * np.arctan2(fy[shadow], fx[shadow])
        th = 0.5 * np.arctan2(np.sin(t2).mean(), np.cos(t2).mean())
        hatch_mask(shadow, float(th), 2)
        for k in range(K):
            ang_of[k] = float(th)
    else:
        for k in range(K):
            mask = cls == k
            if not mask.any():
                continue
            if angle_mode == "gravity":
                t2 = 2 * np.arctan2(fy[mask], fx[mask])
                th = 0.5 * np.arctan2(np.sin(t2).mean(),
                                      np.cos(t2).mean())
            elif angle_mode == "chiral":
                # TWO stroke families, the ridge as the flip (user):
                # keep each class's plunge MAGNITUDE from its fall line,
                # but the SIGN comes from which way the face points —
                # faces-left drains down-left, everything else
                # down-right. Density untouched; the ridge emerges from
                # direction alone.
                n = ctr[k]
                a = ((np.degrees(np.arctan2(n[1], n[0])) + 90) % 180) - 90
                m = abs(a)
                th = np.radians(m if n[0] >= 0 else 180 - m)
            else:
                n = ctr[k]
                th = np.arctan2(n[1], n[0])
            if amp != 1.0:
                # steepness EXAGGERATION (user): amplify each face's
                # deviation from horizontal — 45° becomes ~60°, near-
                # horizontal fields stay put. Not a global steepening.
                a = ((np.degrees(th) + 90) % 180) - 90
                a = np.sign(a) * min(90.0, abs(a) * amp)
                th = np.radians(a)
            ang_of[k] = float(th)
            level = 3 - int(np.digitize(float(shade[mask].mean()), qs))
            if level <= 0:
                continue
            hatch_mask(mask, th, level)
    if dark_speckle:
        # the artist's mid-slope punctuation: deepest shadow pockets get
        # L3 hatching regardless of class — texture the downslope
        deep = (shade < np.quantile(shade[land], 0.06)) & land
        deep = cv2.morphologyEx(deep.astype(np.uint8), cv2.MORPH_OPEN,
                                np.ones((2, 2), np.uint8)) > 0
        for k in range(K):
            m = deep & (cls == k)
            if m.sum() > 40:
                hatch_mask(m, ang_of.get(k, 1.2), 3)
    out = cv2.resize(out, (W, H), interpolation=cv2.INTER_AREA)
    cviz = np.full((H, W, 3), 245, np.uint8)
    for k in range(K):
        col = cv2.cvtColor(np.uint8([[[int((k * 0.618 % 1) * 179),
                                       150, 220]]]),
                           cv2.COLOR_HSV2BGR)[0, 0]
        cviz[cls == k] = col
    nviz = cv2.cvtColor(((nrm + 1) / 2 * 255).astype(np.uint8),
                        cv2.COLOR_RGB2BGR)
    gap = np.full((H, 12, 3), 255, np.uint8)
    return np.concatenate([nviz, gap, cviz, gap,
                           cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)], 1)


def _ridge_probe(photo: str):
    """'Ridge lines everywhere' (docs/ridges-research.md probe #1):
    multi-scale curvature of the normal map. Fold strength = extreme
    eigenvalue of sym(d(nx,ny)/d(x,y)); fold axis = its eigenvector's
    perpendicular; creases = thresholded+skeletonized strength ridges.
    Panels: strength | axis field | crease lines over the photo."""
    from skimage.morphology import skeletonize

    from engine.scene import load_normals, load_semantic

    pp = ROOT / photo
    bgr = cv2.imread(str(pp))
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    nrm = load_normals(str(pp), (H, W))
    sem = load_semantic(str(pp), (H, W))
    sky = np.isin(sem["labels"],
                  [i for i, n in sem["names"].items()
                   if "sky" in n.lower()])
    strength = np.zeros((H, W), np.float32)
    axis = np.zeros((H, W), np.float32)
    for sig in (2.0, 5.0, 10.0, 20.0):
        ns = cv2.GaussianBlur(nrm, (0, 0), sig)
        a = cv2.Sobel(ns[..., 0], cv2.CV_32F, 1, 0)
        d = cv2.Sobel(ns[..., 1], cv2.CV_32F, 0, 1)
        b = 0.5 * (cv2.Sobel(ns[..., 0], cv2.CV_32F, 0, 1)
                   + cv2.Sobel(ns[..., 1], cv2.CV_32F, 1, 0))
        half = np.sqrt(((a - d) / 2) ** 2 + b ** 2)
        lam = np.abs((a + d) / 2) + half
        s = sig * lam
        th = 0.5 * np.arctan2(2 * b, a - d) + np.pi / 2  # crease axis
        upd = s > strength
        strength[upd] = s[upd]
        axis[upd] = th[upd]
    strength[sky] = 0
    strength /= np.quantile(strength[~sky], 0.995) + 1e-9
    strength = np.clip(strength, 0, 1)

    p1 = cv2.applyColorMap((strength * 255).astype(np.uint8),
                           cv2.COLORMAP_INFERNO)
    hsv = np.stack([((axis % np.pi) / np.pi * 179).astype(np.uint8),
                    np.full((H, W), 200, np.uint8),
                    (strength * 255).astype(np.uint8)], -1)
    p2 = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    crease = strength > np.quantile(strength[~sky], 0.86)
    crease = cv2.morphologyEx(crease.astype(np.uint8), cv2.MORPH_CLOSE,
                              np.ones((3, 3), np.uint8))
    sk = skeletonize(crease > 0)
    sk = cv2.dilate(sk.astype(np.uint8), np.ones((2, 2), np.uint8)) > 0
    p3 = cv2.cvtColor((gray // 2 + 127).astype(np.uint8),
                      cv2.COLOR_GRAY2BGR)
    p3[sk] = (40, 40, 230)
    gap = np.full((H, 12, 3), 255, np.uint8)
    return np.concatenate([p1, gap, p2, gap, p3], 1)


def build_forms() -> dict:
    """The forming & angles arc (engine/formplan.py): photo -> form plan
    (committed level + angle per mass) -> patch-language render. The
    PLAN is shown as its own artifact — forming is judged before ink."""
    from engine.formplan import (build_normal_form_plan, normals_viz,
                                 plan_viz, render_form_plan)
    from engine.page import Page
    from engine.svgout import write_svg

    svg_dir = OUT / "svg"
    svg_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    # every config is PINNED (incl. value quantiles) — shared-code
    # changes must never mutate a variant the user kept as reference
    CFGS = (  # (suffix, k, blur, snap, spacing_scale, raster_px, qs)
        ("k6b2", 6, 2.0, 15.0, 1.0, 900, (0.45, 0.72, 0.9)),
        ("k6b2_v2", 6, 2.0, 15.0, 1.0, 900, (0.10, 0.30, 0.60)),
        ("k8b1_ref", 8, 1.2, 15.0, 1.0, 900, (0.45, 0.72, 0.9)),
        ("slope_fine", 10, 1.2, 0.0, 0.65, 1500, (0.10, 0.30, 0.60)),
    )
    arch = OUT / "experiments" / "forms"
    arch.mkdir(parents=True, exist_ok=True)
    for suffix, kk, blur, snap, spsc, rpx, qs in CFGS:
        photo = "tests/fixtures/peak_src.png"
        stem = f"{Path(photo).stem}_{suffix}"
        try:
            plan = build_normal_form_plan(str(ROOT / photo), k=kk,
                                          blur_mm=blur, snap_deg=snap,
                                          value_qs=qs)
        except Exception as e:
            log.warning("forms: %s failed: %s", stem, e)
            continue
        layers = render_form_plan(plan, np.random.default_rng(7),
                                  spacing_scale=spsc)
        page = Page(plan["w_mm"], plan["h_mm"], 0.0,
                    plan["w_mm"] / rpx, 0.0, 0.0)
        img = _raster(layers, page, rpx)
        hpx = img.shape[0]
        ph = cv2.resize(plan["bgr"], (int(hpx * plan["bgr"].shape[1]
                                          / plan["bgr"].shape[0]), hpx))
        pv = plan_viz(plan)
        pv = cv2.resize(pv, (int(hpx * pv.shape[1] / pv.shape[0]), hpx))
        nv = normals_viz(plan)
        nv = cv2.resize(nv, (int(hpx * nv.shape[1] / nv.shape[0]), hpx))
        gap = np.full((hpx, 10, 3), 255, np.uint8)
        panel = np.concatenate([nv, gap, pv, gap, img], 1)
        name = f"nforms_{stem}"
        write_svg(layers, PENS, page, str(svg_dir / f"{name}.svg"))
        # APPEND-ONLY archive: content-hashed copy of every panel ever
        # shown; a shown experiment can never be silently mutated again
        ok, buf = cv2.imencode(".png", panel)
        hh = hashlib.sha1(buf.tobytes()).hexdigest()[:8]
        apath = arch / f"{name}__{hh}.png"
        if not apath.exists():
            apath.write_bytes(buf.tobytes())
            log.info("forms archive: + %s", apath.name)
        history = [q.name for q in sorted(arch.glob(f"{name}__*.png"), key=lambda q: q.stat().st_mtime)]
        rows.append({
            "name": name, "svg": f"svg/{name}.svg",
            "n_forms": len(plan["forms"]),
            "levels": sorted({f["level"] for f in plan["forms"]}),
            "img": f"experiments/forms/{apath.name}",
            "history": [f"experiments/forms/{h}" for h in history]})

    # pixel-true raw posterize variants (no polygons) — append-only
    RAW = (("raw10", {}),
           ("raw10_steep", {"angle_mode": "gravity"}),
           ("raw10_steepdark", {"angle_mode": "gravity",
                                "dark_speckle": True}),
           ("raw_shadow1", {"angle_mode": "shadow1",
                            "dark_speckle": True}),
           ("raw10_ampdark", {"amp": 1.35, "dark_speckle": True}),
           ("raw_chiral", {"angle_mode": "chiral"}),
           ("raw_chiral_curve", {"angle_mode": "chiral",
                                 "curve_amp": 6.0}))
    for rname, kw in RAW:
        panel = _raw_normal_sheet("tests/fixtures/peak_src.png", K=10,
                                  **kw)
        ok, buf = cv2.imencode(".png", panel)
        hh = hashlib.sha1(buf.tobytes()).hexdigest()[:8]
        apath = arch / f"nforms_peak_src_{rname}__{hh}.png"
        if not apath.exists():
            apath.write_bytes(buf.tobytes())
            log.info("forms archive: + %s", apath.name)
        history = [q.name for q in
                   sorted(arch.glob(f"nforms_peak_src_{rname}__*.png"),
                          key=lambda q: q.stat().st_mtime)]
        rows.append({"name": f"nforms_peak_src_{rname}", "svg": "",
                     "n_forms": 10, "levels": [0, 1, 2, 3],
                     "img": f"experiments/forms/{apath.name}",
                     "history": [f"experiments/forms/{h}"
                                 for h in history]})

    # ridge probe: ridge lines EVERYWHERE (docs/ridges-research.md)
    panel = _ridge_probe("tests/fixtures/peak_src.png")
    ok, buf = cv2.imencode(".png", panel)
    hh = hashlib.sha1(buf.tobytes()).hexdigest()[:8]
    apath = arch / f"ridge_probe__{hh}.png"
    if not apath.exists():
        apath.write_bytes(buf.tobytes())
        log.info("forms archive: + %s", apath.name)
    history = [f"experiments/forms/{q.name}" for q in
               sorted(arch.glob("ridge_probe__*.png"),
                      key=lambda q: q.stat().st_mtime)]
    rows.append({"name": "ridge_probe (fold strength | fold axis | "
                 "creases on photo)", "svg": "", "n_forms": 0,
                 "levels": [], "img": history[-1], "history": history})

    # THE FULL ARCHIVE — every panel ever shown, grouped, regardless of
    # what configs exist today. Nothing leaves this list, ever.
    groups = {}
    for p in sorted(arch.glob("*.png"), key=lambda q: q.stat().st_mtime):
        base = p.name.rsplit("__", 1)[0]
        groups.setdefault(base, []).append(f"experiments/forms/{p.name}")
    archive = [{"name": k, "versions": v} for k, v in groups.items()]
    return {"rows": rows, "archive": archive}


# ---------------------------------------------------------------- tuner ----
def build_tuner() -> dict:
    """Interactive angle/value tuner: precompute posterize class maps at
    several K plus per-class stats; the browser hatches on a canvas in
    real time — click a mass, nudge its angle, slide brightness/contrast
    and posterize depth. Saves POST back to the server so the user's
    tweaks become my spec."""
    from engine.scene import load_normals, load_semantic, relight

    photo = ROOT / "tests/fixtures/peak_src.png"
    bgr = cv2.imread(str(photo))
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    H, W = gray.shape
    nrm = load_normals(str(photo), (H, W))
    sem = load_semantic(str(photo), (H, W))
    sky = np.isin(sem["labels"],
                  [i for i, n in sem["names"].items()
                   if "sky" in n.lower()])
    land = ~sky
    best_az, best_c = 315.0, -2.0
    gl = (gray[land] - gray[land].mean()) / (gray[land].std() + 1e-9)
    for az in range(0, 360, 30):
        sh = relight(nrm, float(az), 40.0)[land]
        sh = (sh - sh.mean()) / (sh.std() + 1e-9)
        c = float((sh * gl).mean())
        if c > best_c:
            best_az, best_c = float(az), c
    shade = relight(nrm, best_az, 40.0)
    qs = [round(float(q), 4) for q in
          np.quantile(shade[land], [0.10, 0.30, 0.60])]

    ns = cv2.GaussianBlur(nrm, (0, 0), 3)
    feats = ns[land].reshape(-1, 3).astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-3)
    variants = {}
    for K in (6, 8, 10, 12, 14):
        cv2.setRNGSeed(7)
        _c2, lab, ctr = cv2.kmeans(feats, K, None, crit, 4,
                                   cv2.KMEANS_PP_CENTERS)
        cls = np.full((H, W), 255, np.uint8)
        cls[land] = lab.ravel().astype(np.uint8)
        cv2.imwrite(str(IMG / f"tuner_cls_k{K}.png"), cls)
        classes = []
        for k in range(K):
            m = cls == k
            n = ctr[k]
            ang = float(np.degrees(np.arctan2(n[1], n[0]))) % 180
            classes.append({
                "angle": round(ang, 1),
                "shade": round(float(shade[m].mean()) if m.any()
                               else 1.0, 4),
                "area": round(float(m.mean()), 4)})
        variants[K] = {"map": f"imgs/tuner_cls_k{K}.png",
                       "classes": classes}
    cv2.imwrite(str(IMG / "tuner_photo.png"), bgr)
    return {"photo": "imgs/tuner_photo.png", "w": W, "h": H,
            "sun_az": best_az, "qs": qs, "variants": variants}


# ---------------------------------------------------------------- bench ----
def build_bench() -> dict:
    """The re-ink bench (bench/): per reference crop — measurement,
    skeleton-trace ceiling, greedy vocabulary reconstruction, and the
    coverage/economy scores. Cached by crop bytes + code version."""
    from bench.greedy import greedy_reink
    from bench.measure import measure
    from bench.trace import trace_replot

    crops_dir = ROOT / "refs" / "crops"
    if not crops_dir.exists():
        return {"crops": []}
    ver = "2"
    out = []
    for cp in sorted(crops_dir.glob("*.png")):
        tag = hashlib.sha1(ver.encode() + cp.read_bytes()).hexdigest()[:10]
        cache = IMG / f"bench_{cp.stem}_{tag}.json"
        if cache.exists():
            out.append(json.loads(cache.read_text()))
            continue
        log.info("bench: %s", cp.name)
        m = measure(cp)
        trace_ink, _polys, trace_stats = trace_replot(m)
        greedy_ink, greedy_stats = greedy_reink(m)

        imgs = {}
        imgs["crop"] = _save(f"bench_{cp.stem}_crop.png", m["bgr"])
        sk = (m["gray"] * 200 + 55).astype(np.uint8)
        sk = cv2.cvtColor(sk, cv2.COLOR_GRAY2BGR)
        sk[m["skeleton"]] = (40, 40, 230)
        imgs["skeleton"] = _save(f"bench_{cp.stem}_skel.png", sk)
        hsv = np.stack([
            ((m["theta"] % np.pi) / np.pi * 179).astype(np.uint8),
            np.full(m["gray"].shape, 190, np.uint8),
            (70 + m["coh"] * 185).astype(np.uint8)], -1)
        imgs["orient"] = _save(f"bench_{cp.stem}_orient.png",
                               cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR))
        imgs["trace"] = _save(f"bench_{cp.stem}_trace.png",
                              (~trace_ink * 255).astype(np.uint8))
        imgs["greedy"] = _save(f"bench_{cp.stem}_greedy.png",
                               (~greedy_ink * 255).astype(np.uint8))
        miss = np.full((*m["ink"].shape, 3), 255, np.uint8)
        miss[m["ink"] & ~greedy_ink] = (60, 60, 230)   # missed ink: red
        miss[~m["ink"] & greedy_ink] = (230, 140, 40)  # spurious: blue
        imgs["diff"] = _save(f"bench_{cp.stem}_diff.png", miss)

        row = {"name": cp.stem, "imgs": imgs, "measure": m["stats"],
               "trace": trace_stats, "greedy": greedy_stats}
        cache.write_text(json.dumps(row, indent=1))
        out.append(row)

    # micro-patch fits (refs/patches/): forms -> parametric hatch fit ->
    # leak/miss scores -> style-transfer matrix
    patches = {"rows": [], "transfer": []}
    pdir = ROOT / "refs" / "patches"
    ppaths = sorted(pdir.glob("*.png")) if pdir.exists() else []
    if ppaths:
        from bench.fit import fit_patch, transfer
        fits = {}
        for pp in ppaths:
            f = fit_patch(pp)
            fits[pp.stem] = (f, pp)
            h, w = f["ink"].shape
            gap = np.full((h, 8, 3), 255, np.uint8)
            lab = cv2.applyColorMap((f["labels"] * 80 + 40).astype(np.uint8),
                                    cv2.COLORMAP_TURBO)
            diff = np.full((h, w, 3), 255, np.uint8)
            diff[f["ink"] & ~f["render"]] = (60, 60, 230)
            diff[~f["ink"] & f["render"]] = (230, 140, 40)
            panel = np.concatenate(
                [f["bgr"], gap, lab, gap,
                 cv2.cvtColor((~f["render"] * 255).astype(np.uint8),
                              cv2.COLOR_GRAY2BGR), gap, diff], 1)
            panel = cv2.resize(panel, None, fx=2, fy=2,
                               interpolation=cv2.INTER_NEAREST)
            patches["rows"].append({
                "name": pp.stem, "k": f["k"],
                "img": _save(f"fitpatch_{pp.stem}.png", panel),
                "forms": f["forms"], "score": f["score"]})
        names = list(fits)
        for a in names:
            row = []
            for b in names:
                sc = (fits[a][0]["score"] if a == b
                      else transfer(fits[a][0], fits[b][1]))
                row.append(round(sc["loss"], 3))
            patches["transfer"].append({"from": a, "losses": row})
        patches["names"] = names

    # comb-cover: the emergent-boundary patch arrangement, validated
    # against the user's annotated rockface + shown generating freely
    anno = ROOT / "refs" / "patches" / "rockface_anno.png"
    if anno.exists():
        from bench.combs import comb_cover, strip_annotation
        from bench.measure import orientation_field, stroke_width_px
        bgr = cv2.imread(str(anno))
        clean = strip_annotation(bgr)
        gray = cv2.cvtColor(clean, cv2.COLOR_BGR2GRAY
                            ).astype(np.float32) / 255
        lo, hi = np.percentile(gray, [8, 92])
        ink_m = gray < (lo + hi) / 2
        w_px, _ = stroke_width_px(ink_m)
        th, _coh = orientation_field(gray, sigma_px=max(w_px * 2, 3))
        recon, _placed, cst = comb_cover(ink_m, th, w_px,
                                         np.random.default_rng(7))
        hh, ww = ink_m.shape
        noise = cv2.GaussianBlur(np.random.default_rng(3)
                                 .standard_normal((hh, ww))
                                 .astype(np.float32), (0, 0), 40)
        th_g = (noise - noise.min()) / (noise.max() - noise.min()) * np.pi
        gen, _p2, gst = comb_cover(np.ones((hh, ww), bool), th_g, w_px,
                                   np.random.default_rng(11),
                                   stop_deficit=0.42)
        gp = np.full((hh, 10, 3), 255, np.uint8)
        panel = np.concatenate(
            [bgr, gp, cv2.cvtColor((~recon * 255).astype(np.uint8),
                                   cv2.COLOR_GRAY2BGR),
             gp, cv2.cvtColor((~gen * 255).astype(np.uint8),
                              cv2.COLOR_GRAY2BGR)], 1)
        patches["combs"] = {
            "img": _save("combs_panel.png", panel),
            "recon": cst, "gen": gst}
    return {"crops": out, "patches": patches}


# -------------------------------------------------------------- starred ----
STARS_PATH = Path(__file__).parent / "stars.json"


def _all_showcase_variants() -> dict:
    """(family, title) -> genome for every variant showcase.py can emit.
    All generators are seeded/deterministic, so a starred panel's genome is
    reconstructable from its manifest entry forever."""
    import showcase
    vs = (showcase.variants() + showcase.texture2_variants()
          + showcase.patchwork_variants() + showcase.mosaic_variants()
          + showcase.emphasis_variants() + showcase.iter2_variants()
          + showcase.iter3_variants() + showcase.toneclosed_variants()
          + showcase.downhill_variants() + showcase.plansweep_variants()
          + showcase.bigsweep_variants())
    return {(f, t): g for f, t, _p, g in vs}


def import_stars() -> dict:
    """Merge raw starred-id captures (stars_raw_<port>.json, written by the
    collect-stars server) with every gallery manifest -> review/stars.json,
    the committed home for taste data. Ids are param-hashed, so a star can
    match manifests of several photos; all matches are kept."""
    raw = set()
    for f in sorted(OUT.glob("stars_raw_*.json")):
        raw |= set(json.loads(f.read_text()))
    stars = {}
    for mf in sorted(ROOT.glob("runs/*/*/manifest.json")):
        kind, stem = mf.parent.parent.name, mf.parent.name
        if kind not in ("bakeoff", "showcase"):
            continue
        hit = [p for p in json.loads(mf.read_text()).get("panels", [])
               if p.get("id") in raw]
        if hit:
            stars[f"{kind}/{stem}"] = hit
    STARS_PATH.write_text(json.dumps(stars, indent=1))
    found = sum(len(v) for v in stars.values())
    log.info("import_stars: %d raw ids -> %d panels in %d galleries",
             len(raw), found, len(stars))
    return stars


def build_starred() -> dict:
    """Starred showcase renders rebuilt at PIPELINE level (genome
    reconstructed, every stage imaged); starred bakeoff panels shown as
    composition-channel references (they have no genome)."""
    if not STARS_PATH.exists():
        return {"pairs": [], "bakeoff": []}
    stars = json.loads(STARS_PATH.read_text())
    reg = None
    pairs, bak = [], []
    for gal, panels in sorted(stars.items()):
        kind, stem = gal.split("/", 1)
        for p in panels:
            item = {"gallery": gal, "family": p.get("family"),
                    "title": p.get("title"), "params": p.get("params", {}),
                    "id": p.get("id")}
            src_img = ROOT / "runs" / kind / stem / p.get("img", "")
            if p.get("img") and src_img.exists():
                dst = f"star_{kind}_{stem}_{Path(p['img']).name}"
                shutil.copy(src_img, IMG / dst)
                item["img"] = f"imgs/{dst}"
            if kind != "showcase":
                bak.append(item)
                continue
            if reg is None:
                log.info("starred: loading showcase variant registry…")
                reg = _all_showcase_variants()
            title = re.sub(r"\s+tf\d+\.\d+$", "", p.get("title", ""))
            g = reg.get((p.get("family"), title))
            if g is None:
                item["note"] = ("genome not reconstructable — no matching "
                                "variant in showcase registry")
                bak.append(item)
                continue
            pair = build_pair_from(g, f"star_{stem}_{p['id']}",
                                   f"tests/fixtures/{stem}.png", 42)
            pair["starred_meta"] = item
            pairs.append(pair)
    return {"pairs": pairs, "bakeoff": bak}


# ----------------------------------------------------------- iterations ----
def _flat(d, prefix=""):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(_flat(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(d, list):
        for i, v in enumerate(d):
            out.update(_flat(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = d
    return out


def _genome_diff(a: dict, b: dict) -> list[str]:
    fa, fb = _flat(a), _flat(b)
    out = []
    for k in sorted(set(fa) | set(fb)):
        if k not in fa:
            out.append(f"+ {k} = {fb[k]}")
        elif k not in fb:
            out.append(f"- {k} (was {fa[k]})")
        elif fa[k] != fb[k]:
            out.append(f"~ {k}: {fa[k]} -> {fb[k]}")
    return out


def snapshot_iteration(pair: dict) -> None:
    """Archive this genome state (content-addressed) so the hand loop's
    history stays reviewable forever. Keyed by GENOME content only —
    builder-code changes must not fake a new iteration."""
    ghash = hashlib.sha1(json.dumps(pair["genome"],
                                    sort_keys=True).encode()).hexdigest()[:12]
    d = OUT / "iterations" / pair["name"] / ghash
    if d.exists():
        return
    d.mkdir(parents=True)
    (d / "genome.json").write_text(json.dumps(pair["genome"], indent=1))
    shutil.copy(IMG / Path(pair["final_img"]).name, d / "render.png")
    (d / "meta.json").write_text(json.dumps({
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "photo": pair["photo"], "seed": pair["seed"],
        "note": ""}, indent=1))
    log.info("iterations: archived %s/%s", pair["name"], pair["hash"])


def build_iterations() -> dict:
    out = {}
    itdir = OUT / "iterations"
    if not itdir.exists():
        return out
    for gdir in sorted(itdir.iterdir()):
        if not gdir.is_dir():
            continue
        snaps = []
        for s in gdir.iterdir():
            meta_p = s / "meta.json"
            if not meta_p.exists():
                continue
            meta = json.loads(meta_p.read_text())
            snaps.append({
                "hash": s.name, "meta": meta,
                "genome": json.loads((s / "genome.json").read_text()),
                "img": f"iterations/{gdir.name}/{s.name}/render.png"})
        snaps.sort(key=lambda x: x["meta"]["saved_at"])
        for i, s in enumerate(snaps):
            s["diff"] = (_genome_diff(snaps[i - 1]["genome"], s["genome"])
                         if i else ["(first snapshot)"])
            s.pop("genome")
        out[gdir.name] = snaps
    return out


# ----------------------------------------------------------------- main ----
SECTIONS = ("strokes", "bench", "abstract", "forms", "tuner", "marks",
            "pipeline", "iterations", "starred")


def build(sections=SECTIONS) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)
    man_p = OUT / "manifest.json"
    man = (json.loads(man_p.read_text()) if man_p.exists()
           else {"sections": {}})

    if "strokes" in sections:
        man["sections"]["strokes"] = build_strokes()
    if "bench" in sections:
        man["sections"]["bench"] = build_bench()
    if "abstract" in sections:
        man["sections"]["abstract"] = build_abstract()
    if "forms" in sections:
        man["sections"]["forms"] = build_forms()
    if "tuner" in sections:
        man["sections"]["tuner"] = build_tuner()
    if "marks" in sections:
        man["sections"]["marks"] = build_marks()
    if "pipeline" in sections:
        pairs = []
        for genome_path, photo, seed in ACTIVE:
            pair = build_pair(genome_path, photo, seed)
            snapshot_iteration(pair)
            pairs.append(pair)
        man["sections"]["pipeline"] = pairs
    if "iterations" in sections or "pipeline" in sections:
        man["sections"]["iterations"] = build_iterations()
    if "starred" in sections:
        man["sections"]["starred"] = build_starred()

    man["generated"] = datetime.now(timezone.utc).isoformat()
    man["active"] = [{"genome": g, "photo": p, "seed": s}
                     for g, p, s in ACTIVE]
    # stamp the UI version into both page and manifest: an open tab that
    # polls the manifest reloads ITSELF when the page code changes (data
    # auto-refresh alone leaves stale JS running against new manifests)
    src = (Path(__file__).parent / "index.html").read_text()
    ui_ver = hashlib.sha1(src.encode()).hexdigest()[:10]
    man["ui"] = ui_ver
    man_p.write_text(json.dumps(man, indent=1))
    (OUT / "index.html").write_text(
        src.replace("__UI_VERSION__", ui_ver))
    log.info("review site -> %s", OUT / "index.html")
    return OUT
