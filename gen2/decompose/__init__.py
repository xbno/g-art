"""Offline scene decomposition: photo -> frozen scene plan.

Runs SAM (automatic mask generation) + DepthAnything ONCE per source photo
and freezes the result to sibling files the engine can consume forever:

    <photo stem>.scene.npz   labels (uint8 HxW, 0 = unassigned never survives
                             post-processing), depth (float16 HxW, 0..1,
                             higher = NEARER)
    <photo stem>.scene.json  per-region stats: depth_rank (0 = farthest),
                             tone_level (0 = lightest), area_frac, centroid;
                             "name" is null until a human/mutator labels it
    <photo stem>.scene.png   overlay panel for eyes (photo | depth | regions)

Model inference is not reproducible across library versions, so it must
never run inside render(); the frozen plan is part of the *source input*,
exactly like the photo bytes. The engine-side reader is engine/scene.py —
this package is the only place torch/transformers may be imported.
"""
