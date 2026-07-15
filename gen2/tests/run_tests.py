"""Smoke + golden + benchmark tests. Run: ../.venv/bin/python tests/run_tests.py

1. Module smoke: every registered module renders a synthetic band without
   NaNs, stays within the region bbox (+ tolerance), returns valid polylines.
2. Golden: render(genome, seed) twice -> identical polylines (purity).
3. Real-photo benchmark: every preset genome renders against real photos.
4. Pair benchmark: fixtures include (photo, human ink drawing) pairs of the
   SAME composition — renders are scored on whether they put ink where the
   artist did (density correlation, ink budget, bare paper).
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.photo import (load_structure_ctx, mask_to_region,  # noqa: E402
                          region_to_mask)
from engine.modules import MODULES                            # noqa: E402
from engine.render import render                              # noqa: E402

FIXTURE = str(Path(__file__).parent / "fixtures" / "landscape.png")
# All *_src fixtures are real photographs. mountain/peak additionally have
# a matching *_ink fixture: a human pen-and-ink drawing of the SAME
# composition — ground truth for the pair benchmark below.
FIXDIR = Path(__file__).parent / "fixtures"
REAL_PHOTOS = [str(FIXDIR / f"{n}.png")
               for n in ("snow_trees_src", "mountain_peaks_src")]
PAIRS = [("mountain_src.png", "mountain_ink.png"),
         ("peak_src.png", "peak_ink.png")]
PAIR_GENOMES = ("pen_ink", "classic_ink")
OVERSHOOT_TOL = 3.0  # mm; humanization overshoot allowance


def smoke() -> None:
    ctx = load_structure_ctx(FIXTURE, page_size="letter")
    page = ctx["page"]
    region = mask_to_region(ctx["tone_bands"][2], page)
    mask = region_to_mask(region, page, ctx["tone_bands"][2].shape)
    minx, miny, maxx, maxy = region.bounds
    for name, fn in MODULES.items():
        rng = np.random.default_rng(7)
        lines = fn(mask, region, ctx, {}, rng)
        assert isinstance(lines, list), name
        for ln in lines:
            assert ln.ndim == 2 and ln.shape[1] == 2 and len(ln) >= 2, name
            assert not np.isnan(ln).any(), f"{name}: NaN"
            if name != "contour_lines":  # edge layer spans whole page
                assert ln[:, 0].min() >= minx - OVERSHOOT_TOL, name
                assert ln[:, 0].max() <= maxx + OVERSHOOT_TOL, name
                assert ln[:, 1].min() >= miny - OVERSHOOT_TOL, name
                assert ln[:, 1].max() <= maxy + OVERSHOOT_TOL, name
        print(f"  smoke ok: {name:15s} {len(lines):5d} lines")


def golden() -> None:
    genome = json.loads(
        (Path(__file__).parent.parent / "genomes" / "classic_ink.json")
        .read_text())
    a, _ = render(genome, 42, photo_path=FIXTURE)
    b, _ = render(genome, 42, photo_path=FIXTURE)
    assert a.keys() == b.keys()
    for pen in a:
        assert len(a[pen]) == len(b[pen]), pen
        for x, y in zip(a[pen], b[pen]):
            assert np.array_equal(x, y), f"{pen}: polyline mismatch"
    n = sum(len(v) for v in a.values())
    print(f"  golden ok: render(genome, 42) reproducible ({n} lines)")


def real_photo() -> None:
    """Render every preset genome against the real photograph and write
    previews for human rubric scoring (runs/tests/)."""
    import tempfile
    import tomllib
    from engine.svgout import render_png, write_svg
    root = Path(__file__).parent.parent
    pens = tomllib.loads((root / "pens.toml").read_text())
    out_dir = root / "runs" / "tests"
    out_dir.mkdir(parents=True, exist_ok=True)
    for photo in REAL_PHOTOS:
        pname = Path(photo).stem.removesuffix("_src")
        for gpath in sorted((root / "genomes").glob("*.json")):
            genome = json.loads(gpath.read_text())
            layers, page = render(genome, 42, photo_path=photo)
            n = sum(len(v) for v in layers.values())
            assert n > 100, f"{gpath.stem} on {pname}: only {n} lines"
            png = out_dir / f"{gpath.stem}_{pname}_s42.png"
            with tempfile.NamedTemporaryFile(suffix=".svg") as tf:
                write_svg(layers, pens, page, tf.name)
                render_png(tf.name, str(png), width_px=1100)
            print(f"  real photo ok: {gpath.stem:12s} on {pname:14s} "
                  f"{n:5d} lines → {png.name}")


def _ink_density(png: Path, grid_w: int = 40) -> "np.ndarray":
    """Content-cropped, coarse ink-density grid (0 = paper, 1 = solid)."""
    import cv2
    g = cv2.imread(str(png), cv2.IMREAD_GRAYSCALE).astype(np.float32)
    paper = max(float(np.percentile(g, 95)), 1.0)
    ink = np.clip((paper - g) / paper, 0.0, 1.0)
    ys, xs = np.nonzero(ink > 0.12)   # crop page margins / paper border
    ink = ink[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    gh = max(int(round(grid_w * ink.shape[0] / ink.shape[1])), 8)
    return cv2.resize(ink, (grid_w, gh), interpolation=cv2.INTER_AREA)


def pairs() -> None:
    """Score genome renders against the paired human ink drawings: does
    the render put ink where the artist did? Soft floors only — the
    printed scorecard is the real product; watch it climb."""
    import cv2
    import tempfile
    import tomllib
    from engine.svgout import render_png, write_svg
    root = Path(__file__).parent.parent
    pens = tomllib.loads((root / "pens.toml").read_text())
    out_dir = root / "runs" / "tests"
    out_dir.mkdir(parents=True, exist_ok=True)
    for src, ink in PAIRS:
        human = _ink_density(FIXDIR / ink)
        for gname in PAIR_GENOMES:
            genome = json.loads(
                (root / "genomes" / f"{gname}.json").read_text())
            layers, page = render(genome, 42,
                                  photo_path=str(FIXDIR / src))
            png = out_dir / f"{gname}_{Path(src).stem}_s42.png"
            with tempfile.NamedTemporaryFile(suffix=".svg") as tf:
                write_svg(layers, pens, page, tf.name)
                render_png(tf.name, str(png), width_px=1100)
            d = _ink_density(png)
            d = cv2.resize(d, (human.shape[1], human.shape[0]))
            corr = float(np.corrcoef(d.ravel(), human.ravel())[0, 1])
            ratio = float(d.mean() / max(human.mean(), 1e-6))
            paper_h = float((human < 0.06).mean())
            paper_r = float((d < 0.06).mean())
            print(f"  pair {Path(src).stem:9s} x {gname:12s} "
                  f"corr {corr:+.2f}  ink x{ratio:.2f}  "
                  f"paper {paper_r:.0%} (artist {paper_h:.0%})")
            assert corr > 0.15, f"{gname}/{src}: ink placement corr {corr}"
            assert 0.2 < ratio < 5.0, f"{gname}/{src}: ink budget x{ratio}"


if __name__ == "__main__":
    print("module smoke tests:")
    smoke()
    print("golden test:")
    golden()
    print("real-photo benchmark:")
    real_photo()
    print("pair benchmark (render vs human ink, same photo):")
    pairs()
    import test_evolve
    print("evolve tests:")
    test_evolve.store_roundtrip()
    test_evolve.mutator_validity()
    test_evolve.one_generation()
    print("ALL PASS")
