# Prior art: photo → pen-and-ink composition (deep-research synthesis, 2026-07-15)

Verified survey (104-agent fan-out, 22 sources fetched, 25/25 claims
confirmed 3-0 by adversarial verification) of everything relevant to the
core question: *why does bottom-up hatching look compositionally dead, and
what architecture fixes it?*

## The 30-year-old verdict

Every classic pen-and-ink system automates **mark synthesis** but
delegates **composition** to a human. This is not our discovery — it is
stated in the primary sources:

- **Winkenbach & Salesin, SIGGRAPH 1994** ([pdf](https://www.cs.ucdavis.edu/~ma/SIGGRAPH02/course23/notes/papers/Winkenbach.pdf)) —
  prioritized stroke textures (add strokes in priority order until target
  tone is reached; tone and texture from the same strokes). Input is a 3D
  model, so composition comes free from geometry. Even then, detail
  placement ("indication") defeated automation: *"Clearly, a purely
  automated method for artistically placing indication is a challenging
  research project. We therefore decided to compromise and implement a
  semi-automated method"* — a human places detail segments, a distance
  falloff gates strokes elsewhere.
- **Salisbury et al., SIGGRAPH 1997** ([pdf](https://cs.colby.edu/courses/S19/cs365/papers/salisbury-penAndInk-SIG97.pdf)) —
  the canonical *photo-input* architecture, and the closest ancestor of
  gen2. Its IR is exactly a per-layer triple: **grayscale tone target +
  per-pixel direction field + stroke exemplars**, rendered by a greedy
  importance loop (place stroke at greatest tone deficit until below
  threshold — even spacing falls out). Output is genuinely plottable
  B-spline strokes (665–56k per illustration). But the direction field is
  **hand-painted with comb brushes**, and the paper concedes *"Some
  automated assistance in detecting object boundaries would be valuable."*
- **Ostromoukhov, Digital Facial Engraving, SIGGRAPH 1999** ([pdf](https://w3.impa.br/~lvelho/ip/papers/ostroeng.pdf)) —
  closest to the engraving look: layered architecture, region masks,
  per-layer merging rules, direction fields from Coons patches. The patch
  border curves are **drawn by hand in Illustrator** along facial
  features, and the output is a raster halftone ("universal copperplate"
  dither), not plottable strokes.
- **Durand et al., EGWR 2001** ([link](https://people.csail.mit.edu/fredo/PUBLI/Drawing/)) —
  formalized the split in its title: "Decoupling Strokes and High-Level
  Attributes" — user places strokes, computer matches tone via a
  thresholding stroke model.
- **Hertzmann, IEEE CGA 2003 survey** ([pdf](https://www.dgp.toronto.edu/~hertzman/sbr02/hertzmann-cga03.pdf)) —
  the era's flat verdict on stroke-based rendering: these algorithms
  *"are useless without human control"* — every aesthetic decision must
  come from an artist. Same survey documents **Jobard–Lefer evenly-spaced
  streamlines** (seed ≥ d from existing curves, trace until within d of
  another) — guaranteed non-crossing, bounded-spacing polylines; the
  plotter-native stroke primitive (vpype-flow-imager implements it).

**Consequence:** gen2's "tone bands + orientation field + mark modules"
is the Salisbury back-end, faithfully rebuilt. What Salisbury had that
gen2 lacked is the *human* painting the direction field and tone targets
per object. The scene plan (decompose/) is the mechanization of that
human: SAM regions ≈ the hand-drawn region boundaries, depth ordering ≈
draw order, quantized per-region tone ≈ the artist's committed value
decisions, zone-level `base` pass ≈ Salisbury's per-layer treatment.

## The modern split

- **Compositionally aware but raster:** Chan et al., *Informative
  Drawings*, CVPR 2022 ([arXiv](https://arxiv.org/abs/2203.12691)) —
  unpaired image translation with a geometry loss (depth must be
  recoverable from the drawing) and a CLIP semantic loss. Knows *what
  matters* in the scene; emits pixels, not strokes.
- **Vector-native but sparse:** the diffvg family — CLIPasso
  ([arXiv](https://arxiv.org/abs/2202.05822)), CLIPDraw, VectorFusion,
  DiffSketcher, SVGDreamer, unified in
  [PyTorch-SVGRender](https://github.com/ximinng/PyTorch-SVGRender) —
  optimize explicit Bézier strokes by gradient. Genuinely plottable, but
  built for minimal abstraction (dozens of strokes), not dense tonal
  engraving; open question whether the optimization survives 10⁴ strokes
  with bounded spacing.
- **The only verified hybrid:** Dev 2025, IEEE CGA
  ([arXiv](https://arxiv.org/pdf/2506.00870)) — rule-initialized strokes
  refined by a network, blended per-stroke (s* = γ·neural + (1−γ)·rules).
  A *conceptual proposal in a magazine column*, not an implemented
  system.
- **Community practice:** mostly bottom-up (StippleGen, TSP art,
  vpype-flow-imager, DrawingBotV3) — which is exactly why plotter photo
  work shares the "screen door" texture-without-composition look.
  [plottter](https://github.com/pywkt/plottter) (AI depth maps +
  segmentation feeding hatching modes) is the closest working neighbor to
  our decompose stage. The documented AI→plot path is no-code tracing
  (AI image → contrast cleanup → Inkscape Trace Bitmap → AxiDraw,
  [aestheticdata.eu](https://aestheticdata.eu/how-to-use-generative-ai-to-createpen-plots/));
  the vectorization literature confirms why that's weak for engravings —
  junction failures on clean line drawings are a documented failure mode
  ([Stroke Vectorization, ECCV 2020](https://www.ecva.net/papers/eccv_2020/papers_ECCV/papers/123580579.pdf),
  [ACM TOG 2018](https://dl.acm.org/doi/fullHtml/10.1145/3202661)), and
  centerline tracing (autotrace/Inkscape) exists precisely because edge
  tracing doubles every stroke.

**Research caveat:** claims about tracing failure modes, plotter
community pipelines, and SAM/depth-based hatching largely did not survive
adversarial verification (thin/absent sources) — absence of a verified
"someone already did this" is not proof nobody has, but nothing surfaced.

## Where this leaves the architecture

The unfilled slot, per the verified record: **automatically producing the
composition plan** (tone map + direction field + region decomposition)
that every classic system required a human to author, then feeding it to
the mark-synthesis machinery that has worked since 1994. That is the
scene-plan architecture:

```
photo ──► decompose (SAM + depth, offline, frozen)──► scene plan ──► engine (zones/base/keyline + modules) ──► pens
photo ──► AI engraving raster (img2img) ──► extract plan from the STYLIZED raster ──► same engine   [M3d, pending]
```

The second front-end is the genuinely novel move: the generative model
performs the artistic simplification (committed values, form-following
texture, scalloped object vocabulary), and plan extraction from a flat
high-contrast engraving is far easier than from a photo. Nobody in the
verified record has built it.

Open questions worth testing (from the research):
1. Do AI engraving rasters carry locally coherent direction fields, or do
   they only read at viewing distance? (Structure-tensor probe on the
   reference AI images answers this in an afternoon.)
2. Jobard–Lefer streamlines as a `flow_hatch` upgrade for guaranteed
   even spacing in base passes.
3. Winkenbach's "indication" (detail near hand-picked/salient loci,
   falloff elsewhere) as a cheap composition gene.
