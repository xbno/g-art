"""M2 headless evolution loop.

    python -m evolve.cli tests/fixtures/peak_src.png \
        --genome genomes/classic_ink.json --seed 1

Each generation renders A and B (same seed, different genomes), writes a
side-by-side composite PNG, and reads one command from the terminal:

    a / b        pick the winner (becomes next parent)
    x            both bad (mutator reheats, jumps structurally)
    s <text>     steer: prompt the mutator, then re-propose
    p <name>     pin the current parent as a named style
    r            reroll seed (explicit siblings, per seed discipline)
    e            export current parent as full-quality SVG (vpype)
    q            quit
"""

import argparse
import json
import logging
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.render import render                       # noqa: E402
from engine.svgout import render_png, write_svg        # noqa: E402
from evolve.mutator import RandomMutator, make_mutator  # noqa: E402
from evolve.store import Store                         # noqa: E402

HERE = Path(__file__).parent.parent
log = logging.getLogger("evolve")


def render_thumb(genome: dict, seed: int, photo: str,
                 out_png: Path, width_px: int = 850) -> Path:
    """Fast preview render: no vpype, straight to PNG."""
    layers, page = render(genome, seed, photo_path=photo)
    pens = tomllib.loads((HERE / "pens.toml").read_text())
    with tempfile.NamedTemporaryFile(suffix=".svg") as tf:
        write_svg(layers, pens, page, tf.name)
        render_png(tf.name, str(out_png), width_px=width_px)
    return out_png


def composite(a_png: Path, b_png: Path, out: Path) -> None:
    a, b = cv2.imread(str(a_png)), cv2.imread(str(b_png))
    h = min(a.shape[0], b.shape[0])
    a = a[:h]
    b = b[:h]
    bar = np.full((h, 6, 3), 40, np.uint8)
    img = cv2.hconcat([a, bar, b])
    for label, x in (("A", 20), ("B", a.shape[1] + 26)):
        cv2.putText(img, label, (x, 60), cv2.FONT_HERSHEY_SIMPLEX,
                    2.0, (30, 30, 200), 4)
    cv2.imwrite(str(out), img)


def export_full(genome: dict, seed: int, photo: str, out_dir: Path) -> Path:
    """Full-quality vpype export via the m1 pipeline."""
    import m1
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".json",
                                     delete=False) as tf:
        json.dump(genome, tf)
        gpath = tf.name
    svg, png = m1.render_genome(gpath, photo, seed, out_dir)
    return svg


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("engine").setLevel(logging.WARNING)
    ap = argparse.ArgumentParser()
    ap.add_argument("photo")
    ap.add_argument("--genome", default=str(HERE / "genomes/classic_ink.json"))
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--db", default=str(HERE / "runs/evolve/evolve.db"))
    ap.add_argument("--branch", help="node id to branch from")
    ap.add_argument("--random", action="store_true",
                    help="force the no-CLI random mutator")
    ap.add_argument("--model", default=None,
                    help="claude CLI --model (default: your CLI default)")
    ap.add_argument("--no-open", action="store_true",
                    help="don't auto-open composites")
    args = ap.parse_args()

    store = Store(args.db)
    seed = args.seed

    if args.branch:
        node = store.get_node(args.branch)
        if not node:
            sys.exit(f"no node {args.branch}")
        parent_genome, gen = node["genome"], node["generation"]
        run_id = store.new_run(args.photo, seed, f"branch of {args.branch}")
        parent_id = store.add_node(run_id, args.branch, parent_genome, seed,
                                   gen, "root", "branch")
    else:
        parent_genome = json.loads(Path(args.genome).read_text())
        gen = 0
        run_id = store.new_run(args.photo, seed)
        parent_id = store.add_node(run_id, None, parent_genome, seed, 0,
                                   "root")
    store.mark_chosen(parent_id)

    run_dir = Path(args.db).parent / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"run {run_id} → {run_dir}")
    mutator = make_mutator(force_random=args.random, seed=args.seed,
                           model=args.model,
                           payload_dir=run_dir / "payloads")

    parent_png = render_thumb(parent_genome, seed, args.photo,
                              run_dir / f"{parent_id}.png")
    history: list[dict] = []
    steer: str | None = None
    pick_streak, bad_streak = 0, 0

    while True:
        gen += 1
        if steer or bad_streak >= 2:
            temperature = "explore"
        else:
            temperature = "refine" if pick_streak >= 3 else "explore"

        print(f"\ngen {gen} [{temperature}]"
              + (f" steering: {steer}" if steer else "")
              + " — mutating...")
        try:
            prop = mutator.propose(parent_genome, history, steer=steer,
                                   parent_png=str(parent_png),
                                   temperature=temperature)
        except Exception as e:
            log.warning("mutator failed (%s); random fallback this gen", e)
            prop = RandomMutator(seed + gen).propose(
                parent_genome, history, temperature=temperature)
        print(f"  {prop['rationale']}")

        nodes, pngs = {}, {}
        for slot in ("a", "b"):
            nid = store.add_node(run_id, parent_id, prop[f"child_{slot}"],
                                 seed, gen, slot,
                                 steer or prop["rationale"])
            print(f"  rendering {slot.upper()} ({nid})...")
            pngs[slot] = render_thumb(prop[f"child_{slot}"], seed,
                                      args.photo, run_dir / f"{nid}.png")
            nodes[slot] = nid
        comp = run_dir / f"gen{gen:03d}_ab.png"
        composite(run_dir / f"{nodes['a']}.png",
                  run_dir / f"{nodes['b']}.png", comp)
        if not args.no_open and sys.platform == "darwin":
            subprocess.run(["open", str(comp)], check=False)
        steer = None

        while True:
            cmd = input(f"gen {gen} [a/b/x/s <txt>/p <name>/r/e/q] > ").strip()
            if cmd in ("a", "b"):
                store.mark_chosen(nodes[cmd])
                parent_id, parent_genome = nodes[cmd], prop[f"child_{cmd}"]
                parent_png = pngs[cmd]
                history.append({"generation": gen, "outcome": f"picked_{cmd}",
                                "note": prop["rationale"]})
                pick_streak, bad_streak = pick_streak + 1, 0
                break
            if cmd == "x":
                history.append({"generation": gen, "outcome": "both_bad",
                                "note": prop["rationale"]})
                bad_streak, pick_streak = bad_streak + 1, 0
                break
            if cmd.startswith("s "):
                steer = cmd[2:].strip()
                history.append({"generation": gen, "outcome": "steered",
                                "note": steer})
                break
            if cmd.startswith("p "):
                store.pin(parent_id, cmd[2:].strip())
                print(f"  pinned {parent_id} as {cmd[2:].strip()!r}")
                continue
            if cmd == "r":
                seed += 1
                print(f"  seed → {seed} (new siblings next gen)")
                break
            if cmd == "e":
                svg = export_full(parent_genome, seed, args.photo,
                                  run_dir / "exports")
                print(f"  exported {svg}")
                continue
            if cmd == "q":
                print(f"run {run_id} saved. branch back any time with "
                      f"--branch {parent_id}")
                return
            print("  ? a/b pick · x both bad · s <prompt> steer · "
                  "p <name> pin · r reroll seed · e export · q quit")


if __name__ == "__main__":
    main()
