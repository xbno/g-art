"""Fast preview render (no vpype): genome + photo + seed -> PNG.

Importable (used by evolve/cli.py) and runnable — the /mutate-genome
command invokes it to see its own candidates before returning them:

    .venv/bin/python gen2/evolve/preview.py <genome.json> <photo> <seed> <out.png>
"""

import json
import sys
import tempfile
import tomllib
from pathlib import Path

HERE = Path(__file__).parent.parent

sys.path.insert(0, str(HERE))

from engine.render import render                 # noqa: E402
from engine.svgout import render_png, write_svg  # noqa: E402


def render_thumb(genome: dict, seed: int, photo: str,
                 out_png: Path, width_px: int = 850) -> Path:
    layers, page = render(genome, seed, photo_path=photo)
    pens = tomllib.loads((HERE / "pens.toml").read_text())
    with tempfile.NamedTemporaryFile(suffix=".svg") as tf:
        write_svg(layers, pens, page, tf.name)
        render_png(tf.name, str(out_png), width_px=width_px)
    return out_png


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    genome_path, photo, seed, out = sys.argv[1:]
    genome = json.loads(Path(genome_path).read_text())
    render_thumb(genome, int(seed), photo, Path(out))
    print(out)
