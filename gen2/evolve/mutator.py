"""Mutation operators: Claude Code CLI (with vision) and a seeded random
fallback.

propose(parent, history, steer, parent_png, temperature) -> {
    "rationale": str, "child_a": genome, "child_b": genome
}
A and B always share the render seed downstream; they differ by genome only.

The Claude path shells out to `claude -p "/mutate-genome <payload.json>"`
(command lives in .claude/commands/mutate-genome.md at the repo root) — one
subprocess per generation, billed to the subscription, not API dollars.
ANTHROPIC_API_KEY is stripped from the subprocess env: with it set, the CLI
silently bills the API instead of the subscription.
"""

import copy
import json
import logging
import os
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path

import numpy as np

from engine.modules import MODULES

log = logging.getLogger(__name__)

HERE = Path(__file__).parent.parent      # gen2/
REPO_ROOT = HERE.parent                  # g-art/ (where .claude/commands is)
CLI_TIMEOUT = 1800  # the command renders + inspects its own candidates
MODEL = "claude-sonnet-5"  # mutator default; override with --model
                           # (claude-opus-4-8 for harder steering)
ALLOWED_TOOLS = ("Read,Write,"
                 "Bash(.venv/bin/python gen2/evolve/preview.py:*)")


def pen_names() -> list[str]:
    return list(tomllib.loads((HERE / "pens.toml").read_text()))


def validate_genome(g: dict) -> None:
    pens = set(pen_names())
    if not isinstance(g.get("bands"), list) or not g["bands"]:
        raise ValueError("bands missing")
    entries = list(g["bands"]) + ([g["edges"]] if g.get("edges") else [])
    for e in entries:
        if e.get("module") not in MODULES:
            raise ValueError(f"unknown module {e.get('module')!r}")
        if e["module"] != "empty" and e.get("pen", "black03") not in pens:
            raise ValueError(f"unknown pen {e.get('pen')!r}")
    json.dumps(g)  # must be serializable


def _extract_json(text: str) -> dict:
    """The command asks for bare JSON; tolerate fences/preamble anyway."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"no JSON object in CLI output: {text[:200]!r}")
    return json.loads(text[start:end + 1])


class CliMutator:
    """Tier 1 genome mutation via `claude -p /mutate-genome`, with vision."""

    def __init__(self, model: str | None = None,
                 payload_dir: Path | None = None):
        if not shutil.which("claude"):
            raise FileNotFoundError("claude CLI not on PATH")
        self.model = model or MODEL
        self.payload_dir = payload_dir or Path(tempfile.mkdtemp(
            prefix="mutate_"))

    def propose(self, parent: dict, history: list[dict],
                steer: str | None = None,
                parent_png: str | None = None,
                temperature: str = "explore",
                photo: str | None = None,
                seed: int | None = None) -> dict:
        workdir = self.payload_dir / f"work_{os.getpid()}"
        workdir.mkdir(parents=True, exist_ok=True)
        payload = {
            "parent_genome": parent,
            "pick_history": history[-8:],
            "temperature": temperature,
            "steer": steer,
            "parent_render_png": parent_png,
            "photo": photo,
            "seed": seed,
            "workdir": str(workdir),
            "pens": pen_names(),
            "gate_feedback": None,
        }
        for attempt in range(2):
            out = self._call(payload, attempt)
            try:
                validate_genome(out["child_a"])
                validate_genome(out["child_b"])
                return out
            except (ValueError, KeyError) as e:
                log.warning("mutator reply invalid (%s), retrying", e)
                payload["gate_feedback"] = str(e)
        raise ValueError("mutator produced invalid genomes twice")

    def _call(self, payload: dict, attempt: int) -> dict:
        self.payload_dir.mkdir(parents=True, exist_ok=True)
        path = self.payload_dir / f"req_{os.getpid()}_{attempt}.json"
        path.write_text(json.dumps(payload, sort_keys=True))
        cmd = ["claude", "-p", f"/mutate-genome {path}",
               "--output-format", "json", "--allowedTools", ALLOWED_TOOLS,
               "--strict-mcp-config", "--model", self.model]
        env = {k: v for k, v in os.environ.items()
               if k != "ANTHROPIC_API_KEY"}
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL,  # don't eat the
                              timeout=CLI_TIMEOUT, env=env,  # user's tty
                              cwd=REPO_ROOT)
        if proc.returncode != 0:
            raise RuntimeError(f"claude CLI exit {proc.returncode}: "
                               f"{(proc.stderr or proc.stdout)[:300]}")
        outer = json.loads(proc.stdout)
        out = _extract_json(outer["result"])
        log.info("  mutator: %.0fs, %s self-renders, $%.3f API-equiv",
                 outer.get("duration_ms", 0) / 1000,
                 out.get("renders", "?"),
                 outer.get("total_cost_usd") or 0)
        return out


class RandomMutator:
    """No-CLI fallback: seeded structural/param perturbations."""

    STRUCTURAL_MODULES = ["empty", "fixed_hatch", "cross_hatch", "flow_hatch",
                          "contour_hatch", "scribble_fill", "solid_fill"]

    def __init__(self, seed: int | None = None):
        self.rng = np.random.default_rng(seed)

    def propose(self, parent: dict, history: list[dict],
                steer: str | None = None,
                parent_png: str | None = None,
                temperature: str = "explore",
                photo: str | None = None,
                seed: int | None = None) -> dict:
        return {"rationale": f"random {temperature} mutation (no claude CLI)",
                "child_a": self._mutate(parent, temperature),
                "child_b": self._mutate(parent, temperature)}

    def _mutate(self, parent: dict, temperature: str) -> dict:
        g = copy.deepcopy(parent)
        if temperature == "explore" and self.rng.random() < 0.7:
            band = g["bands"][int(self.rng.integers(len(g["bands"])))]
            band["module"] = str(self.rng.choice(self.STRUCTURAL_MODULES))
            band.pop("params", None)
            if band["module"] != "empty":
                band.setdefault("pen", str(self.rng.choice(pen_names())))
        self._scale_numbers(g.get("humanize", {}))
        for band in g["bands"]:
            self._scale_numbers(band.get("params", {}))
        if g.get("edges"):
            self._scale_numbers(g["edges"].get("params", {}))
        self._scale_numbers(g.get("source", {}).get("params", {}),
                            int_keys={"n_bands", "canny_lo", "canny_hi"})
        return g

    def _scale_numbers(self, params: dict, int_keys: set | None = None):
        for k, v in params.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            if self.rng.random() < 0.4:
                nv = float(v) * float(self.rng.lognormal(0, 0.18))
                params[k] = round(nv) if k in (int_keys or set()) \
                    else round(nv, 3)


def make_mutator(force_random: bool = False, seed: int | None = None,
                 model: str | None = None,
                 payload_dir: Path | None = None):
    """Claude Code CLI if on PATH; else degrade to random mutations."""
    if not force_random:
        try:
            return CliMutator(model=model, payload_dir=payload_dir)
        except FileNotFoundError as e:
            log.warning("%s; falling back to random mutations", e)
    return RandomMutator(seed)
