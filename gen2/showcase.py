"""Render a sweep of REAL pen renders exercising the normal-map powers
(orientation_source, normal_var zones, relight) and serve them in the
bake-off gallery UI for judging.

    python showcase.py tests/fixtures/peak_src.png
    cd runs/showcase/<stem> && python -m http.server 8766
"""

import argparse
import copy
import json
import logging
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from bakeoff import GALLERY_HTML          # noqa: E402
from evolve.preview import render_thumb   # noqa: E402

log = logging.getLogger("showcase")

BASE = {
    "name": "showcase",
    "page": {"size": "11x17", "margin_mm": 24},
    "source": {"params": {
        "n_bands": 5, "band_gamma": 1.2, "blur_mm": 1.2,
        "orientation_source": "normals", "normals_smooth_mm": 5.0,
        "normals_stroke": "downslope"}},
    "humanize": {"wobble_amp_mm": 0.13, "overshoot_prob": 0.08,
                 "break_per_mm": 0.002},
    "zones": [
        {"name": "sky",
         "select": {"type": "hsv", "hue": [170, 260], "sat": [0.05, 1.0],
                    "max_edge_density": 0.05, "top_connected": True,
                    "smooth_mm": 3.0},
         "bands": [
             {"module": "fixed_hatch", "pen": "blue03",
              "params": {"angle_deg": 0, "spacing_mm": 0.9,
                         "spacing_jitter": 0.06},
              "tone_mod": {"low": 0.04, "high": 0.32, "seg_mm": 4.0}},
             {"module": "fixed_hatch", "pen": "blue03",
              "params": {"angle_deg": 0, "spacing_mm": 0.75,
                         "spacing_jitter": 0.06},
              "tone_mod": {"low": 0.05, "high": 0.4, "seg_mm": 4.0}},
             {"module": "fixed_hatch", "pen": "blue03",
              "params": {"angle_deg": 0, "spacing_mm": 0.65,
                         "spacing_jitter": 0.06}},
             {"module": "empty"}, {"module": "empty"}]},
        {"name": "texture",
         "select": {"type": "hsv", "normal_var": [0.45, 1.0],
                    "smooth_mm": 2.5},
         "base": {"module": "curl_fill", "pen": "black03",
                  "params": {"radius_mm": 1.2, "spacing_mm": 2.0,
                             "sweep_deg_min": 160, "sweep_deg_max": 340},
                  "tone_mod": {"low": 0.1, "high": 0.55, "seg_mm": 2.0}},
         "bands": [
             {"module": "empty"}, {"module": "empty"}, {"module": "empty"},
             {"module": "curl_fill", "pen": "black05",
              "params": {"radius_mm": 1.0, "spacing_mm": 1.6}},
             {"module": "curl_fill", "pen": "black05",
              "params": {"radius_mm": 0.9, "spacing_mm": 1.3}}]},
        {"name": "faces", "select": {"type": "rest"},
         "base": {"module": "flow_hatch", "pen": "blue03",
                  "params": {"spacing_mm": 0.8, "step_mm": 0.7,
                             "min_coherence": 0.04,
                             "fallback_angle_deg": 60,
                             "max_len_mm": 60},
                  "tone_mod": {"low": 0.04, "high": 0.5, "seg_mm": 2.5}},
         "bands": [
             {"module": "empty"}, {"module": "empty"}, {"module": "empty"},
             {"module": "flow_hatch", "pen": "black03",
              "params": {"spacing_mm": 0.55, "step_mm": 0.7,
                         "min_coherence": 0.04, "fallback_angle_deg": 60,
                         "max_len_mm": 40},
              "tone_mod": {"low": 0.25, "high": 0.7, "seg_mm": 2.0}},
             {"module": "empty"}]}]
}


def patch(g, path, value):
    g = copy.deepcopy(g)
    node = g
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = value
    return g


