# The vocabulary ladder — art rebuilt from the stroke up

2026-07-21. The rigorous reimplementation plan. Companion docs:
`composition-order.md` (the verified pedagogy: Guptill/Payne/Loomis/W&S)
and `prior-art.md` (30 years of systems: mark synthesis is solved,
composition is the open slot).

## Why this document exists

The engine grew top-down: photo → bands → modules, then scene plans, then
the plan compiler. It works (hand_peak v2, 24/25 translation), but the
sweeps all converged on the same look because the *vocabulary* under them
is thin: ~10 monolithic modules, each hard-wiring one stroke shape to one
placement policy to one spacing rule. Evolution can only recombine what
the vocabulary can say. Salisbury/W&S synthesized marks richly in 1994-97
*because their stroke layer was a first-class citizen* (exemplar strokes,
prioritized textures). Ours never was.

So: rebuild bottom-up, one level at a time, **each level exhaustively
enumerated, visually reviewed in the UI, and signed off before the next**.
The gate question at every level: *"is this everything we need for now?"
— answered by eye, in the review UI, together.*

## The ladder

Each level has NOUNS (the things) and OPERATIONS (what can act on them).
A thing at level N is composed of level N-1 things; operations at level N
never reach below N-1 (strict layering — this is what keeps the genome
space clean).

```
L0 STROKE        one continuous pen path (the atom)
L1 ARRANGEMENT   a policy that tiles/flows strokes through space  ("pattern"
                 = arrangement × stroke × spacing-law — combinatorial, not
                 hand-picked pairings)
L2 REGION        bounded 2D areas: primitives, booleans, z-occlusion,
                 material union, boundary treatments
L3 FORM          region(s) + committed value + pattern stack + shading
                 structure = an OBJECT that reads as lit matter
L4 COMPOSITION   arrangement of forms on the page: value plan, scheme,
                 focal, depth order, negative space
```

Cross-cutting (apply at every level, never baked in):
- `humanize` — shared post-pass, page-space wobble (hard rule, unchanged)
- `tone_gate` / `emphasis_gate` — survival modulation by tone / feature
  distance
- `seed` discipline & purity — every generator `f(params, rng) → geometry`

---

## L0 — STROKE (the atom)

A stroke is ONE GESTURE — 1..few pen touches (a broken line, a
cross-tick, a tuft are single gestures with lifts) — generated in a local
frame (origin at start, direction +x, mm units), placed by L1 via rigid
transform. Registry: `engine/strokes.py:STROKES`, grouped by family
(~70 kinds; the registry is the truth, this table just names the families):

| family    | contents |
|-----------|----------|
| geometric | analytic references: line arc crescent s_curve sine zigzag spiral dot |
| ruled     | hatching atoms with hand character: hand/taper/flick lines, j_entry, fishhook, engraver's swell, wedge dab, double/sketch/broken lines, dry_brush, stitch_run |
| curved    | single-bend gestures: hand_arc, hook_tail, ogee, sumi comma, teardrop, lash, whip, catenary, ribbon_s, c_flick |
| wave      | uneven periodics: hand_wave, ripple, swell, chirp, serpentine, crimp, seismo, flame_wave |
| zigzag    | angular runs: hand_zigzag, lightning, sawtooth, staircase, crenel, needle_run |
| bump      | scallop kin: hand_scallop, cloud_run, fish_scale, garland, wave_crest |
| loop      | trochoid kin: hand_loop, chain, figure-8, knot_line, coil, curlicue, pigtail |
| spot      | dabs: hand_spiral, bean, pebble, squiggle_dab, cross/asterisk ticks, tuft |
| organic   | noise-native: fbm_ridge, jitter_walk, bark_line, root_line, hairline, meander_scribble |

Machinery every kind shares: `_fbm` (1D fractional-Brownian noise — the
organic backbone), `_uneven_phase` (periodics that breathe instead of
ticking), `_from_heading` (curvature-space construction: knots, hooks,
bark), `_roughen`/`_hand` (normal-displacement character). Character
(drift, per-cycle unevenness, entry/exit behavior) lives IN the kind;
page-space wobble stays in humanize. Intrinsic rng variation is part of
what a kind is — the review sheet shows three seeds per kind.

