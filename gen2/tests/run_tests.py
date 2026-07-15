"""Smoke + golden tests. Run: ../.venv/bin/python tests/run_tests.py

1. Module smoke: every registered module renders a synthetic band without
   NaNs, stays within the region bbox (+ tolerance), returns valid polylines.
2. Golden: render(genome, seed) twice -> identical polylines (purity).
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


if __name__ == "__main__":
    print("module smoke tests:")
    smoke()
    print("golden test:")
    golden()
    import test_evolve
    print("evolve tests:")
    test_evolve.store_roundtrip()
    test_evolve.mutator_validity()
    test_evolve.one_generation()
    print("ALL PASS")