def variants():
    out = []
    # direction: how much the field is smoothed, and along vs across slope
    for sm in (2.0, 5.0, 10.0):
        for stroke in ("downslope", "contour"):
            g = patch(BASE, ["source", "params", "normals_smooth_mm"], sm)
            g = patch(g, ["source", "params", "normals_stroke"], stroke)
            out.append(("direction", f"smooth{sm} {stroke}",
                        {"smooth_mm": sm, "stroke": stroke}, g))
    # texture gate: where curls take over from ruled strokes
    for thr in (0.3, 0.45, 0.6):
        g = patch(BASE, ["zones", 1, "select", "normal_var"], [thr, 1.0])
        out.append(("texture", f"curls at var>{thr}",
                    {"var_thresh": thr}, g))
    g = copy.deepcopy(BASE)
    g["zones"].pop(1)  # no texture zone at all
    out.append(("texture", "no curls (ruled everywhere)",
                {"var_thresh": None}, g))
    # relight: the sun as a genome knob
    for az in (45, 135, 315):
        for mix in (0.5, 0.85):
            g = patch(BASE, ["source", "params", "tone_source"],
                      {"type": "relight", "azimuth_deg": az,
                       "elevation_deg": 40, "mix": mix})
            out.append(("relight", f"sun az{az} mix{mix}",
                        {"azimuth": az, "mix": mix}, g))
    # combos: best guesses
    g = patch(BASE, ["source", "params", "normals_smooth_mm"], 8.0)
    g = patch(g, ["zones", 1, "select", "normal_var"], [0.4, 1.0])
    g = patch(g, ["source", "params", "tone_source"],
              {"type": "relight", "azimuth_deg": 315, "elevation_deg": 40,
               "mix": 0.5})
    out.append(("combo", "smooth8 + curls.4 + relight315/.5",
                {"smooth": 8, "var": 0.4, "relight": 315}, g))
    g2 = patch(g, ["source", "params", "normals_stroke"], "contour")
    out.append(("combo", "same but contour strokes",
                {"smooth": 8, "var": 0.4, "relight": 315,
                 "stroke": "contour"}, g2))
    return out


def texture2_variants():
    """Contemporary marks for the high-variance (trees/rubble) zone —
    the curls read as antique; these read as now."""
    out = []
    marks = {
        "shingle small": {"module": "shingle_hatch", "pen": "black03",
                          "params": {"swatch_mm": 5, "spacing_mm": 0.55,
                                     "overlap": 0.55, "aspect": 0.7}},
        "shingle tiny": {"module": "shingle_hatch", "pen": "black03",
                         "params": {"swatch_mm": 3.5, "spacing_mm": 0.5,
                                    "overlap": 0.5, "aspect": 0.8}},
        "flow dashes": {"module": "flow_hatch", "pen": "black03",
                        "params": {"spacing_mm": 0.7, "step_mm": 0.6,
                                   "max_len_mm": 4.0,
                                   "min_coherence": 0.0,
                                   "fallback_angle_deg": 80}},
        "scribble fine": {"module": "scribble_fill", "pen": "black03",
                          "params": {"spacing_mm": 0.8, "step_mm": 0.9,
                                     "curl": 0.9, "curl_scale": 0.1,
                                     "stroke_len_mm": 90}},
    }
    for name, entry in marks.items():
        g = copy.deepcopy(BASE)
        base = dict(entry)
        base["tone_mod"] = {"low": 0.18, "high": 0.6, "seg_mm": 2.0}
        g["zones"][1]["base"] = base
        g["zones"][1]["select"]["normal_var"] = [0.5, 1.0]
        g["zones"][1]["bands"] = [
            {"module": "empty"}, {"module": "empty"}, {"module": "empty"},
            {"module": "empty"},
            {"module": "shingle_hatch", "pen": "black05",
             "params": {"swatch_mm": 4, "spacing_mm": 0.45,
                        "overlap": 0.6}}]
        out.append(("texture2", name, {"mark": name, "var": 0.5}, g))
    return out