L0 operations: `scale`, `mirror`, `reverse`, param jitter (rng). NOT
operations here: wobble (humanize), pressure taper (plotter can't — the
engraver's swell fakes it with geometry), color (pen is L3 assignment).

Gate: the family sheets in the review strokes tab. Questions: which kinds
are keepers, which are still clip-art, what's missing?

## L1 — ARRANGEMENT (pattern = arrangement × stroke × spacing-law)

An arrangement takes (region, field ctx, stroke spec, spacing law) and
returns placed strokes. Current modules collapse into this factored form:

| arrangement    | today's module     | placement rule |
|----------------|--------------------|----------------|
| parallel       | fixed_hatch        | rows at angle θ |
| cross          | cross_hatch        | 2+ parallel passes, angle set |
| flow           | flow_hatch         | streamlines along field |
| fan            | fan_hatch          | radiate from pivot |
| shingle        | shingle_hatch      | clustered swatches, per-swatch θ |
| contour_offset | (NEW)              | inward offsets of the boundary |
| scatter        | (stipple, NEW)     | blue-noise density placement |
| scribble       | scribble_fill      | one continuous meander |
| mosaic         | mosaic/patch_hatch | subdivide region, per-cell parallel |

Spacing laws are first-class (gen1's contribution, generalized):
`regular | exponential(ratio) | jittered(σ) | graded(by field) | dashed(duty)`.
Angle SETS from gen1 ([0,90], [15,105], [0,30,60,90]…) are cross params.

The payoff: `parallel×scallop`, `flow×loop`, `contour_offset×wave`,
`scatter×spiral` … ~9 arrangements × 12 strokes × 5 spacing laws ≈ 500
patterns from ~26 parts, every one reachable by the mutator flipping one
gene. Gate: the arrangement×stroke matrix in the UI; darkness calibration
(marks.json v2) regenerated over the factored space.

## L2 — REGION

Where gen1 (`gen1/20250226/hatch_hatch.py`) gets absorbed — its real
inventions were all region operations:

- primitives: circle, rect, triangle, blob (noise-deformed), polygon;
  plus raster masks from the photo pipeline (unchanged)
- **z-occlusion** → *effective regions*: higher-z shapes subtract from
  lower (gen1 `calculate_effective_regions`)
- **material union**: same-material regions merge and are hatched as ONE
  field — continuous pattern flowing across separate shapes (gen1
  `calculate_unified_color_regions`; the strongest idea in that file)
- **composite outline**: outline the UNION silhouette, not each shape
  (gen1 `find_composite_outline`); interior boundaries optional
- booleans: clip/subtract/union/ring(buffer); keyline (white seam);
  inset/outset; holes
- boundary treatments: outline pen, keyline gap, contour_offset rows,
  ragged edge (gate near boundary)

Gate: an abstract-composition testbed — regenerate gen1-style abstract
sheets (shapes + z-order + material hatching) with the new stack. No
photo, no scene: vocabulary expressivity judged naked. If abstract sheets
all look samey, the vocabulary is still too thin to bother evolving photos.

## L3 — FORM (object)

Region(s) + committed value + pattern stack + shading structure:
- committed value per form (the plan compiler's levels — exists)
- calibrated stack lookup (marks.json — exists, regenerated over L1 space)
- shading structure inside a form (Loomis, composition-order §6): lit /
  halftone / core-shadow planes from normals or relight; texture only
  after construction
- edge logic: outline only where adjacent values fail to separate (§4);
  keyline between overlapping forms
- object glyphs (tree stamps, cloud lobes, rock facets) become forms with
  intrinsic pattern bindings — design.md M3c lands here

Gate: single-object studies (one boulder, one tree, one cloud) each
rendered under several shading structures; pipeline tab per study.

## L4 — COMPOSITION

Everything in `composition-order.md`, now operating on L3 forms:
- value plan: k-level posterize, principal light + dark elected (§1)
- arrangement doctrine: adjacent-order over accuracy → tonecheck v2 (§2)
- Payne schemes as genes (steelyard, S-curve, pyramid…), rejection rules
  as automated critics (never halve, no equal masses/spacing…) (§0)
- focal: single center, sharpest contrast + densest detail, falloff (§5)
- depth order, occlusion (L2 machinery), atmospheric recession
- the photo/scene pipeline (decompose/) becomes ONE source of L4 plans;
  gen1-style procedural abstract plans are another; AI-engraving
  extraction (prior-art M3d) a third

Gate: the plan compiler retargeted at the factored vocabulary; hand-loop
pieces (hand_peak line) re-expressed; translation + arrangement scores in
the UI.

---

## Build order & discipline

- **V0 strokes** → strokes tab, alphabet + sweeps. SIGN-OFF, then
- **V1 arrangements** → factor existing modules into arrangement×stroke×
  spacing; matrix tab; recalibrate marks.json v2. SIGN-OFF, then
- **V2 regions** → shapely-native region algebra; abstract testbed
  (gen1 reborn); sign-off on abstract sheets. Then
- **V3 forms** → object studies. Then
- **V4 composition** → plan compiler v2 over the new stack; evolution
  gets switched back on ONLY here, with the genome spanning all levels.

Rules for every phase: pure & seeded; clean polylines (humanize is a
post-pass); one px↔mm transform; every new noun/op lands in the review UI
in the same change; nothing advances without the visual gate; old modules
keep working until their factored replacements match them pixel-for-eye.
