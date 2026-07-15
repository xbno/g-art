# Hatchwork v3 — Design Doc (handoff)
*Interactive style evolution for pen plotter art. Sources: photos, procedural/abstract, or hybrid. Output: multi-layer Inkscape-ready SVG. Interface: A/B picks growing a lineage tree of styles you can pin, branch, and steer with prompts.*

## 0. Summary of the idea

The rendering engine turns **structure** (a flow field, tone-band masks, an edge map) into **plotter line art** (hatching, cross-hatch, scribble, solids, contours) with deliberate human imperfection, split into per-pen SVG layers. Where the structure comes from is pluggable: a photo, a procedural generator, or a hybrid of both.

The user-facing product is an **evolution loop**: each generation renders two candidates (A/B) from meaningfully different genomes, the user taps the better one, and the winner parents the next pair. Every candidate is a node in an append-only lineage tree. Any node can be pinned (named style), branched from later (optionally with a new steering prompt or new source), or re-rendered against a different photo. Claude is the mutation operator, with vision, and can escalate to writing new renderer modules in code when the user's direction exceeds the current vocabulary.

This is interactive evolutionary computation (Picbreeder lineage) with an LLM mutator — the LLM is what keeps the mutation vocabulary from running dry.

## 1. Core concepts

**Genome** — JSON document fully specifying a render. Four gene levels:

1. **Source genes** — where structure comes from (section 3).
2. **Structural genes** — which renderer modules are active and how tone regions map to them. `{sky: flow_hatch, midtones: contour_hatch, shadows: cross_hatch + double_stroke}` vs `{sky: empty, midtones: scribble_fill, shadows: solid_fill}` are different organisms.
3. **Strategy genes** — discrete choices inside modules: angle mode (follow/cross/fixed), streamline vs advected-parallel, break style, band count, pen assignment.
4. **Continuous params** — spacing, wobble amplitude, field strength, jitter %, etc.

