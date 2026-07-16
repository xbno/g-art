# The canonical order of composition (verified pedagogy → pipeline)

Deep-research synthesis, 2026-07-16 (103 agents, claims verified 3-0
against primary texts — Guptill quoted verbatim from the archive.org
scan). Full trail: deep-research run `wf_4bfbca09-23a`.

Sources: Guptill *Rendering in Pen and Ink*
([archive.org](https://archive.org/details/rendering-in-pen-and-ink-arthur-l.-guptil)),
Payne *Composition of Outdoor Painting*, Loomis, atelier pedagogy,
Winkenbach & Salesin 1994
([pdf](https://www.cin.ufpe.br/~sbm/p91-winkenbach.pdf)) which *derives
its principles from Guptill directly*, Praun et al. *Real-Time Hatching*
2001 (tonal art maps). Unverified gaps: Dow's notan ordering, Harold
Speed, Alphonso Dunn — absent from surviving claims, not refuted.

## The order

**0. Edit the masses (Payne).** The scene is raw material: simplify
ragged contours, weld equally-spaced elements into single masses, reduce
to ONE opening and ONE interest, choose a mass-arrangement scheme
(Payne names ~15: Steelyard, S-curve, Pyramid, Silhouette, ...).
Negative constraints, mechanically checkable: never halve the canvas;
no equal masses or equal spacing; no three equal divisions; nothing
mechanically centered; not crowded.
→ *ours:* fusion masses + merge passes (partial). GAP: the Payne
rejection rules as automated critic checks; scheme vocabulary as
composition genes.

**1. Value plan before anything (Loomis, atelier, Guptill).** 3-4 tone
thumbnails precede drawing; atelier stage 2 is a strict two-value
light/dark massing; Guptill demands a separate pencil value study fixing
every tone's darkness *before the pen touches paper*, and the principal
light and principal dark areas are selected immediately.
→ *ours:* fusion "masses committed to posterize k3/k4" IS this artifact.
GAP: explicitly electing the principal light + principal dark mass.

**2. The value doctrine: ARRANGEMENT over accuracy (Guptill, restated
verbatim by W&S).** Pen's range forces simplification — lights pushed
to paper, darks to black, one general value per mass. "It is not the
absolute correctness of each individual tone... but the right
arrangement or disposition of the various values." Tone may be *forced*
(contrast enhanced, shadows invented) to disambiguate objects.
→ *ours:* THIS REDEFINES TONECHECK. Score the preserved *ordering of
adjacent masses* (is A still darker than B?), not per-cell absolute
darkness — which is exactly how the woolly bigsweep renders gamed the
old metric. tonecheck v2 = pairwise adjacent-mass order agreement.

**3. Tone → texture via a pre-built value scale (Guptill ch.5; W&S
prioritized stroke textures; Praun TAMs).** Guptill's graded hatching
scales (5 steps, up to 9) are built as an exercise BEFORE pictorial
work; W&S add strokes in priority order *only until the target tone is
reached*; Praun quantizes tone into a fixed sequence of hatch images.
→ *ours:* `calibrate.py` + `runs/calibration/marks.json` is the scale
(measured, not assumed; black03 single-pass ceiling ≈ 0.59 — stacks
required for true darks). GAP: the plan compiler — per-mass lookup that
picks the mark stack whose measured value matches the mass's level.

**4. Render by values, from the center of interest outward; outline
last and minimal (Guptill; W&S).** Never outline-everything-first; work
the values systematically; from photos, start at the focal center and
stop when the message is conveyed. W&S draw outline ONLY where adjacent
tones are too similar to separate regions.
→ *ours:* GAP with a one-line rule: contour_lines gated to boundaries
whose two sides differ by < ~1 value level. Plot-order = focal-first is
also a natural vpype sort criterion.

**5. Focal emphasis decided last, and single (Guptill; atelier edges;
W&S indication).** One center of interest carries the sharpest
contrasts and densest detail; everything else subordinated; competing
equal centers destroy the drawing. Detail fades with distance from
user/salience-placed loci ("indication" — automation acknowledged as
unsolved in 1994; our emphasis pass automates the falloff).
→ *ours:* `emphasis` exists but is feature-line based. GAP: a single
FOCAL POINT gene (position + radius) that concentrates both detail AND
the sharpest value contrast, with Payne's not-centered rule as a check.

**6. Form planes within masses (Loomis).** Light → halftone → shadow,
reflected light inside the shadow; texture/character only after
construction.
→ *ours:* relight (n·L) gives the planes; normals give direction.

## Pipeline restated

fusion value plan (masses + k3/4 levels, principal light/dark elected)
→ calibrated mark stacks per level (marks.json) → direction from
normals per mass → texture where variance says so → outline only where
value contrast fails → emphasis/detail at ONE focal point → tonecheck
v2 scores arrangement, Payne rules veto bad layouts.