def patchwork_variants():
    """The reference-artist move: dark areas as PATCHES of straight
    parallel hatching, each facet at its own angle, facets cut from the
    normal field (watershed-style faces). patch_hatch finally fed a real
    orientation field."""
    def faces_zone(sector, snap, gap):
        pp = {"sector_deg": sector, "snap_deg": snap, "patch_gap_mm": gap,
              "smooth_mm": 3.0, "min_coherence": 0.03,
              "fallback_angle_deg": 55, "min_patch_mm2": 20}
        return {
            "name": "faces", "select": {"type": "rest"},
            "base": {"module": "patch_hatch", "pen": "blue03",
                     "params": {**pp, "spacing_mm": 0.8},
                     "tone_mod": {"low": 0.05, "high": 0.5,
                                  "seg_mm": 2.5}},
            "bands": [
                {"module": "empty"}, {"module": "empty"},
                {"module": "empty"},
                {"module": "patch_hatch", "pen": "black03",
                 "params": {**pp, "spacing_mm": 0.5},
                 "tone_mod": {"low": 0.12, "high": 0.5, "seg_mm": 2.5}},
                {"module": "patch_hatch", "pen": "black05",
                 "params": {**pp, "spacing_mm": 0.45,
                            "cross_delta_deg": 60}}]}

    shingle = {"module": "shingle_hatch", "pen": "black03",
               "params": {"swatch_mm": 3.5, "spacing_mm": 0.5,
                          "overlap": 0.5, "aspect": 0.8},
               "tone_mod": {"low": 0.18, "high": 0.6, "seg_mm": 2.0}}
    dashes = {"module": "flow_hatch", "pen": "black03",
              "params": {"spacing_mm": 0.7, "step_mm": 0.6,
                         "max_len_mm": 4.0, "min_coherence": 0.0,
                         "fallback_angle_deg": 80},
              "tone_mod": {"low": 0.18, "high": 0.6, "seg_mm": 2.0}}

    out = []
    combos = [
        ("sector25 free gap.3 +shingle", 25, 0, 0.3, shingle),
        ("sector25 snap30 gap.3 +shingle", 25, 30, 0.3, shingle),
        ("sector40 free gap.4 +shingle", 40, 0, 0.4, shingle),
        ("sector40 snap30 gap.4 +dashes", 40, 30, 0.4, dashes),
        ("sector30 snap30 NO seams +dashes", 30, 30, 0.0, dashes),
        ("sector30 free patches-everywhere", 30, 0, 0.25, None),
    ]
    for title, sector, snap, gap, tex in combos:
        g = copy.deepcopy(BASE)
        # high-key snow photo: anchor bands to the histogram so the
        # darkest quantiles actually receive the dark patch passes
        g["source"]["params"]["band_anchor"] = "quantile"
        g["source"]["params"]["band_gamma"] = 1.0
        g["zones"][2] = faces_zone(sector, snap, gap)
        if tex is None:
            g["zones"].pop(1)
        else:
            g["zones"][1]["base"] = copy.deepcopy(tex)
            g["zones"][1]["select"]["normal_var"] = [0.5, 1.0]
            g["zones"][1]["bands"] = [
                {"module": "empty"}, {"module": "empty"},
                {"module": "empty"}, {"module": "empty"},
                {"module": "shingle_hatch", "pen": "black05",
                 "params": {"swatch_mm": 4, "spacing_mm": 0.45,
                            "overlap": 0.6}}]
        out.append(("patchwork", title,
                    {"sector": sector, "snap": snap, "gap": gap,
                     "texture": "none" if tex is None else
                     tex["module"]}, g))
    return out


def emphasis_variants():
    """Indication: ink survival decays with distance from feature lines
    (creases + silhouettes + edges). The anti-uniformity pass — dark
    hatching clusters at ridges and dissipates, like the artist."""
    out = []
    pw = patchwork_variants()
    base_g = None
    for fam, title, params, g in pw:
        if title.startswith("sector30 snap30"):
            base_g = g
            break
    for falloff in (15.0, 35.0, 70.0):
        for floor in (0.05, 0.2):
            g = copy.deepcopy(base_g)
            em = {"falloff_mm": falloff, "floor": floor,
                  "sources": ["crease", "silhouette", "edges"]}
            faces = g["zones"][-1]
            faces["base"]["emphasis"] = em
            for band in faces["bands"]:
                if band["module"] != "empty":
                    band["emphasis"] = em
            out.append(("emphasis", f"falloff{falloff:.0f} floor{floor}",
                        {"falloff_mm": falloff, "floor": floor}, g))
    return out


