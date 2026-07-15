"""M2 tests: store round-trip, random-mutator genome validity, and one
headless generation (mutate -> render both children with a shared seed)."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.render import render                    # noqa: E402
from evolve.mutator import RandomMutator, validate_genome  # noqa: E402
from evolve.store import Store                      # noqa: E402

FIXTURE = str(Path(__file__).parent / "fixtures" / "landscape.png")
GENOME = json.loads(
    (Path(__file__).parent.parent / "genomes" / "classic_ink.json")
    .read_text())


def store_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = Store(f"{td}/t.db")
        rid = s.new_run("photo.png", 7)
        root = s.add_node(rid, None, GENOME, 7, 0, "root")
        a = s.add_node(rid, root, GENOME, 7, 1, "a", "ctx")
        b = s.add_node(rid, root, GENOME, 7, 1, "b")
        s.mark_chosen(a)
        s.pin(a, "test style")
        assert s.get_node(a)["chosen"] == 1
        assert s.get_node(b)["chosen"] == 0
        assert s.get_node(a)["genome"] == GENOME
        assert [n["id"] for n in s.lineage(a)] == [root, a]
        assert len(s.generation_nodes(rid, 1)) == 2
        assert s.last_chosen(rid)["id"] == a
        assert s.pins()[0]["name"] == "test style"
    print("  store ok: round-trip, lineage, pins")


def mutator_validity() -> None:
    m = RandomMutator(seed=3)
    for temp in ("explore", "refine"):
        prop = m.propose(GENOME, [], temperature=temp)
        validate_genome(prop["child_a"])
        validate_genome(prop["child_b"])
    print("  mutator ok: random children validate")


def one_generation() -> None:
    m = RandomMutator(seed=11)
    prop = m.propose(GENOME, [], temperature="explore")
    seed = 42  # A/B share the seed — genome is the only difference
    for slot in ("child_a", "child_b"):
        layers, _ = render(prop[slot], seed, photo_path=FIXTURE)
        n = sum(len(v) for v in layers.values())
        assert n > 0 or all(
            b["module"] == "empty" for b in prop[slot]["bands"]), slot
        print(f"  generation ok: {slot} rendered {n} lines (seed {seed})")


if __name__ == "__main__":
    print("evolve tests:")
    store_roundtrip()
    mutator_validity()
    one_generation()
    print("EVOLVE PASS")
