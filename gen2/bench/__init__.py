"""The re-ink bench: reconstruction as the measure of vocabulary.

The gate question of the vocabulary ladder made objective: can our stroke
system reproduce a reference ink crop — black covered, white respected,
stroke count comparable to the artist's? A crop that can't be re-inked
economically is a measured vocabulary gap, not an opinion.

Rungs:
  measure   read everything off the crop with no vocabulary assumed:
            pen width (the pen is the ruler — physical scale comes from
            the ink itself), orientation field, skeleton, segment count
  trace     skeleton-trace replot — the ceiling: a plotter re-inking the
            crop verbatim; also the ground-truth stroke count
  greedy    Salisbury-style deficit loop placing OUR strokes along the
            measured orientation field — what the vocabulary can honestly
            do today; scored ink-recall / white-precision / economy

Literature: Hertzmann's stroke-based rendering survey (2003); Salisbury
et al. 1997 (importance-driven placement); Winkenbach & Salesin 1994
(prioritized stroke textures); diffvg/CLIPasso (gradient-fit strokes — a
future rung); Portilla-Simoncelli-style statistics matching (why texture
fills should be scored statistically, not pixel-phase-exactly).

Corpus: refs/crops/*.png. Review UI section: bench.
"""
