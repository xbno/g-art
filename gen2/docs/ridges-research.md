# "Ridge lines everywhere" — research memo (2026-07-21)

The user's insight: THE summit ridge works because hatch direction flips
across it. Generalize: *every* fold in the surface — every locus where
adjacent facets disagree in orientation — should be a boundary that
hatching expresses (direction change, chirality flip, or drawn line).
This memo maps the literature and ranks what to try. Sources checked
2026-07; foundational papers stable.

## 1. The exact concept in the literature

- **Apparent ridges** (Judd, Durand, Adelson, SIGGRAPH 2007) — THE
  formalization: loci of maxima of *view-dependent* curvature. Designed
  specifically to answer "where should a line drawing place its lines."
  View-dependent = a fold reads as a fold from THIS viewpoint — exactly
  our case (we work in image space).
  https://dl.acm.org/doi/10.1145/1276377.1276401
- **Suggestive contours** (DeCarlo et al. 2003) — near-silhouette folds;
  complements apparent ridges.
- **Ridge–valley / crest lines** on surfaces (Ohtake et al. 2004;
  medical-illustration survey: https://arxiv.org/pdf/1501.03605) —
  view-independent creases: extrema of principal curvature along its own
  principal direction.
- **Critical contours** (https://arxiv.org/pdf/1705.07329) — links image
  shading flows to salient surface organization; theoretical backbone
  for "the folds ARE the drawing."

## 2. Hatch direction from curvature (why flips happen naturally)

- **Hertzmann & Zorin, "Illustrating Smooth Surfaces" (2000)** — the
  canonical result: hatch along PRINCIPAL CURVATURE DIRECTIONS; the
  field's own discontinuities/singularities land on parabolic lines and
  umbilics — direction flips at folds fall out for free. The artist's
  two-family rule is a special case.
- **Cross fields / 4-RoSy** (Knöppel et al., Globally Optimal Direction
  Fields: http://www.cs.cmu.edu/~kmcrane/Projects/GloballyOptimalDirectionFields/paper.pdf;
  NeurCross 2024: https://arxiv.org/pdf/2405.13745) — smooth a
  4-symmetric direction field aligned to curvature; singularities become
  sparse and *placed where geometry demands*. The quad-meshing world
  solved "coherent direction field with honest discontinuities" —
  directly reusable for hatching (Real-Time Hatching, Praun:
  https://hhoppe.com/hatching.pdf).

## 3. What we can compute TODAY from the frozen Marigold normals

The shape operator's image-space proxy: derivatives of the normal map.
A = sym(∂(nx,ny)/∂(x,y)) per pixel → eigenvalues (fold strength) +
eigenvectors (fold axis / cross-fold direction), multi-scale via a
normal-map pyramid. Gives:
  1. crease-strength map ("ridge lines everywhere", multi-scale)
  2. fold-axis field (what direction the crease runs)
  3. natural region boundaries = curvature ridges → forms with honest
     edges (replaces k-means blobs at class boundaries)
This is probe #1 (bottom of forms tab): zero new models, frozen inputs.

## 4. Better normals if Marigold limits us

- **StableNormal** (SIGGRAPH Asia 2024) — sharper, stabler than
  Marigold/DSINE/GeoWizard on benchmarks; "stable-and-sharp" is
  literally the pitch. https://stable-x.github.io/StableNormal/
- **DSINE** (CVPR 2024) — fast, sharp, per-pixel ray-aware.
- **Metric3D v2** (https://arxiv.org/pdf/2404.15506) — joint metric
  depth + normals foundation model.
Drop-in: decompose/ already freezes normals; swapping the estimator is
one offline script change + refreeze.

## 5. Learned "where would an artist draw lines" models

- **Informative Drawings** (Chan et al., CVPR 2022 — already in
  prior-art.md) — photo → line drawing with geometry (depth) + semantic
  losses; emits internal creases, not just silhouettes.
- Photo-sketching (contour drawings, 2019); reference-based sketch
  extraction (SIGGRAPH 2023); survey list:
  https://github.com/MarkMoHR/Awesome-Sketch-Synthesis
- Classical dense edge nets (HED/DexiNed/PiDiNet) — texture edges, not
  folds; useful as a *negative* filter (edge-but-not-crease = material
  boundary).
These become another frozen offline channel (like scene/normals): a
"where lines belong" prior an arrangement can consume.

## 6. Plane/facet instance models (forms with crisp crease borders)

PlaneRCNN/PlaneNet lineage: learned planar-instance segmentation from a
single image — forms AS planar facets whose shared borders are the
creases. Heavier; only if probe #1's regions disappoint.

## Ranked plan

1. **Curvature probe from our normals** (done, see forms tab): strength
   map + fold-axis field + traced crease polylines.
2. **Crease-bounded forms**: replace k-means-only classes with regions
   CUT by crease lines (posterize ∧ watershed-on-crease-strength) —
   masses whose borders ARE folds; chirality per side.
3. **Cross-field hatching**: smooth 4-RoSy aligned to the curvature
   directions → globally coherent hatch field with honest singularities
   (the deep version of "angles from the mountain itself").
4. **StableNormal refreeze** if Marigold's softness caps 1-3.
5. **Informative-Drawings channel** as a learned line prior to compare
   against (and steal from) our geometric creases.
