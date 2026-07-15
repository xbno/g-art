"""M1 CLI: render a genome JSON against a photo.

    python m1.py genomes/blue_mountain.json tests/fixtures/peak_src.png --seed 1

Each pen layer is optimized through vpype separately, then re-merged into one
multi-layer SVG, so layer colors/widths always come from pens.toml.
"""

import argparse
import json
import logging
import re
import tempfile
import tomllib
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import numpy as np

from engine.render import render
from engine.svgout import render_png, vpype_optimize, write_svg

HERE = Path(__file__).parent
log = logging.getLogger("m1")

_UNIT_MM = {"mm": 1.0, "cm": 10.0, "in": 25.4, "px": 25.4 / 96, "": 25.4 / 96}


def _parse_optimized(svg_path: str) -> list[np.ndarray]:
    """Pull polylines back out of a vpype-written SVG, in mm."""
    root = ET.parse(svg_path).getroot()
    m = re.match(r"([0-9.]+)\s*([a-z]*)", root.get("width", ""))
    w_mm = float(m.group(1)) * _UNIT_MM.get(m.group(2), 1.0)
    vb_w = float(root.get("viewBox").split()[2])
    s = w_mm / vb_w
    out = []
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "polyline":
            pts = np.array([[float(v) for v in p.split(",")]
                            for p in el.get("points").strip().split()])
            out.append(pts * s)
        elif tag == "line":
            out.append(s * np.array(
                [[float(el.get("x1")), float(el.get("y1"))],
                 [float(el.get("x2")), float(el.get("y2"))]]))
    return out


def render_genome(genome_path: str, photo: str, seed: int,
                  out_dir: Path) -> tuple[Path, Path]:
    genome = json.loads(Path(genome_path).read_text())
    layers, page = render(genome, seed, photo_path=photo)
    pens = tomllib.loads((HERE / "pens.toml").read_text())
    ordered = {n: layers[n] for n in pens if layers.get(n)}

    opt: dict[str, list] = {}
    with tempfile.TemporaryDirectory() as td:
        for name, lines in ordered.items():
            raw = Path(td) / f"{name}.svg"
            done = Path(td) / f"{name}_o.svg"
            write_svg({name: lines}, pens, page, str(raw))
            if vpype_optimize(str(raw), str(done)):
                opt[name] = _parse_optimized(str(done))
            else:
                log.warning("vpype unavailable; %s unoptimized", name)
                opt[name] = lines

    out_dir.mkdir(parents=True, exist_ok=True)
    gname = genome.get("name", Path(genome_path).stem)
    stem = f"{gname}_{Path(photo).stem}_s{seed}_{datetime.now():%H%M%S}"
    svg = out_dir / f"{stem}.svg"
    png = out_dir / f"{stem}.png"
    write_svg(opt, pens, page, str(svg))
    render_png(str(svg), str(png))
    return svg, png


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("genome")
    ap.add_argument("photo")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default="runs")
    args = ap.parse_args()
    svg, png = render_genome(args.genome, args.photo, args.seed,
                             Path(args.out))
    print(svg)
    print(png)