def iter2_variants():
    """Generation 2 on the emphasis-patchwork line: gate the texture zone
    too (the last uniform element), bracket falloff, fold in relight,
    bigger calmer planes, crease-only feature sources."""
    pw = {t: g for _, t, _, g in patchwork_variants()}
    base_g = pw["sector30 snap30 NO seams +dashes"]

    def build(falloff, floor, sources, tex_em=True, relight_az=None,
              sector=None, smooth=None, tex_swap=None, tex_var=0.55):
        g = copy.deepcopy(base_g)
        em = {"falloff_mm": falloff, "floor": floor, "sources": sources}
        faces = g["zones"][-1]
        faces["base"]["emphasis"] = em
        for band in faces["bands"]:
            if band["module"] != "empty":
                band["emphasis"] = em
        if sector:
            for e in [faces["base"]] + faces["bands"]:
                if e.get("params", {}).get("sector_deg"):
                    e["params"]["sector_deg"] = sector
        tex = g["zones"][1]
        tex["select"]["normal_var"] = [tex_var, 1.0]
        if tex_swap:
            tex["base"] = copy.deepcopy(tex_swap)
        if tex_em:
            tex["base"]["emphasis"] = {**em, "floor": max(floor, 0.15)}
        if relight_az is not None:
            g["source"]["params"]["tone_source"] = {
                "type": "relight", "azimuth_deg": relight_az,
                "elevation_deg": 40, "mix": 0.5}
        if smooth:
            g["source"]["params"]["normals_smooth_mm"] = smooth
        return g

    shingle_tiny = {"module": "shingle_hatch", "pen": "black03",
                    "params": {"swatch_mm": 3.5, "spacing_mm": 0.5,
                               "overlap": 0.5, "aspect": 0.8},
                    "tone_mod": {"low": 0.18, "high": 0.6, "seg_mm": 2.0}}
    ALL = ["crease", "silhouette", "edges"]
    CR = ["crease", "silhouette"]
    combos = [
        ("A emphasis-everywhere f35", build(35, 0.1, ALL)),
        ("B A+relight az315", build(35, 0.1, ALL, relight_az=315)),
        ("C crease-only sources", build(35, 0.1, CR)),
        ("D big calm planes s45 sm8", build(35, 0.1, ALL, sector=45,
                                            smooth=8.0)),
        ("E tight sparse f20", build(20, 0.05, ALL, relight_az=315)),
        ("F shingle-tiny texture", build(35, 0.1, ALL,
                                         tex_swap=shingle_tiny)),
        ("G D+relight", build(35, 0.1, ALL, sector=45, smooth=8.0,
                              relight_az=315)),
        ("H soft spread f60", build(60, 0.15, CR)),
    ]
    return [("iter2", t, {"variant": t.split()[0]}, g) for t, g in combos]


def iter3_variants():
    """Gen 3: breed the gen-2 winners — E's tight sparse emphasis x F's
    shingle-tiny texture, with relight, bracketed."""
    pw = {t: g for _, t, _, g in iter2_variants()}
    e, f = pw["E tight sparse f20"], pw["F shingle-tiny texture"]

    def child(falloff, floor, sources, relight):
        g = copy.deepcopy(e)
        g["zones"][1]["base"] = copy.deepcopy(f["zones"][1]["base"])
        # tonecheck: the forest must be able to REACH photo darkness —
        # tighter spacing and a lower gate floor raise the zone's ceiling
        g["zones"][1]["base"]["params"]["spacing_mm"] = 0.42
        g["zones"][1]["base"]["tone_mod"] = {"low": 0.08, "high": 0.5,
                                             "seg_mm": 2.0}
        faces = g["zones"][-1]
        em = {"falloff_mm": falloff, "floor": floor, "sources": sources}
        for entry in [faces["base"]] + faces["bands"] \
                + [g["zones"][1]["base"]]:
            if entry.get("module", "x") != "empty" and "emphasis" in entry:
                entry["emphasis"] = {**em}
        g["zones"][1]["base"]["emphasis"] = {**em,
                                             "floor": max(floor, 0.15)}
        if relight is None:
            g["source"]["params"].pop("tone_source", None)
        return g

    ALL = ["crease", "silhouette", "edges"]
    CR = ["crease", "silhouette"]
    combos = [
        ("I ExF f20 relight", child(20, 0.05, ALL, 315)),
        ("J I crease-only", child(20, 0.05, CR, 315)),
        ("K fuller f30", child(30, 0.1, CR, 315)),
        ("L J no relight", child(20, 0.05, CR, None)),
    ]
    return [("iter3", t, {"variant": t.split()[0]}, g) for t, g in combos]


