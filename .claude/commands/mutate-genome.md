---
description: Hatchwork evolution mutator — propose child genomes A/B from a parent (gen2)
allowed-tools: Read
---

The file at `$ARGUMENTS` is a mutation request JSON with fields:
`parent_genome`, `pick_history`, `temperature`, `steer` (nullable),
`parent_render_png` (nullable path), `pens` (valid pen names), and
`gate_feedback` (nullable — set when your previous reply was invalid).
Read it first. If `parent_render_png` is set, Read that image too — it is
the render of the parent genome; judge it visually before mutating.

You are the mutation operator in an interactive evolution loop for pen
plotter art (AxiDraw, real pens on real paper). Each generation the user is
shown two candidate renders, A and B, and taps the better one; the winner
becomes the next parent. Your job: propose child genomes A and B whose
difference carries maximum information about the user's taste.

## Genome schema
```
{
  "name": str,
  "page": {"size": "11x17"|"letter"|"a3"|..., "margin_mm": 15-30},
  "source": {"type": "photo", "params": {
      "n_bands": 3-7,        # tone bands, band 0 = LIGHTEST
      "band_gamma": 0.7-1.8, # >1 pushes thresholds darker => more bare paper
      "blur_mm": 0.3-3.0, "gamma": 0.6-1.6, "clahe_clip": 1-4,
      "tensor_window_mm": 1-6,     # orientation-field smoothing
      "canny_lo": 30-120, "canny_hi": 80-260}},
  "humanize": {   # global hand-feel post-pass; per-band override allowed
      "wobble_amp_mm": 0.05-0.5, "wobble_freq": 0.05-0.3,
      "end_jitter_mm": 0-1.5, "overshoot_prob": 0-0.5,
      "overshoot_mm": 0.5-2.5, "break_per_mm": 0-0.02,
      "break_gap_mm": 0.5-2.5},
  "bands": [ {"module": ..., "pen": ..., "params": {...},
              "humanize": {...optional override}}, ... ],
              # one entry per tone band, index 0 = lightest
  "edges": null | {"module": "contour_lines", "pen": ...,
                   "params": {"min_len_mm": 2-10}, "humanize": {...}}
}
```

## Modules and their params
- `empty` — bare paper. A real gene; restraint is a virtue.
- `fixed_hatch` — angle_deg, spacing_mm 0.4-3.0, spacing_jitter 0-0.3
- `cross_hatch` — angle_deg, spacing_mm, cross_delta_deg 20-90,
  cross_spacing_scale ~1.0, spacing_jitter
- `flow_hatch` — follows the photo's orientation field. spacing_mm,
  step_mm ~0.8, max_len_mm, fallback_angle_deg (used where the field is
  incoherent), min_coherence 0-0.3, angle_offset_deg (0 = follow form,
  90 = hatch ACROSS the form)
- `contour_hatch` — concentric inward offsets of the band boundary, topo
  feel. spacing_mm, spacing_jitter, max_rings
- `scribble_fill` — meandering strokes to a target density. spacing_mm,
  step_mm, curl 0-1.5, curl_scale 0.02-0.15, stroke_len_mm 50-400
- `solid_fill` — dense back-and-forth reading as solid ink.
  spacing_mm 0.35-0.6, angle_deg
- `contour_lines` — outline layer from the edge map. min_len_mm

Every `pen` field must be one of the names in the payload's `pens` list.

## Quality rubric (what a good render looks like)
- lines follow form where the genome says so, not one global angle
- ≥4 distinguishable tone treatments; darkest near-solid, lightest bare paper
- genuine negative space; ragged human endings; cross-hatch reads intentional

## Mutation policy
- A and B must differ MEANINGFULLY from each other and from the parent —
  the pick has to carry information.
- temperature "explore": differ at the structural level (which modules are
  assigned to which bands, edges on/off, pen assignment, n_bands).
- temperature "refine": keep structure, vary strategy/params (angles,
  spacings, humanize character, band_gamma).
- pick_history shows "both_bad": wrong neighborhood — jump structurally,
  try a genuinely different idea in at least one child.
- `steer` is set: translate it into genome vocabulary and BRACKET it —
  child A leans hard into the direction, child B blends it with the current
  style, so the pick tells you how far to go, not just yes/no.
- `gate_feedback` is set: your previous reply failed validation for the
  stated reason; fix exactly that.

Your FINAL message must be ONLY a single JSON object — no markdown fences,
no prose before or after:

{"rationale": "<=2 sentences on the A/B contrast", "child_a": {...full genome...}, "child_b": {...full genome...}}
