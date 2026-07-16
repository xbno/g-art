"""Visual review UI — the shared language for judging everything gen2 does.

Every capability in this repo produces aesthetic output; every stage of it
must be *seeable*. This package regenerates a static review site under
runs/review/ (gitignored) from the actual code paths — never mockups:

    python -m review build          # regenerate every section
    python -m review build marks    # just one section
    python -m review serve          # build + serve on :8787, auto-reload

The page polls manifest.json — rebuild in another terminal and the open
browser updates itself. Sections live in build.py; adding a visual
capability to the engine means adding (or extending) a section here.
"""