def toneclosed_variants():
    """The gen-3 winners with the closed loop: render -> measure ink ->
    top up the deficit -> repeat. Outputs constrained by tone, not
    merely scored."""
    it3 = {t: g for _, t, _, g in iter3_variants()}
    out = []
    tc = {"module": "flow_hatch", "pen": "black03",
          "params": {"spacing_mm": 0.5, "step_mm": 0.7, "max_len_mm": 25,
                     "min_coherence": 0.0, "fallback_angle_deg": 60},
          "gamma": 1.15, "max_cov": 0.8, "min_deficit": 0.1}
    for parent in ("I ExF f20 relight", "K fuller f30"):
        for passes in (0, 1, 2):
            g = copy.deepcopy(it3[parent])
            if passes:
                g["tone_close"] = {**copy.deepcopy(tc), "passes": passes}
            out.append(("toneclosed",
                        f"{parent.split()[0]} +close x{passes}",
                        {"parent": parent.split()[0], "passes": passes},
                        g))
    return out


def mosaic_variants():
    """Angular tessellating patches (mosaic_hatch) as the whole land
    treatment — patch borders from the image's own lines, one committed
    density per patch."""
    dashes = {"module": "flow_hatch", "pen": "black03",
              "params": {"spacing_mm": 0.7, "step_mm": 0.6,
                         "max_len_mm": 4.0, "min_coherence": 0.0,
                         "fallback_angle_deg": 80},
              "tone_mod": {"low": 0.18, "high": 0.6, "seg_mm": 2.0}}
    combos = [
        ("fine merge.05 free", {"merge": 0.05, "snap_deg": 0}),
        ("fine merge.05 snap30", {"merge": 0.05, "snap_deg": 30}),
        ("coarse merge.12 free", {"merge": 0.12, "snap_deg": 0}),
        ("coarse merge.12 snap30", {"merge": 0.12, "snap_deg": 30}),
        ("coarse + seams", {"merge": 0.12, "snap_deg": 30,
                            "gap_mm": 0.4}),
        ("chunky corners", {"merge": 0.08, "snap_deg": 30,
                            "corner_mm": 1.6}),
    ]
    out = []
    for title, extra in combos:
        g = copy.deepcopy(BASE)
        g["zones"][1]["base"] = copy.deepcopy(dashes)
        g["zones"][1]["select"]["normal_var"] = [0.55, 1.0]
        g["zones"][1]["bands"] = [{"module": "empty"}] * 5
        g["zones"][2] = {
            "name": "faces", "select": {"type": "rest"},
            "base": {"module": "mosaic_hatch", "pen": "black03",
                     "params": {"spacing_mm": [None, 1.15, 0.7, 0.45],
                                "seed_h": 0.015, **extra}},
            "bands": [{"module": "empty"}] * 5}
        out.append(("mosaic", title, extra, g))
    return out


