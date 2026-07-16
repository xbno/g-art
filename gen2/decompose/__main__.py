"""CLI: python -m decompose <photo> [<photo>...]

Writes <stem>.scene.{npz,json,png} next to each photo."""

import argparse
import json
import logging
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from . import models, plan, vis

log = logging.getLogger("decompose")


def decompose_one(path: Path, args) -> None:
    img = Image.open(path).convert("RGB")
    if max(img.size) > args.max_side:
        s = args.max_side / max(img.size)
        img = img.resize((round(img.width * s), round(img.height * s)),
                         Image.LANCZOS)
    rgb = np.asarray(img)
    log.info("%s %sx%s", path.name, img.width, img.height)

    depth = models.run_depth(img)
    masks = models.run_sam_masks(img, points_per_crop=args.points)
    labels, regions = plan.build_plan(
        rgb, masks, depth, {"min_frac": args.min_frac})

    stem = path.parent / path.stem
    gen = f"{models.SAM_MODEL}+{models.DEPTH_MODEL}"
    plan.save_plan(stem, labels, depth, regions, path.name, gen)
    panel = vis.plan_overlay(rgb, labels, depth, regions)
    cv2.imwrite(f"{stem}.scene.png", cv2.cvtColor(panel, cv2.COLOR_RGB2BGR))
    log.info("wrote %s.scene.{npz,json,png} (%d regions)", stem,
             len(regions))

    if not args.skip_semantic:
        seg, id2label = models.run_semantic(img)
        np.savez_compressed(f"{stem}.semantic.npz", labels=seg,
                            names=json.dumps(id2label))
        log.info("wrote %s.semantic.npz", stem)

    if not args.skip_normals:
        n = models.run_normals(img)
        np.savez_compressed(f"{stem}.normals.npz",
                            normals=n.astype(np.float16))
        cv2.imwrite(f"{stem}.normals.png", cv2.cvtColor(
            ((n + 1) / 2 * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
        log.info("wrote %s.normals.{npz,png}", stem)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("photos", nargs="+", type=Path)
    ap.add_argument("--max-side", type=int, default=1280)
    ap.add_argument("--points", type=int, default=32,
                    help="SAM points per crop side (more = finer regions)")
    ap.add_argument("--min-frac", type=float, default=0.004)
    ap.add_argument("--skip-normals", action="store_true",
                    help="skip the Marigold surface-normal artifact")
    ap.add_argument("--skip-semantic", action="store_true",
                    help="skip the frozen semantic segmentation")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for p in args.photos:
        decompose_one(p, args)


if __name__ == "__main__":
    main()
