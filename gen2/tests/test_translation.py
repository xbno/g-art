"""Translation check: does the ink DELIVERED per mass match the coverage
the plan PROMISED? Renders a plan genome, rasterizes the result, and
reports per-mass achieved coverage vs the level target. This isolates
'our patterns fail to hit their calibrated values' from 'the plan was
bad' — the two have been conflated all along.

    .venv/bin/python gen2/tests/test_translation.py <genome.json> <photo>
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.inkmap import ink_map        # noqa: E402
from engine.render import render         # noqa: E402
from engine.render import _structure_ctx  # noqa: E402


def check(genome: dict, photo: str, seed: int = 42):
    layers, page = render(genome, seed, photo_path=photo)
    ctx = _structure_ctx(genome, photo)
    masses = ctx.get("plan_masses")
    levels = ctx.get("plan_levels")
    if masses is None:
        print("no compiled plan in genome — nothing to check")
        return []
    targets = genome["plan"].get("assign", {}).get("targets", [])
    cov = ink_map(layers, page, ctx["gray"].shape)
    rows = []
    print(f"{'mass':>5} {'lvl':>3} {'target':>7} {'achieved':>9} "
          f"{'ratio':>6}  verdict")
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
        rows.append({"mass": mid, "level": lvl, "target": t,
                     "achieved": round(a, 3), "verdict": verdict})
        print(f"{mid:>5} {lvl:>3} {t:>7.2f} {a:>9.3f} "
              f"{ratio:>6.2f}  {verdict}")
    bad = [r for r in rows if r["verdict"] != "ok"]
    print(f"\n{len(rows) - len(bad)}/{len(rows)} masses deliver their "
          f"promised value")
    return rows


if __name__ == "__main__":
    genome = json.loads(Path(sys.argv[1]).read_text())
    check(genome, sys.argv[2])