def downhill_variants():
    """Long flowing strokes running from the summit down the slopes the
    way water would — the user's watershed-flow ask. Normals-driven
    downslope streamlines, long max_len, no texture zone in the way."""
    it3 = {t: g for _, t, _, g in iter3_variants()}
    out = []
    for max_len, spacing, smooth in ((80, 0.8, 6.0), (160, 0.8, 10.0),
                                     (160, 1.1, 6.0), (80, 1.1, 10.0)):
        g = copy.deepcopy(it3["I ExF f20 relight"])
        g["zones"] = [z for z in g["zones"] if z["name"] != "texture"]
        g["source"]["params"]["normals_smooth_mm"] = smooth
        g["source"]["params"]["normals_stroke"] = "downslope"
        faces = g["zones"][-1]
        faces["base"] = {
            "module": "flow_hatch", "pen": "blue03",
            "params": {"spacing_mm": spacing, "step_mm": 0.8,
                       "max_len_mm": max_len, "min_coherence": 0.03,
                       "fallback_angle_deg": 60},
            "tone_mod": {"low": 0.05, "high": 0.5, "seg_mm": 4.0}}
        faces["bands"] = [
            {"module": "empty"}, {"module": "empty"}, {"module": "empty"},
            {"module": "flow_hatch", "pen": "black03",
             "params": {"spacing_mm": spacing * 0.7, "step_mm": 0.8,
                        "max_len_mm": max_len, "min_coherence": 0.03,
                        "fallback_angle_deg": 60},
             "tone_mod": {"low": 0.25, "high": 0.65, "seg_mm": 3.0}},
            {"module": "empty"}]
        out.append(("downhill",
                    f"len{max_len} sp{spacing} sm{smooth}",
                    {"max_len": max_len, "spacing": spacing,
                     "smooth": smooth}, g))
    return out


PLAN_SKY = {
    "name": "sky",
    "select": {"type": "hsv", "hue": [170, 260], "sat": [0.05, 1.0],
               "max_edge_density": 0.05, "top_connected": True,
               "smooth_mm": 3.0},
    "bands": [
        {"module": "fixed_hatch", "pen": "blue03",
         "params": {"angle_deg": 0, "spacing_mm": 0.85,
                    "spacing_jitter": 0.06},
         "tone_mod": {"low": 0.04, "high": 0.32, "seg_mm": 4.0}},
        {"module": "fixed_hatch", "pen": "blue03",
         "params": {"angle_deg": 0, "spacing_mm": 0.7,
                    "spacing_jitter": 0.06},
         "tone_mod": {"low": 0.05, "high": 0.4, "seg_mm": 4.0}},
        {"module": "fixed_hatch", "pen": "blue03",
         "params": {"angle_deg": 0, "spacing_mm": 0.6,
                    "spacing_jitter": 0.06}},
        {"module": "empty"}, {"module": "empty"}]}

PLAN_TEXTURE = {
    "name": "texture",
    "base": {"module": "shingle_hatch", "pen": "black03",
             "params": {"swatch_mm": 3.5, "spacing_mm": 0.45,
                        "overlap": 0.5, "aspect": 0.8},
             "tone_mod": {"low": 0.08, "high": 0.5, "seg_mm": 2.0}},
    "bands": []}


def plansweep_variants():
    """The compiled composition pipeline, swept: masses granularity x
    levels x compose-op recipes x focal on/off. The plan spec is genome —
    ops can be added/removed/reordered like any other gene."""
    def build(merge, k, ops, focal, targets=None):
        compose = [{"op": "commit_levels"},
                   {"op": "weld_small", "min_frac": 0.01}] + ops
        if focal:
            compose.append({"op": "focal", "pos": "auto",
                            "radius_mm": 70})
        return {
            "name": "plansweep",
            "page": {"size": "11x17", "margin_mm": 24},
            "source": {"params": {
                "n_bands": 5, "blur_mm": 1.2,
                "orientation_source": "normals",
                "normals_smooth_mm": 6.0}},
            "humanize": {"wobble_amp_mm": 0.13, "overshoot_prob": 0.08,
                         "break_per_mm": 0.002},
            "plan": {
                "channels": {"masses": {"field": "crease+shadow",
                                        "merge": merge},
                             "levels": {"k": k, "sigma_frac": 0.012},
                             "texture": {"thresh": 0.55}},
                "compose": compose,
                "assign": {
                    "targets": targets or
                    list(np.linspace(0, 0.62, k)),
                    "palette": ["blue03", "black03", "black05"],
                    "prefer": ["fixed_hatch", "cross_hatch",
                               "shingle_hatch"],
                    # committed value = flat; a mild gate only spares the
                    # brightest micro-veins instead of re-applying photo
                    # tone on top of the level (double counting)
                    "micro_tone": {"low": 0.0, "high": 0.12,
                                   "seg_mm": 3.0},
                    "emphasis": {"falloff_mm": 35, "floor": 0.25},
                    "keyline_mm": 0.3},
                "direction": {"mode": "per_mass", "snap_deg": 15},
                "sky_zone": copy.deepcopy(PLAN_SKY),
                "texture_zone": copy.deepcopy(PLAN_TEXTURE),
                "outline": {"max_level_gap": 0, "pen": "black03",
                            "min_len_mm": 6}}}

    FT = [{"op": "force_tone", "min_gap": 0.04}]
    EE = [{"op": "elect_extremes"}]
    combos = [
        ("m.12 k4 full recipe focal", build(0.12, 4, FT + EE, True)),
        ("m.12 k4 full recipe", build(0.12, 4, FT + EE, False)),
        ("m.2 k4 full recipe focal", build(0.2, 4, FT + EE, True)),
        ("m.12 k3 full recipe focal", build(0.12, 3, FT + EE, True,
                                            [0.0, 0.3, 0.6])),
        ("m.12 k4 NO force_tone", build(0.12, 4, EE, True)),
        ("m.12 k4 NO extremes", build(0.12, 4, FT, True)),
        ("m.12 k4 bare (commit only)", build(0.12, 4, [], False)),
        ("m.12 k4 darker targets", build(0.12, 4, FT + EE, True,
                                         [0.0, 0.25, 0.5, 0.75])),
    ]
    return [("plansweep", t, {"recipe": t}, g) for t, g in combos]


