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
    return {"crops": out}


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
SECTIONS = ("strokes", "bench", "marks", "pipeline", "iterations",
            "starred")


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