**Render** — `render(genome, seed) → SVG + PNG`. Pure function, reproducible forever. (The photo, if any, is referenced *inside* the genome's source genes by content hash.)

**Node** — one rendered candidate: `{id, parent_id, genome, seed, thumbnail, chosen: bool, prompt_context, timestamp, notes}`. Append-only. Nothing is deleted; returning to pair 7 a week later is clicking a node.

**Pin** — named bookmark on a node ("gnarly tree style", "blue mountain minimal"). Pins are the style library; exportable as presets, applicable to any new source without evolving.

**Branch** — a new evolution run from any node, optionally with a new prompt and/or new source. The tree is a DAG grown by branches.

## 2. The loop (one generation)

```
        ┌────────────────────────────────────────────┐
        │ parent genome + recent pick history         │
        │ + optional user prompt / reference image    │
        ▼                                            │
   MUTATOR (Claude) ──► child genome A, child genome B│
        ▼                                            │
   ENGINE renders A and B                             │
        ▼                                            │
   UI shows A | B side by side (+ parent, ghosted)    │
        ▼                                            │
   user taps one (or: "both bad" / pin / done /       │
   steering prompt)                                   │
        └── winner becomes parent ────────────────────┘
```

### Mutation policy

The mutator maintains a **temperature** per gene level, annealed by behavior:

- **Fresh branch or explicit prompt** → hot: A/B differ at source/structural level. Two genuinely different ideas.
- **Consistent picks in one neighborhood for ~3–5 generations** → cooling: strategy genes, then continuous params. Refinement mode.
- **"Both bad" twice** → reheat; mutator treats it as "wrong neighborhood," jumps structurally, may ask a one-line question.
- **Prompt or pasted reference image** → temperature override + direction. The mutator (with vision) translates the reference into genome vocabulary and generates A/B to *bracket* the direction — A leans hard in, B blends with current style — so the pick communicates how far, not just yes/no.

**Why it doesn't run dry:** (a) source × structural genes are combinatorial — thousands of meaningfully distinct organisms before touching params; (b) **code mutations**: when a prompt demands something outside the module set ("woodcut solids", "stippled skies"), Claude Code writes and registers a new module. The gene pool grows with the user's taste.

### Two mutation tiers

- **Tier 1 — genome mutation** (JSON edit): seconds. Every normal generation. Anthropic API with vision: the mutator sees the parent render, pick-history thumbnails, and any reference before proposing children.
- **Tier 2 — code mutation** (new module): minutes, in Claude Code against the repo, gated by smoke tests (valid clipped polylines, pen-registry compliance, successful test render). Session continues on Tier 1 while Tier 2 cooks; the new module joins the pool when green.

### Seed discipline (critical)

A and B always share the same seed and differ by genome only — otherwise picks are noise about dice rolls, not style. Rerolling the seed is an explicit user action that creates sibling nodes marked as such.

## 3. Sources — photo, procedural, hybrid

Renderer modules never see a photo. They consume `structure_ctx`:

```
structure_ctx = {
  flow_field:  HxW orientation field,
  tone_bands:  list of region masks with band index,
  edge_map:    binary/strength map,
  meta:        page size, dpi, working resolution
}
```

Anything that can produce a `structure_ctx` is a **source**. Source genes select and parameterize one:

**`photo` source** — the v1 pipeline: grayscale/CLAHE/blur → structure tensor → smoothed orientation field (average in doubled-angle space); brightness quantization → tone bands; Canny → edge map. Params: blur, contrast, gamma, band thresholds, tensor window, field smoothing.

**`procedural` source** — generators composed by genes:
- *Flow fields*: simplex/Perlin noise fields, spirals, vortices/attractors, wave interference, radial fields, curl noise. Params: scale, octaves, turbulence, attractor positions.
- *Tone regions*: noise-threshold blobs, geometric compositions (circles, bars, grids, torn/irregular edges), gradients (linear/radial), Voronoi cells, layered combinations with boolean ops.
- *Edges*: boundaries of the generated regions.

**`hybrid` source** — mix per channel: e.g. photo flow field + procedural tone regions (a mountain's contours driving a non-representational piece), or procedural field + photo tone bands (a portrait's values rendered in swirling abstract line). Hybrids are first-class genes, not a hack — some of the most interesting territory is here.

**Composition genes (procedural/hybrid only).** Photos carry composition for free; abstract mode must encode it or evolution degenerates into uniform texture wallpaper: focal points (count/position/strength), density falloff from focals, negative-space budget (% bare paper, enforced), margin behavior (hard frame vs bleed vs ragged), symmetry/asymmetry bias. The mutator treats these as high-value structural-level genes.

## 4. Renderer module contract

```python
class RendererModule(Protocol):
    name: str
    param_schema: dict          # JSON schema; drives auto-generated advanced-panel UI
    def render(self, region_mask, structure_ctx, params, seed) -> list[Polyline]: ...
```

`structure_ctx` products are computed once per (source genes, source input) and cached. Modules only generate lines; **humanization is a shared post-pass** (wobble via simplex displacement, ±spacing variance, endpoint jitter, overshoots, break gaps, doubled strokes in dark bands) with per-module overrides — so every module, including future Claude-written ones, gets the hand-feel for free.

**Launch modules:** `flow_hatch`, `fixed_hatch`, `cross_hatch`, `contour_hatch` (follows band boundaries, topo feel), `scribble_fill`, `solid_fill` (dense back-and-forth reading as solid ink), `contour_lines` (outline layer from edge map), `empty` (bare paper is a real gene).

## 5. Storage & tree

- SQLite, single file. Tables: `sources` (photos by content hash + procedural defs), `nodes`, `pins`, `runs`, `modules` (registry incl. Claude-written, each pinned to a git SHA).
- Genomes are small JSON. Thumbnails (~400px PNG) on disk keyed by node id. Full SVGs regenerated on demand (pure function); stored only for pins as convenience.
- Project dir is a git repo; code mutations are commits referencing the requesting node. Each node records the module-registry SHA it rendered under, so genome time-travel and code time-travel stay consistent.

## 6. UI

**Evolve view (default, phone-friendly):** session source at top (photo thumb or procedural preview), A and B below, tap left/right. Buttons: ⟲ both bad · 📌 pin winner · ⤴ change source · ✏️ steer (prompt box, accepts pasted image). Ghosted parent thumbnail. Generation counter + temperature indicator ("exploring" ↔ "refining").

**Tree view:** zoomable DAG of thumbnails, chosen path highlighted, pins labeled. Tap a node → genome diff vs parent (human-readable), full-size re-render, branch-from-here, apply-to-new-source. Filters: pins / source / date.

**Export view:** any node → full-res multi-layer SVG through vpype (`linemerge`, `linesort`, `linesimplify`), physical page size in mm, Inkscape layers (`inkscape:groupmode="layer"`, label = "1 - blue 0.3"), plot-time estimate + path length per pen. Pin presets export/import as JSON.

**Advanced panel (hidden):** auto-generated sliders from param schemas, live on the current winner. Manual edits create nodes like any mutation; the tree doesn't care who mutated. Manual edits reset temperature to "refining."

## 7. Milestones

1. **M0 — Engine substrate.** Photo source → fixed-angle banded hatching → humanization → layered SVG, verified in Inkscape and on the physical plotter. *Definition of done: a plotted sheet that looks hand-hatched from arm's length.*
2. **M1 — Module architecture.** Module contract, 8 launch modules, genome schema, `render(genome, seed)` single entry point, structure_ctx caching. Photo source only.
3. **M2 — Headless evolution.** CLI loop: mutator via API proposes A/B, renders both, user types a/b in terminal. Node store, tree persistence, pins, branching by node id. *This milestone exists to iterate on the mutator prompt/policy cheaply — mutation quality is the whole product. Spend real time here.*
4. **M3 — Procedural + hybrid sources.** Generators, composition genes, source genes wired into the mutator's vocabulary.
5. **M4 — UI.** Evolve/tree/export views over FastAPI. Phone-usable.
6. **M5 — Steering.** Prompt box, reference-image analysis, temperature tuning, "both bad + three words why."
7. **M6 — Code mutations.** Tier 2 pipeline, module smoke tests, registry versioning.

## 8. Handoff notes for Claude Code

**Build conventions**
- Python 3.11+. `uv` or plain venv. Deps: numpy, opencv-python-headless, opensimplex (or `noise`), shapely≥2 (use STRtree for mask clipping — naive per-line clipping will be the bottleneck), svgwrite or stdlib xml, vpype (invoke as subprocess with documented CLI flags; its Python API is less stable), cairosvg or resvg for PNG rasterization, fastapi+uvicorn (M4+), anthropic SDK (M2+).
- Repo layout: `engine/` (sources, modules, humanize, export), `evolve/` (mutator, store, cli), `ui/` (M4+), `tests/`, `refs/` (style reference images), `tests/fixtures/` (2–3 small test photos), `runs/` (gitignored).
- Write a `CLAUDE.md` at repo root capturing: seed discipline rule, module contract, "humanization is a shared post-pass — never bake wobble into a module," genome schema location, and the rubric below.
- ANTHROPIC_API_KEY from env only; the tool must degrade gracefully to manual-slider mode when unset.
- Keep the engine importable and headless. The UI and the mutator are both clients of the same functions. No engine code may read stdin, print progress to stdout (use logging), or depend on the server.

**Testing strategy**
- Golden-file tests: fixed genome + seed + fixture photo → SVG must be byte-identical across runs (this enforces the pure-function property and catches accidental nondeterminism, the #1 practical bug risk).
- Module smoke test harness (also used to gate Tier 2 code mutations): returns polylines, all inside region mask ± overshoot tolerance, no NaNs, respects pen registry.
- One integration test per milestone that renders a full genome and validates SVG structure (layer names, units in mm, viewBox matches page size).

**Visual quality rubric** (used by the mutator's self-checks and by humans; score 0–2 each)
- Lines visibly follow form on curved surfaces (photo source) or field (procedural) — not one global angle unless the genome says so
- ≥4 distinguishable tone treatments; darkest reads near-solid, lightest is bare paper
- No two adjacent lines perfectly parallel and evenly spaced under zoom
- Ragged endings: jitter, some overshoots, some gaps
- Cross-hatching only where the genome assigns it; offset angle reads intentional
- Genuine negative space (restraint)
- Sensible per-pen layer separation; no orphan micro-segments (< 0.5 mm) after vpype
- Thumbnail test: at small size, does it read as hand-inked?

**Known gotchas**
- Orientation fields are periodic: smooth/average in doubled-angle space (2θ) or fields will cancel at 0/180° boundaries.
- SVG previews with 50k+ segments will choke browsers: decimate preview (cap segments, round coords) while exporting full fidelity.
- vpype `linesimplify` tolerance must stay well under pen width (~0.05 mm for 0.3 mm nibs) or humanization wobble gets smoothed away — the exact failure mode this project exists to avoid.
- cv2 uses y-down coords, SVG is y-down too, but plotters/physical pages need explicit mm mapping — centralize the transform in one place, day one.
- Simplex wobble must be sampled in *page space*, not per-line parameter space, or parallel lines wobble identically and the eye catches the correlation instantly.

**Working style with the human**
- Build strictly in milestone order; demo after each (M0/M1: rendered PNGs + an SVG to plot; M2+: run the CLI together).
- When a design decision is ambiguous, prefer the choice that keeps `render(genome, seed)` pure and the engine headless.
- Do not gold-plate the UI before M4. The CLI evolution loop is the proving ground.

## 9. Open questions (decide during build, with the human)

- "Both bad" + optional three-word why: cheap signal, big mutator value — probably yes at M5.
- Population strictly 2, or 3–4 on structural jumps? Start with 2; protect tap-left/tap-right simplicity.
- Multi-photo fitness at refinement time: render A/B against 2 sources in a 2×2 grid so picks reward the style, not one image? M5 toggle.
- Procedural preview in tree/evolve views: render tiny, or icon + genome summary? Decide by feel at M4.
- Plotter specifics: pen inventory (nib sizes, colors) belongs in a `pens.toml` the human edits; page sizes likewise. Ask for the plotter model at M0 to set defaults, but SVG+Inkscape is the contract, so nothing else may depend on the hardware.