def bigsweep_variants(n_sampled=128):
    """Overnight sweep: seeded random sample of the full combination
    space (parent x relight x emphasis x tone_close x pens x texture),
    plus curated picks. Captions carry the tone-fidelity score."""
    import random
    rnd = random.Random(7)
    it3 = {t: g for _, t, _, g in iter3_variants()}
    mos = {t: g for _, t, _, g in mosaic_variants()}
    pw = {t: g for _, t, _, g in patchwork_variants()}
    parents = {
        "I": it3["I ExF f20 relight"],
        "K": it3["K fuller f30"],
        "MO": mos["coarse merge.12 snap30"],
        "PW": pw["sector30 snap30 NO seams +dashes"],
    }
    relights = [None, (45, 0.5), (135, 0.5), (225, 0.5), (315, 0.5),
                (315, 0.8), (90, 0.8)]
    emphs = [None, (20, 0.05), (35, 0.1), (60, 0.15)]
    closes = [None, (1.15, 0.8, 1, "flow_hatch"),
              (1.15, 0.8, 2, "flow_hatch"), (0.9, 0.7, 1, "fixed_hatch"),
              (1.4, 0.85, 1, "flow_hatch")]
    pens = ["default", "blue_close"]
    texs = [("dash", 0.55), ("shingle", 0.5), ("dash", 0.65)]

    shingle_tiny = {"module": "shingle_hatch", "pen": "black03",
                    "params": {"swatch_mm": 3.5, "spacing_mm": 0.42,
                               "overlap": 0.5, "aspect": 0.8},
                    "tone_mod": {"low": 0.08, "high": 0.5, "seg_mm": 2.0}}

    def build(pname, rel, emp, clo, pen, tex):
        g = copy.deepcopy(parents[pname])
        if rel is None:
            g["source"]["params"].pop("tone_source", None)
        else:
            g["source"]["params"]["tone_source"] = {
                "type": "relight", "azimuth_deg": rel[0],
                "elevation_deg": 40, "mix": rel[1]}
        for zone in g.get("zones", []):
            for entry in ([zone.get("base")] + zone.get("bands", [])):
                if not entry or entry.get("module", "empty") == "empty":
                    continue
                if emp is None:
                    entry.pop("emphasis", None)
                elif "emphasis" in entry or zone["name"] != "sky":
                    entry["emphasis"] = {
                        "falloff_mm": emp[0], "floor": emp[1],
                        "sources": ["crease", "silhouette"]}
        if len(g.get("zones", [])) > 2 and \
                g["zones"][1].get("select", {}).get("normal_var"):
            g["zones"][1]["select"]["normal_var"] = [tex[1], 1.0]
            if tex[0] == "shingle":
                g["zones"][1]["base"] = copy.deepcopy(shingle_tiny)
        if clo is not None:
            gamma, cov, passes, module = clo
            g["tone_close"] = {
                "module": module, "pen":
                    "blue03" if pen == "blue_close" else "black03",
                "params": ({"spacing_mm": 0.5, "step_mm": 0.7,
                            "max_len_mm": 25, "min_coherence": 0.0,
                            "fallback_angle_deg": 60}
                           if module == "flow_hatch"
                           else {"angle_deg": 55, "spacing_mm": 0.5}),
                "gamma": gamma, "max_cov": cov, "passes": passes,
                "min_deficit": 0.1}
        return g

    space = [(p, r, e, c, pn, t)
             for p in parents for r in relights for e in emphs
             for c in closes for pn in pens for t in texs]
    picks = rnd.sample(space, min(n_sampled, len(space)))
    curated = [("I", (315, 0.5), (20, 0.05), (1.15, 0.8, 1, "flow_hatch"),
                "default", ("shingle", 0.5)),
               ("K", (315, 0.5), (35, 0.1), (1.15, 0.8, 1, "flow_hatch"),
                "blue_close", ("dash", 0.55)),
               ("MO", (315, 0.5), None, (1.15, 0.8, 1, "flow_hatch"),
                "blue_close", ("dash", 0.65)),
               ("PW", (315, 0.8), (35, 0.1), (1.15, 0.8, 2, "flow_hatch"),
                "default", ("shingle", 0.5))]
    out = []
    for combo in curated + picks:
        p, r, e, c, pn, t = combo
        title = (f"{p} rel{r[0] if r else '-'} emp{e[0] if e else '-'} "
                 f"clo{c[2] if c else '-'} {pn} {t[0]}{t[1]}")
        params = {"parent": p, "relight": r, "emphasis": e, "close": c,
                  "pens": pn, "texture": t}
        try:
            out.append(("bigsweep", title, params, build(*combo)))
        except Exception:
            continue
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("photo", type=Path)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--only", default=None,
                    help="render only this variant family, merging into "
                         "the existing gallery")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    out = args.out or Path("runs/showcase") / args.photo.stem
    (out / "imgs").mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(GALLERY_HTML)
    import shutil
    shutil.copy(args.photo, out / "imgs" / "_photo.png")

    manifest, status = [], {}
    mf = out / "manifest.json"
    if mf.exists():
        prev = json.loads(mf.read_text())
        manifest = prev.get("panels", [])
        status = prev.get("status", {})
    vs = (variants() + texture2_variants() + patchwork_variants()
          + mosaic_variants() + emphasis_variants() + iter2_variants()
          + iter3_variants() + toneclosed_variants())
    if args.only == "bigsweep":
        vs = vs + bigsweep_variants()
    if args.only == "downhill":
        vs = vs + downhill_variants()
    if args.only == "plansweep":
        vs = vs + plansweep_variants()
    if args.only:
        vs = [v for v in vs if v[0] == args.only]
        manifest = [m for m in manifest if m["family"] != args.only]
    for i, (family, title, params, genome) in enumerate(vs):
        status[family] = "running"
        (out / "manifest.json").write_text(json.dumps(
            {"photo": "imgs/_photo.png", "status": status,
             "panels": manifest}, indent=1))
        log.info("[%d/%d] %s: %s", i + 1, len(vs), family, title)
        img = f"imgs/{family}__{i:03d}.png"
        try:
            render_thumb(genome, args.seed, str(args.photo),
                         out / img, width_px=900)
            try:
                from evolve.tonecheck import tone_fidelity
                tf, _ = tone_fidelity(str(out / img), str(args.photo))
                title = f"{title} tf{tf:.2f}"
                params = {**params, "tone_fidelity": round(tf, 3)}
            except Exception:
                pass
            manifest.append({"id": img[5:-4], "family": family,
                             "title": title, "params": params,
                             "img": img})
        except Exception as e:
            log.error("variant %r failed: %s", title, e)
        done = all(f != family for f, *_ in vs[i + 1:])
        status[family] = "done" if done else "running"
    for f in status:
        status[f] = "done"
    (out / "manifest.json").write_text(json.dumps(
        {"photo": "imgs/_photo.png", "status": status,
         "panels": manifest}, indent=1))
    log.info("wrote %d renders -> %s", len(manifest), out)


if __name__ == "__main__":
    main()
