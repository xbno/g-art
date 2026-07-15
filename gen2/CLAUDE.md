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
- `m0.py` — M0 CLI: photo → banded fixed-angle hatch → humanize → layered SVG.
- `pens.toml` — pen inventory; genome layers reference pen names.
- `tests/fixtures/` — synthetic + cropped test sources (`make_fixture.py`).
- `runs/` — outputs, gitignored.

Milestones (design.md §7): M0 engine substrate ✅ → M1 module architecture →
M2 headless evolution CLI → M3 procedural/hybrid sources → M4 UI →
M5 steering → M6 code mutations.

## Visual quality rubric (score 0–2 each)

- Lines follow form/field, not one global angle (unless genome says so)
- ≥4 distinguishable tone treatments; darkest near-solid, lightest bare paper
- No two adjacent lines perfectly parallel and evenly spaced under zoom
- Ragged endings: jitter, some overshoots, some gaps
- Cross-hatching only where assigned; offset angle reads intentional
- Genuine negative space (restraint)
- Sensible per-pen layers; no orphan micro-segments (<0.5mm) after vpype
- Thumbnail test: reads as hand-inked at small size
