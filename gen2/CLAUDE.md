# Hatchwork v3 (gen2)

Pen plotter art engine + interactive style evolution. Full design: `design.md`.
Target hardware: AxiDraw V3/A3, 11×17 default page (SVG + Inkscape is the
contract — nothing may depend on the plotter itself). Plot workflow:
`plotterpi/WORKFLOW.md`. Python env: repo-root `.venv`.

## Hard rules

- **Purity**: `render(genome, seed)` is a pure function, reproducible forever.
  No `datetime.now()`, no unseeded RNG anywhere in `engine/`. Golden tests
  compare the *raw* SVG (pre-vpype; vpype embeds timestamps in metadata).
- **Seed discipline**: A/B candidates always share the same seed and differ by
  genome only. Rerolling seed is an explicit user action creating siblings.
- **Humanization is a shared post-pass** (`engine/humanize.py`) — never bake
  wobble/jitter/overshoot into a renderer module. Modules emit clean polylines.
- **Wobble samples page space** (x,y in mm), never per-line parameter space,
  or parallel lines wobble in sync and the eye catches it instantly.
- **One px↔mm transform**: `engine/page.py:Page`. No other coordinate math
  between image pixels and page mm, anywhere.
- Engine stays importable and headless: no stdin, no print (use logging),
  no server dependencies.
- Orientation fields are periodic — smooth/average only in doubled-angle (2θ)
  space.
- vpype `linesimplify` tolerance stays ≤0.05mm (well under pen width) or it
  erases the humanization wobble.

## Layout

- `engine/` — page, geom, photo (source → structure_ctx), hatch (modules),
  humanize, svgout. Modules consume `structure_ctx`, never the photo.
- `decompose/` — OFFLINE scene decomposition (`python -m decompose
  <photo>`): SAM + DepthAnything freeze a scene plan
  (`<stem>.scene.{npz,json,png}`) next to the photo — true object regions
  with depth order (0 = farthest) and quantized tone (0 = lightest).
  The ONLY place torch/transformers may be imported; model inference
  never runs inside render() (not reproducible across versions — the
  frozen plan is source input, like photo bytes). Engine-side reader:
  `engine/scene.py`. Genomes consume it via
  `"select": {"type": "scene", "ids"|"depth_rank"|"tone_level": ...}`
  zones plus zone-level `"base"` (whole-object pass — one committed
  directional treatment per surface; the fix for tone-band confetti) and
  `"keyline_mm"` (white seam between objects). See genomes/alpine_scene
  and docs/prior-art.md for why this layer exists.
- `evolve/` — M2 loop: store (SQLite tree), mutator, preview, cli
  (`python -m evolve.cli <photo>`). The mutator shells out to
  `claude -p "/mutate-genome <payload>"` (command:
  repo-root `.claude/commands/mutate-genome.md`) — subscription-billed, NOT
  the Anthropic SDK; ANTHROPIC_API_KEY is stripped from the subprocess env
  so it can't silently bill the API. The command SELF-CHECKS: it renders
  its own candidates via `evolve/preview.py`, views the PNGs, and revises
  until both pass the rubric — never show the user an unseen render.
  Degrades to a seeded RandomMutator when the claude CLI is absent
  (or `--random`).
- `review/` — THE review UI (`python -m review serve` → localhost:8787;
  `python -m review build` regenerates, the open page auto-reloads).
  Static site under `runs/review/`: marks (every module swatch + gradient
  response + measured coverage, sorted value scale), pipeline (the active
  genome×photo pair stage by stage), translation (per-mass promise vs
  delivered, verdict map), iterations (content-addressed archive of every
  genome state with diffs). **Discipline: everything in this repo is
  judged by eye, through this UI.** Any new visual capability (module,
  field, pipeline stage, test) gets a section or stage here in the same
  change; after visual work, rebuild and LOOK before telling the user.
  The active hand-loop pair lives in `review/build.py:ACTIVE`.
- `m0.py` — M0 CLI: photo → banded fixed-angle hatch → humanize → layered SVG.
- `pens.toml` — pen inventory; genome layers reference pen names.
- `tests/fixtures/` — synthetic + cropped test sources (`make_fixture.py`).
- `runs/` — outputs, gitignored.

Milestones (design.md §7): M0 engine substrate ✅ → M1 module architecture ✅ →
M2 headless evolution CLI ✅ → M3 procedural/hybrid sources → M4 UI →
M5 steering → M6 code mutations.

**Current focus (2026-07): the vocabulary ladder — docs/vocabulary.md.**
Rebuild bottom-up with visual gates: L0 strokes (`engine/strokes.py`,
review strokes tab) → L1 arrangements (factor modules into
arrangement × stroke × spacing-law) → L2 regions (gen1 ops: z-occlusion,
material-union hatching, composite outline; abstract testbed) → L3 forms
→ L4 composition. No level advances until the user signs off on its
review-UI sheet. Evolution restarts only at L4, over the full factored
genome.

## Visual quality rubric (score 0–2 each)

- Lines follow form/field, not one global angle (unless genome says so)
- ≥4 distinguishable tone treatments; darkest near-solid, lightest bare paper
- No two adjacent lines perfectly parallel and evenly spaced under zoom
- Ragged endings: jitter, some overshoots, some gaps
- Cross-hatching only where assigned; offset angle reads intentional
- Genuine negative space (restraint)
- Sensible per-pen layers; no orphan micro-segments (<0.5mm) after vpype
- Thumbnail test: reads as hand-inked at small size
