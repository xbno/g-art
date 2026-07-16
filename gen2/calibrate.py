"""Mark darkness calibration — Guptill's hatching value scale for OUR
marks. Renders a swatch per (module, params, pen) on a synthetic context,
measures effective ink coverage with engine/inkmap, and emits:

    runs/calibration/marks.json   the darkness proxy table
    runs/calibration/scale.png    the visual value scale, sorted

This is the 'first step of composition' the user named: before assigning
patterns to regions, know what gray each pattern actually reads as, so a
region's target tone can be MATCHED, not guessed.

    python calibrate.py
"""

import json
import logging
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from shapely.geometry import Polygon          # noqa: E402

from engine.humanize import humanize          # noqa: E402
from engine.inkmap import ink_map, pen_width_mm  # noqa: E402
from engine.modules import MODULES            # noqa: E402
from engine.page import Page                  # noqa: E402

log = logging.getLogger("calibrate")

SWATCH_MM = 40.0
PX_PER_MM = 4.0


def synthetic_ctx(gray_value: float = 0.35):
    n = int(SWATCH_MM * PX_PER_MM)
    # exact swatch geometry: the page IS the swatch, 1px = 1/PX_PER_MM mm
    page = Page(SWATCH_MM, SWATCH_MM, 0.0, 1 / PX_PER_MM, 0.0, 0.0)
    g = np.full((n, n), gray_value, np.float32)
    theta = np.full((n, n), np.deg2rad(52.0), np.float32)
    return {"gray": g, "orientation": theta,
            "coherence": np.ones((n, n), np.float32),
            "edge_map": np.zeros((n, n), bool),
            "tone_bands": [np.ones((n, n), bool)],
            "page": page, "normals": None}


SPECS = []
for sp in (1.6, 1.2, 0.9, 0.7, 0.55, 0.45):
    SPECS.append(("fixed_hatch", {"angle_deg": 52, "spacing_mm": sp}))
for sp in (0.9, 0.7, 0.55):
    SPECS.append(("cross_hatch", {"angle_deg": 45, "spacing_mm": sp,
                                  "cross_delta_deg": 60}))
for sp in (0.7, 0.5):
    SPECS.append(("shingle_hatch", {"swatch_mm": 5, "spacing_mm": sp,
                                    "overlap": 0.5}))
for sp in (0.9, 0.7, 0.55):
    SPECS.append(("flow_hatch", {"spacing_mm": sp, "step_mm": 0.6,
                                 "max_len_mm": 4.0,
                                 "min_coherence": 0.0,
                                 "fallback_angle_deg": 80}))
for sp in (2.4, 1.8, 1.3):
    SPECS.append(("curl_fill", {"radius_mm": 1.2, "spacing_mm": sp}))
for sp in (1.5, 1.0):
    SPECS.append(("scribble_fill", {"spacing_mm": sp, "step_mm": 1.0}))
SPECS.append(("solid_fill", {"angle_deg": 48, "spacing_mm": 0.42}))


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    out = Path("runs/calibration")
    out.mkdir(parents=True, exist_ok=True)
    ctx = synthetic_ctx()
    page = ctx["page"]
    n = ctx["gray"].shape[0]
    mask = np.ones_like(ctx["gray"], dtype=bool)
    # region corners defined in PIXEL space and mapped through the page so
    # region-based and mask-based modules land in the same frame
    pad = 8
    corners_px = np.array([[pad, pad], [n - pad, pad],
                           [n - pad, n - pad], [pad, n - pad]], float)
    region = Polygon(page.px_to_mm(corners_px))

    rows = []
    for pen in ("black03", "black05", "blue03"):
        for module, params in SPECS:
            rng = np.random.default_rng(7)
            lines = MODULES[module](mask, region, ctx, params, rng)
            lines = humanize(lines, 7, {"wobble_amp_mm": 0.12})
            cov = ink_map({pen: lines}, page, ctx["gray"].shape,
                          blur_mm=1.4)
            inner = cov[n // 6: -n // 6, n // 6: -n // 6]
            rows.append({"module": module, "params": params, "pen": pen,
                         "coverage": round(float(inner.mean()), 4),
                         "lines": len(lines)})
            log.info("%-14s %-10s %s -> %.3f", module, pen,
                     params.get("spacing_mm"), rows[-1]["coverage"])

    rows.sort(key=lambda r: r["coverage"])
    (out / "marks.json").write_text(json.dumps(rows, indent=1))

    # visual value scale: rasterize each swatch, order light -> dark
    black = [r for r in rows if r["pen"] == "black03"]
    cell = 160
    cols = 8
    rws = (len(black) + cols - 1) // cols
    sheet = np.full((rws * (cell + 34), cols * cell, 3), 255, np.uint8)
    for i, r in enumerate(black):
        rng = np.random.default_rng(7)
        lines = MODULES[r["module"]](mask, region, ctx, r["params"], rng)
        lines = humanize(lines, 7, {"wobble_amp_mm": 0.12})
        canvas = np.zeros(ctx["gray"].shape, np.uint8)
        t = max(int(round(pen_width_mm(r["pen"]) / page.mm_per_px)), 1)
        pts = [np.round(page.mm_to_px(np.asarray(ln))).astype(np.int32)
               for ln in lines if len(ln) >= 2]
        if pts:
            cv2.polylines(canvas, pts, False, 255, t)
        sw = 255 - cv2.resize(canvas, (cell, cell))
        y, x = divmod(i, cols)
        y0 = y * (cell + 34)
        sheet[y0:y0 + cell, x * cell:(x + 1) * cell] = sw[..., None]
        label = f"{r['module'][:9]} {r['params'].get('spacing_mm', '')}" \
                f" ={r['coverage']:.2f}"
        cv2.putText(sheet, label, (x * cell + 4, y0 + cell + 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1,
                    cv2.LINE_AA)
    cv2.imwrite(str(out / "scale.png"), sheet)
    log.info("wrote %s (%d specs x 3 pens)", out, len(SPECS))


if __name__ == "__main__":
    main()
