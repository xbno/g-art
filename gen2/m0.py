"""M0: photo -> fixed-angle banded hatching -> humanize -> layered SVG.

Usage:
    python m0.py photo.jpg [--seed 1] [--page letter] [--out runs/]
"""

import argparse
import logging
import tomllib
from datetime import datetime
from pathlib import Path

import numpy as np

from engine.hatch import fixed_hatch
from engine.humanize import humanize
from engine.photo import load_structure_ctx, mask_to_region
from engine.svgout import render_png, vpype_optimize, write_svg

log = logging.getLogger("m0")

# per-band treatment, lightest (0) to darkest. angle_delta is added to the
# global base angle; "cross" adds a second pass at +cross_delta degrees.
BAND_PLAN = [
    {"spacing": None},                                   # bare paper
    {"spacing": 2.4, "angle_delta": 0.0},
    {"spacing": 1.4, "angle_delta": -14.0},
    {"spacing": 0.85, "angle_delta": 11.0},
    {"spacing": 0.5, "angle_delta": -4.0, "cross": True, "cross_delta": 72.0},
]


def render(photo: str, seed: int, page_size: str, out_dir: Path,
           base_angle: float = 52.0, pen: str = "black03",
           source_params: dict | None = None,
           human_params: dict | None = None) -> tuple[Path, Path]:
    ctx = load_structure_ctx(photo, page_size=page_size,
                             params=source_params)
    page = ctx["page"]
    rng = np.random.default_rng(seed)

    all_lines = []
    for band_i, plan in enumerate(BAND_PLAN[:len(ctx["tone_bands"])]):
        if plan["spacing"] is None:
            continue
        region = mask_to_region(ctx["tone_bands"][band_i], page)
        if region.is_empty:
            continue
        angle = base_angle + plan["angle_delta"] + rng.uniform(-1.5, 1.5)
        lines = fixed_hatch(region, angle, plan["spacing"], rng)
        if plan.get("cross"):
            lines += fixed_hatch(region, angle + plan["cross_delta"],
                                 plan["spacing"] * 1.15, rng)
        lines = humanize(lines, seed * 100 + band_i, human_params)
        log.info("band %d: %d lines", band_i, len(lines))
        all_lines.extend(lines)

    pens = tomllib.loads(
        (Path(__file__).parent / "pens.toml").read_text())
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{Path(photo).stem}_s{seed}_{datetime.now():%H%M%S}"
    svg_raw = out_dir / f"{stem}_raw.svg"
    svg = out_dir / f"{stem}.svg"
    png = out_dir / f"{stem}.png"

    write_svg({pen: all_lines}, pens, page, str(svg_raw))
    if vpype_optimize(str(svg_raw), str(svg)):
        svg_raw.unlink()
    else:
        log.warning("vpype not found; SVG is unoptimized")
        svg_raw.rename(svg)
    render_png(str(svg), str(png))
    return svg, png


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("photo")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--page", default="11x17")
    ap.add_argument("--angle", type=float, default=52.0)
    ap.add_argument("--out", default="runs")
    ap.add_argument("--blur", type=float, default=0.8,
                    help="pre-band blur in mm (crank up for busy sources)")
    ap.add_argument("--band-gamma", type=float, default=1.0,
                    help=">1 = more bare paper, darker thresholds")
    ap.add_argument("--clahe", type=float, default=2.0,
                    help="CLAHE clip limit, 0 disables")
    args = ap.parse_args()
    svg, png = render(args.photo, args.seed, args.page,
                      Path(args.out), base_angle=args.angle,
                      source_params={"blur_mm": args.blur,
                                     "band_gamma": args.band_gamma,
                                     "clahe_clip": args.clahe})
    print(svg)
    print(png)
