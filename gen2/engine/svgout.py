"""Layered SVG export, Inkscape/AxiDraw-ready.

Document units are mm (width/height in mm, viewBox 1 unit = 1 mm).
Each pen gets one Inkscape layer named "N - name width".
"""

import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

from .geom import Polyline
from .page import Page


def _path_d(line: Polyline, nd: int = 2) -> str:
    pts = np.round(line, nd)
    coords = [f"{p[0]:.{nd}f},{p[1]:.{nd}f}" for p in pts]
    return "M " + " L ".join(coords)


def write_svg(layers: dict[str, list[Polyline]], pens: dict[str, dict],
              page: Page, path: str) -> None:
    """layers: {pen_name: polylines}; pens: {name: {color, width_mm}}."""
    w, h = page.width_mm, page.height_mm
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
        f'width="{w}mm" height="{h}mm" viewBox="0 0 {w} {h}">',
    ]
    for i, (name, lines) in enumerate(layers.items(), start=1):
        pen = pens[name]
        label = f"{i} - {name} {pen['width_mm']}"
        parts.append(
            f'<g inkscape:groupmode="layer" inkscape:label="{label}" '
            f'id="layer{i}" fill="none" stroke="{pen["color"]}" '
            f'stroke-width="{pen["width_mm"]}" stroke-linecap="round">')
        for ln in lines:
            if len(ln) >= 2:
                parts.append(f'<path d="{_path_d(ln)}"/>')
        parts.append('</g>')
    parts.append('</svg>')
    Path(path).write_text("\n".join(parts))


def vpype_optimize(svg_in: str, svg_out: str,
                   merge_mm: float = 0.5, simplify_mm: float = 0.05) -> bool:
    """Merge/sort/simplify per layer. simplify tolerance stays far below pen
    width so humanization wobble survives. Returns False if vpype missing."""
    vpype = (shutil.which("vpype")
             or str(Path(sys.executable).parent / "vpype"))
    cmd = [vpype, "read", svg_in,
           "linemerge", "-t", f"{merge_mm}mm",
           "linesort",
           "linesimplify", "-t", f"{simplify_mm}mm",
           "filter", "--min-length", "0.5mm",
           "write", svg_out]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def render_png(svg_path: str, png_path: str, width_px: int = 1400) -> None:
    import cairosvg
    cairosvg.svg2png(url=svg_path, write_to=png_path,
                     output_width=width_px, background_color="white")
