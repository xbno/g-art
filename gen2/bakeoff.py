"""Segmentation model bake-off: sweep params per model family, save labeled
overlay panels, and serve a clickable gallery for judging. NOT engine code —
exploratory tooling; nothing here is consumed by render().

    python bakeoff.py tests/fixtures/peak_src.png
    python bakeoff.py photo.png --families depth,posterize,sam3
    cd runs/bakeoff/<stem> && python -m http.server 8765
    open http://localhost:8765     # star keepers, Export Starred button

Heavy inference (model x checkpoint x resolution) runs ONCE and is cached
under <out>/cache/; the 30-50 looks per family come from sweeping cheap
post-processing params over the cached outputs. Families are independent:
one failing (missing checkpoint, API drift) is recorded and skipped.
"""

import argparse
import json
import logging
import traceback
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image

log = logging.getLogger("bakeoff")

ARTIST_GROUPS = {  # ADE20K names -> the vocabulary an illustrator uses
    "sky": ["sky"],
    "tree": ["tree", "plant", "palm", "flower", "grass"],
    "mountain": ["mountain", "hill", "rock", "stone"],
    "water": ["water", "sea", "river", "lake", "waterfall"],
    "ground": ["earth", "field", "sand", "path", "dirt", "land", "snow"],
    "built": ["building", "house", "wall", "bridge", "tower", "hut"],
}

SAM3_VOCAB = ["sky", "cloud", "mountain", "snow", "rock face", "tree",
              "forest", "glacier", "ridge", "cliff", "shadow", "grass"]


class Bakeoff:
    def __init__(self, photo: Path, out: Path, max_side: int = 1100):
        img = Image.open(photo).convert("RGB")
        if max(img.size) > max_side:
            s = max_side / max(img.size)
            img = img.resize((round(img.width * s), round(img.height * s)),
                             Image.LANCZOS)
        self.img = img
        self.rgb = np.asarray(img)
        self.H, self.W = self.rgb.shape[:2]
        self.out = out
        (out / "imgs").mkdir(parents=True, exist_ok=True)
        (out / "cache").mkdir(exist_ok=True)
        self.manifest: list[dict] = []
        self.status: dict = {}
        mf = out / "manifest.json"
        if mf.exists():  # append/replace families in an existing gallery
            prev = json.loads(mf.read_text())
            self.manifest = prev.get("panels", [])
            self.status = prev.get("status", {})
        self.rng = np.random.default_rng(7)
        Image.fromarray(self.rgb).save(out / "imgs" / "_photo.png")

    # ---------- caching --------------------------------------------------
    def cached(self, key: str, fn):
        p = self.out / "cache" / f"{key}.npz"
        if p.exists():
            return dict(np.load(p, allow_pickle=True))
        val = fn()
        np.savez_compressed(p, **val)
        return val

    # ---------- panel writing -------------------------------------------
    def panel(self, family: str, seg: np.ndarray, names: dict | None,
              title: str, params: dict):
        vis = np.zeros((self.H, self.W, 3), np.float32)
        for lab in np.unique(seg):
            vis[seg == lab] = self.rng.uniform(40, 255, 3)
        img = (0.35 * self.rgb + 0.65 * vis).astype(np.uint8)
        e = cv2.Canny((seg.astype(np.int32) * 37 % 251).astype(np.uint8),
                      0, 0) > 0
        img[cv2.dilate(e.astype(np.uint8), np.ones((2, 2), np.uint8)) > 0] = 0
        if names:
            for lab in np.unique(seg):
                m = seg == lab
                if m.sum() < 0.01 * self.H * self.W:
                    continue
                ys, xs = np.nonzero(m)
                cx, cy = int(xs.mean()), int(ys.mean())
                txt = names.get(int(lab), str(lab))
                for th, col in ((4, (255, 255, 255)), (1, (0, 0, 0))):
                    cv2.putText(img, txt, (cx - 30, cy),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.65, col, th,
                                cv2.LINE_AA)
        import hashlib
        h = hashlib.md5(json.dumps(params, sort_keys=True).encode()
                        ).hexdigest()[:8]
        i = len([m for m in self.manifest if m["family"] == family])
        # param-hashed id: stars survive family re-renders; index keeps sort
        fname = f"{family}__{i:03d}_{h}.png"
        cv2.imwrite(str(self.out / "imgs" / fname),
                    cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        self.manifest.append({"id": fname[:-4], "family": family,
                              "title": title, "params": params,
                              "img": f"imgs/{fname}"})

    def flush(self, status: dict):
        self.status.update(status)
        (self.out / "manifest.json").write_text(json.dumps(
            {"photo": "imgs/_photo.png", "status": self.status,
             "panels": self.manifest}, indent=1))

    # ---------- inference primitives (each cached) ------------------------
    def m2f_semantic(self, ckpt: str, res: int):
        def run():
            from transformers import (AutoImageProcessor,
                                      Mask2FormerForUniversalSegmentation)
            name = f"facebook/mask2former-swin-{ckpt}-ade-semantic"
            proc = AutoImageProcessor.from_pretrained(name)
            model = Mask2FormerForUniversalSegmentation.from_pretrained(name)
            im = self._resized(res)
            with torch.no_grad():
                out = model(**proc(images=im, return_tensors="pt"))
            seg = proc.post_process_semantic_segmentation(
                out, target_sizes=[(self.H, self.W)])[0].numpy()
            labels = json.dumps({int(k): v for k, v
                                 in model.config.id2label.items()})
            return {"seg": seg.astype(np.int16), "id2label": labels}
        d = self.cached(f"m2f_{ckpt}_{res}", run)
        return d["seg"], {int(k): v for k, v
                          in json.loads(str(d["id2label"])).items()}

    def m2f_panoptic(self, res: int):
        def run():
            from transformers import (AutoImageProcessor,
                                      Mask2FormerForUniversalSegmentation)
            name = "facebook/mask2former-swin-large-ade-panoptic"
            proc = AutoImageProcessor.from_pretrained(name)
            model = Mask2FormerForUniversalSegmentation.from_pretrained(name)
            im = self._resized(res)
            with torch.no_grad():
                out = model(**proc(images=im, return_tensors="pt"))
            r = proc.post_process_panoptic_segmentation(
                out, target_sizes=[(self.H, self.W)])[0]
            seg = r["segmentation"].numpy().astype(np.int16)
            id2label = {int(k): v for k, v in model.config.id2label.items()}
            info = {int(s["id"]): id2label.get(int(s["label_id"]),
                                               str(s["label_id"]))
                    for s in r["segments_info"]}
            return {"seg": seg, "names": json.dumps(info)}
        d = self.cached(f"m2f_panoptic_{res}", run)
        return d["seg"], {int(k): v for k, v
                          in json.loads(str(d["names"])).items()}

    def segformer(self, ckpt: str, res: int):
        def run():
            from transformers import (SegformerForSemanticSegmentation,
                                      SegformerImageProcessor)
            name = f"nvidia/segformer-{ckpt}"
            proc = SegformerImageProcessor.from_pretrained(name)
            model = SegformerForSemanticSegmentation.from_pretrained(name)
            kw = {}
            if res:
                kw["size"] = {"height": res, "width": res}
            with torch.no_grad():
                out = model(**proc(images=self.img, return_tensors="pt",
                                   **kw))
            logits = torch.nn.functional.interpolate(
                out.logits, size=(self.H, self.W), mode="bilinear",
                align_corners=False)
            seg = logits.argmax(1)[0].numpy()
            labels = json.dumps({int(k): v for k, v
                                 in model.config.id2label.items()})
            return {"seg": seg.astype(np.int16), "id2label": labels}
        d = self.cached(f"segf_{ckpt}_{res}", run)
        return d["seg"], {int(k): v for k, v
                          in json.loads(str(d["id2label"])).items()}

    def depth(self, size: str):
        def run():
            from transformers import pipeline
            dev = "mps" if torch.backends.mps.is_available() else "cpu"
            dp = pipeline("depth-estimation", device=dev,
                          model=f"depth-anything/Depth-Anything-V2-{size}-hf")
            pred = dp(self.img)["predicted_depth"]
            d = torch.nn.functional.interpolate(
                pred[None, None].float(), size=(self.H, self.W),
                mode="bilinear", align_corners=False)[0, 0].cpu().numpy()
            d = (d - d.min()) / (d.max() - d.min() + 1e-9)
            return {"depth": d.astype(np.float32)}
        return self.cached(f"depth_{size}", run)["depth"]

    def sam_masks(self, points: int, iou: float):
        def run():
            from transformers import pipeline
            pipe = pipeline("mask-generation", device="cpu",
                            model="facebook/sam-vit-large")
            try:
                out = pipe(self.img, points_per_batch=64,
                           points_per_crop=points, pred_iou_thresh=iou)
            except TypeError:
                out = pipe(self.img, points_per_batch=64,
                           pred_iou_thresh=iou)
            masks = np.stack([np.asarray(m) for m in out["masks"]])
            return {"masks": masks.astype(bool)}
        return self.cached(f"sam_p{points}_i{int(iou * 100)}", run)["masks"]

    def sam3(self, concept: str):
        def run():
            from transformers import Sam3Model, Sam3Processor
            dev = "cpu"
            if not hasattr(self, "_sam3"):
                self._sam3 = (
                    Sam3Model.from_pretrained("facebook/sam3").to(dev),
                    Sam3Processor.from_pretrained("facebook/sam3"))
            model, proc = self._sam3
            inputs = proc(images=self.img, text=concept,
                          return_tensors="pt").to(dev)
            with torch.no_grad():
                out = model(**inputs)
            r = proc.post_process_instance_segmentation(
                out, threshold=0.2, mask_threshold=0.5,
                target_sizes=[(self.H, self.W)])[0]
            masks = r["masks"].cpu().numpy().astype(bool)
            scores = r["scores"].cpu().numpy().astype(np.float32)
            if masks.ndim == 2:
                masks = masks[None]
            return {"masks": masks, "scores": scores}
        key = f"sam3_{concept.replace(' ', '_')}"
        d = self.cached(key, run)
        return d["masks"], d["scores"]

    def _resized(self, res: int):
        s = res / max(self.img.size)
        return self.img.resize((round(self.img.width * s),
                                round(self.img.height * s)), Image.LANCZOS)

    # ---------- shared post-processing ------------------------------------
    def sky_mask(self):
        seg, id2label = self.m2f_semantic("large", 1100)
        ids = [i for i, n in id2label.items() if "sky" in n.lower()]
        return np.isin(seg, ids)

    def group(self, seg, id2label):
        out = np.full(seg.shape, len(ARTIST_GROUPS), np.int16)  # other
        names = {len(ARTIST_GROUPS): "other"}
        for gi, (gname, words) in enumerate(ARTIST_GROUPS.items()):
            ids = [i for i, n in id2label.items()
                   if any(w in n.lower() for w in words)]
            out[np.isin(seg, ids)] = gi
            names[gi] = gname
        return out, names


def kmeans1d(vals, k, iters=25):
    centers = np.quantile(vals, np.linspace(0.1, 0.9, k))
    for _ in range(iters):
        a = np.abs(vals[:, None] - centers[None, :]).argmin(1)
        for i in range(k):
            if (a == i).any():
                centers[i] = vals[a == i].mean()
    return np.sort(centers)


def smooth_labels(seg, ksize):
    if ksize <= 1:
        return seg
    return cv2.medianBlur(seg.astype(np.uint8), ksize | 1)


# ---------------- families ------------------------------------------------
def fam_depth(b: Bakeoff):
    sky = b.sky_mask()
    for size in ("Small", "Large"):
        d = b.depth(size)
        land = ~sky
        for bands in (2, 3, 4, 5):
            for method in ("kmeans", "quantile"):
                dl = d[land]
                if method == "kmeans":
                    c = kmeans1d(dl, bands)
                    a = np.abs(d[..., None] - c[None, None, :]).argmin(2)
                else:
                    edges = np.quantile(dl, np.linspace(0, 1, bands + 1))
                    a = np.clip(np.digitize(d, edges[1:-1]), 0, bands - 1)
                for sm in (9, 21, 41):
                    seg = (a + 1).astype(np.uint8)
                    seg[sky] = 0
                    seg = smooth_labels(seg, sm)
                    seg[sky] = 0
                    names = {0: "sky", **{i + 1: f"d{i}" for i in
                                          range(bands)}}
                    b.panel("depth", seg, names,
                            f"DA-{size} {bands}bands {method} sm{sm}",
                            {"ckpt": size, "bands": bands,
                             "binning": method, "smooth": sm})


def fam_posterize(b: Bakeoff):
    from skimage.color import rgb2lab
    L = rgb2lab(b.rgb)[..., 0].astype(np.float32)
    for sigma in (0.008, 0.015, 0.025, 0.04, 0.06):
        Lb = cv2.GaussianBlur(L, (0, 0), sigma * b.W)
        for k in (3, 4, 5):
            c = kmeans1d(Lb.reshape(-1)[::7], k)
            seg = np.abs(Lb[..., None] - c[None, None, :]).argmin(2)
            for min_frac in (0.002, 0.008):
                s2 = smooth_labels(seg, 15)
                n, lab, stats, _ = cv2.connectedComponentsWithStats(
                    s2.astype(np.uint8) + 1, 8)
                for i in range(n):
                    if stats[i, cv2.CC_STAT_AREA] < min_frac * b.H * b.W:
                        m = lab == i
                        ring = cv2.dilate(m.astype(np.uint8),
                                          np.ones((3, 3), np.uint8)
                                          ).astype(bool) & ~m
                        if ring.any():
                            v, cts = np.unique(s2[ring], return_counts=True)
                            s2[m] = v[cts.argmax()]
                b.panel("posterize", s2,
                        {i: f"L{i}" for i in range(k)},
                        f"squint {sigma:.3f}w k{k} min{min_frac}",
                        {"sigma_frac": sigma, "levels": k,
                         "min_frac": min_frac})


def fam_m2f(b: Bakeoff):
    for ckpt in ("large", "base"):
        for res in (768, 1100):
            try:
                seg, id2label = b.m2f_semantic(ckpt, res)
            except Exception as e:
                log.warning("m2f %s@%s failed: %s", ckpt, res, e)
                continue
            for grouping in ("raw", "artist"):
                s, names = (b.group(seg, id2label) if grouping == "artist"
                            else (seg, {int(i): id2label[int(i)]
                                        for i in np.unique(seg)}))
                for sm in (0, 15):
                    b.panel("mask2former", smooth_labels(s, sm), names,
                            f"m2f-{ckpt} @{res} {grouping} sm{sm}",
                            {"ckpt": ckpt, "res": res, "grouping": grouping,
                             "smooth": sm})


def fam_segformer(b: Bakeoff):
    for ckpt, native in (("b4-finetuned-ade-512-512", 512),
                         ("b5-finetuned-ade-640-640", 640)):
        for res in (native, 1024):
            try:
                seg, id2label = b.segformer(ckpt, res)
            except Exception as e:
                log.warning("segformer %s@%s failed: %s", ckpt, res, e)
                continue
            for grouping in ("raw", "artist"):
                s, names = (b.group(seg, id2label) if grouping == "artist"
                            else (seg, {int(i): id2label[int(i)]
                                        for i in np.unique(seg)}))
                for sm in (0, 15):
                    b.panel("segformer", smooth_labels(s, sm), names,
                            f"{ckpt.split('-')[0]} @{res} {grouping} sm{sm}",
                            {"ckpt": ckpt, "res": res, "grouping": grouping,
                             "smooth": sm})


def fam_panoptic(b: Bakeoff):
    for res in (768, 1100):
        seg, names = b.m2f_panoptic(res)
        for min_frac in (0.002, 0.01):
            s = seg.copy()
            for rid in np.unique(s):
                m = s == rid
                if m.sum() < min_frac * b.H * b.W:
                    ring = cv2.dilate(m.astype(np.uint8),
                                      np.ones((3, 3), np.uint8)
                                      ).astype(bool) & ~m
                    if ring.any():
                        v, c = np.unique(s[ring], return_counts=True)
                        s[m] = v[c.argmax()]
            for sm in (0, 15):
                b.panel("panoptic", smooth_labels(s - s.min(), sm), names,
                        f"m2f-panoptic @{res} min{min_frac} sm{sm}",
                        {"res": res, "min_frac": min_frac, "smooth": sm})


def fam_sam(b: Bakeoff):
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from decompose.plan import (build_label_map, fill_unclaimed, merge_small,
                                merge_slivers, split_by_depth)
    dep = b.depth("Small")
    for points in (32, 64):
        for iou in (0.8, 0.88, 0.94):
            try:
                masks = b.sam_masks(points, iou)
            except Exception as e:
                log.warning("sam p%s i%s failed: %s", points, iou, e)
                continue
            for min_frac in (0.004, 0.012):
                for extras in ("raw", "clean", "clean+depth"):
                    labels = build_label_map(list(masks),
                                             (b.H, b.W), min_frac)
                    labels = fill_unclaimed(labels)
                    if "clean" in extras:
                        labels = merge_slivers(labels, 0.02, 0.4)
                    if "depth" in extras:
                        labels = split_by_depth(labels, dep, 0.35, 3,
                                                min_frac)
                    labels = merge_small(labels, min_frac)
                    b.panel("sam", labels, None,
                            f"SAM-L p{points} iou{iou} min{min_frac} "
                            f"{extras}",
                            {"points": points, "iou": iou,
                             "min_frac": min_frac, "post": extras})


def fam_sam3(b: Bakeoff):
    concepts = {}
    for c in SAM3_VOCAB:
        try:
            masks, scores = b.sam3(c)
            concepts[c] = (masks, scores)
            m = masks[scores > 0.3].any(0) if (scores > 0.3).any() \
                else np.zeros((b.H, b.W), bool)
            b.panel("sam3", m.astype(np.uint8), {1: c, 0: ""},
                    f"concept: {c} ({len(scores)} inst)",
                    {"concept": c, "instances": int(len(scores))})
        except Exception as e:
            log.warning("sam3 %r failed: %s", c, e)
            if not concepts and c == SAM3_VOCAB[1]:
                raise  # API/weights broken — fail the family fast
    subsets = {"minimal": ["sky", "mountain", "tree", "snow"],
               "landscape": ["sky", "cloud", "mountain", "snow", "tree",
                             "forest", "rock face", "ridge"],
               "rich": SAM3_VOCAB}
    for sub, vocab in subsets.items():
        for thresh in (0.3, 0.5, 0.7):
            for order in ("first-wins", "last-wins"):
                seg = np.zeros((b.H, b.W), np.int16)
                names = {0: "none"}
                vs = vocab if order == "first-wins" else vocab[::-1]
                for ci, c in enumerate(vs, 1):
                    if c not in concepts:
                        continue
                    masks, scores = concepts[c]
                    keep = scores >= thresh
                    if not keep.any():
                        continue
                    m = masks[keep].any(0)
                    if order == "first-wins":
                        seg[m & (seg == 0)] = ci
                    else:
                        seg[m] = ci
                    names[ci] = c
                b.panel("sam3", seg, names,
                        f"compose {sub} t{thresh} {order}",
                        {"subset": sub, "thresh": thresh, "order": order})


def fam_composite(b: Bakeoff):
    sky = b.sky_mask()
    seg, id2label = b.m2f_semantic("large", 1100)
    gs, gnames = b.group(seg, id2label)
    tree_gi = [k for k, v in gnames.items() if v == "tree"][0]
    trees = gs == tree_gi
    from skimage.color import rgb2lab
    L = rgb2lab(b.rgb)[..., 0].astype(np.float32)
    d = b.depth("Small")
    for bands in (2, 3, 4):
        c = kmeans1d(d[~sky], bands)
        planes = np.abs(d[..., None] - c[None, None, :]).argmin(2) + 1
        for use_trees in (True, False):
            for tone in (0, 2, 3):
                comp = planes.astype(np.uint8)
                comp[sky] = 0
                names = {0: "sky", **{i + 1: f"d{i}" for i in range(bands)}}
                nxt = bands + 1
                if use_trees:
                    comp[trees & ~sky] = nxt
                    names[nxt] = "trees"
                    nxt += 1
                if tone > 0:
                    # split the NEAREST band by squinted tone
                    near = comp == bands
                    Lb = cv2.GaussianBlur(L, (0, 0), 0.02 * b.W)
                    tc = kmeans1d(Lb[near].reshape(-1), tone)
                    ta = np.abs(Lb[..., None] - tc[None, None, :]).argmin(2)
                    for t in range(1, tone):
                        comp[near & (ta == t)] = nxt
                        names[nxt] = f"near-L{t}"
                        nxt += 1
                comp = smooth_labels(comp, 9)
                b.panel("composite", comp, names,
                        f"{bands}bands trees={use_trees} tone{tone}",
                        {"bands": bands, "trees": use_trees,
                         "tone_split": tone})


def _depth_normals(b: Bakeoff, size: str, blur_frac: float):
    d = cv2.GaussianBlur(b.depth(size), (0, 0), blur_frac * b.W)
    gx = cv2.Sobel(d, cv2.CV_32F, 1, 0, ksize=5)
    gy = cv2.Sobel(d, cv2.CV_32F, 0, 1, ksize=5)
    return gx, gy


def fam_faces(b: Bakeoff):
    """Cluster surface-normal DIRECTION from depth: two sides of an arete
    differ in orientation even at identical depth, so region boundaries
    fall on the ridge lines the tone/depth/semantic families all miss.
    Macro blurs: monocular depth is only trustworthy at mountain scale."""
    sky = b.sky_mask()
    land = ~sky
    for size in ("Small", "Large"):
        for blur_frac in (0.025, 0.06, 0.1):
            gx, gy = _depth_normals(b, size, blur_frac)
            mag = np.hypot(gx, gy) + 1e-8
            feats = np.stack([gx / mag, gy / mag], -1)[land].astype(
                np.float32)
            for k in (3, 4, 5):
                crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
                        30, 1e-3)
                _, lab, _ = cv2.kmeans(feats, k, None, crit, 3,
                                       cv2.KMEANS_PP_CENTERS)
                for sm in (21, 41):
                    seg = np.zeros((b.H, b.W), np.uint8)
                    seg[land] = lab.ravel() + 1
                    seg = smooth_labels(seg, sm)
                    seg[sky] = 0
                    b.panel("faces", seg,
                            {0: "sky", **{i + 1: f"face{i}" for i in
                                          range(k)}},
                            f"normals DA-{size} blur{blur_frac} k{k} "
                            f"sm{sm}",
                            {"ckpt": size, "blur_frac": blur_frac,
                             "k": k, "smooth": sm})


def fam_creasecut(b: Bakeoff):
    """Lines first, regions second (how an artist works): detect crease
    lines as edges OF THE NORMAL MAP, cut the land into connected faces
    along them — boundaries are ridge lines end to end."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from decompose.plan import fill_unclaimed, merge_small
    sky = b.sky_mask()
    land = ~sky
    for size in ("Small", "Large"):
        for blur_frac in (0.02, 0.05):
            gx, gy = _depth_normals(b, size, blur_frac)
            # crease strength = how fast the facing direction changes;
            # percentile threshold adapts to however smooth the depth is
            curv = (np.abs(cv2.Sobel(gx, cv2.CV_32F, 1, 0)) +
                    np.abs(cv2.Sobel(gy, cv2.CV_32F, 0, 1)))
            for pct in (88, 95):
                thr = np.percentile(curv[land], pct)
                lines = cv2.dilate((curv >= thr).astype(np.uint8),
                                   np.ones((3, 3), np.uint8)) > 0
                free = land & ~lines
                _, comp = cv2.connectedComponents(free.astype(np.uint8), 8)
                for min_frac in (0.004, 0.012):
                    labels = comp.astype(np.int32)
                    labels = fill_unclaimed(labels)  # lines join a side
                    labels = merge_small(labels, min_frac)
                    labels[sky] = 0
                    b.panel("creasecut", labels, None,
                            f"DA-{size} blur{blur_frac} pct{pct} "
                            f"min{min_frac}",
                            {"ckpt": size, "blur_frac": blur_frac,
                             "pct": pct, "min_frac": min_frac})


def fam_watershed(b: Bakeoff):
    """Watershed: regions bounded by the strongest crease/edge lines."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from decompose.plan import merge_small
    from scipy import ndimage
    from skimage.morphology import h_minima
    from skimage.segmentation import watershed
    from skimage.color import rgb2lab
    sky = b.sky_mask()
    land = ~sky
    L = rgb2lab(b.rgb)[..., 0].astype(np.float32)
    for src in ("lum", "depthS", "depthL"):
        if src == "lum":
            base = L / 100.0
        else:
            base = b.depth("Small" if src == "depthS" else "Large")
        for blur_frac in (0.006, 0.015):
            f = cv2.GaussianBlur(base, (0, 0), blur_frac * b.W)
            grad = np.hypot(cv2.Sobel(f, cv2.CV_32F, 1, 0),
                            cv2.Sobel(f, cv2.CV_32F, 0, 1))
            grad /= grad.max() + 1e-9
            for h in (0.02, 0.06):
                mk, _ = ndimage.label(h_minima(grad, h))
                ws = watershed(grad, mk, mask=land).astype(np.int32)
                ws = merge_small(ws, 0.006)
                ws[sky] = 0
                b.panel("watershed", ws, None,
                        f"{src} blur{blur_frac} h{h}",
                        {"source": src, "blur_frac": blur_frac, "h": h})


def fam_litshadow(b: Bakeoff):
    """The artist's FIRST decision, isolated: land splits into lit vs
    shadow only (the user's starred k3 posterizes work because this
    boundary traces the sunlit arete)."""
    from skimage.color import rgb2lab
    sky = b.sky_mask()
    land = ~sky
    L = rgb2lab(b.rgb)[..., 0].astype(np.float32)
    for sigma in (0.01, 0.02, 0.03, 0.05):
        Lb = cv2.GaussianBlur(L, (0, 0), sigma * b.W)
        c = kmeans1d(Lb[land].reshape(-1)[::5], 2)
        seg = np.zeros((b.H, b.W), np.uint8)
        seg[land] = (np.abs(Lb[land][:, None] - c[None, :]).argmin(1)
                     + 1).astype(np.uint8)
        for min_frac in (0.002, 0.01):
            s2 = smooth_labels(seg, 15)
            n, lab, stats, _ = cv2.connectedComponentsWithStats(s2, 8)
            for i in range(n):
                if stats[i, cv2.CC_STAT_AREA] < min_frac * b.H * b.W:
                    m = lab == i
                    ring = cv2.dilate(m.astype(np.uint8),
                                      np.ones((3, 3), np.uint8)
                                      ).astype(bool) & ~m
                    if ring.any():
                        v, cts = np.unique(s2[ring], return_counts=True)
                        s2[m] = v[cts.argmax()]
            s2[sky] = 0
            b.panel("litshadow", s2, {0: "sky", 1: "shadow", 2: "lit"},
                    f"squint {sigma}w min{min_frac}",
                    {"sigma_frac": sigma, "min_frac": min_frac})


def fam_felz(b: Bakeoff):
    """Graph-based region proposals — the classic non-semantic wildcard."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from decompose.plan import merge_small
    from skimage.segmentation import felzenszwalb
    for scale in (200, 600, 1500):
        for min_frac in (0.003, 0.01):
            seg = felzenszwalb(b.rgb, scale=scale, sigma=1.2,
                               min_size=int(min_frac * b.H * b.W))
            seg = merge_small(seg.astype(np.int32), min_frac)
            b.panel("felz", seg, None,
                    f"scale{scale} min{min_frac}",
                    {"scale": scale, "min_frac": min_frac})


def fam_normals(b: Bakeoff):
    """TRUE surface normals from a monocular normal-estimation model
    (Marigold) — per-pixel facing direction predicted from the photo
    itself, not differentiated from smooth depth. Masses grouped by the
    angle they face; the direct answer to 'separate by facing'."""
    def run():
        import diffusers
        dev = "mps" if torch.backends.mps.is_available() else "cpu"
        pipe = diffusers.MarigoldNormalsPipeline.from_pretrained(
            "prs-eth/marigold-normals-lcm-v0-1",
            torch_dtype=torch.float32).to(dev)
        out = pipe(b.img, num_inference_steps=4, ensemble_size=1)
        n = np.asarray(out.prediction[0], dtype=np.float32)
        if n.shape[:2] != (b.H, b.W):
            n = cv2.resize(n, (b.W, b.H), interpolation=cv2.INTER_LINEAR)
        return {"normals": n}
    n = b.cached("marigold_normals", run)["normals"]
    sky = b.sky_mask()
    land = ~sky

    vis = ((n + 1) / 2 * 255).astype(np.uint8)
    fname = "normals__raw.png"
    cv2.imwrite(str(b.out / "imgs" / fname),
                cv2.cvtColor(vis, cv2.COLOR_RGB2BGR))
    b.manifest.append({"id": fname[:-4], "family": "normals",
                       "title": "raw normal map (marigold-lcm)",
                       "params": {}, "img": f"imgs/{fname}"})

    for blur_frac in (0.0, 0.015, 0.04):
        nb = n if blur_frac == 0 else cv2.GaussianBlur(
            n, (0, 0), blur_frac * b.W)
        feats = nb[land].astype(np.float32)
        for k in (3, 4, 5, 6):
            crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
                    30, 1e-3)
            _, lab, _ = cv2.kmeans(feats, k, None, crit, 3,
                                   cv2.KMEANS_PP_CENTERS)
            for sm in (15, 31):
                seg = np.zeros((b.H, b.W), np.uint8)
                seg[land] = lab.ravel() + 1
                seg = smooth_labels(seg, sm)
                seg[sky] = 0
                b.panel("normals", seg,
                        {0: "sky", **{i + 1: f"face{i}" for i in range(k)}},
                        f"marigold blur{blur_frac} k{k} sm{sm}",
                        {"blur_frac": blur_frac, "k": k, "smooth": sm})


def _rag_weight(graph, src, dst, n):
    d = {"weight": 0.0, "count": 0}
    cs, cd = graph[src].get(n, d)["count"], graph[dst].get(n, d)["count"]
    ws, wd = graph[src].get(n, d)["weight"], graph[dst].get(n, d)["weight"]
    return {"count": cs + cd,
            "weight": (cs * ws + cd * wd) / max(cs + cd, 1)}


def _rag_merge(graph, src, dst):
    pass


def fam_watershed2(b: Bakeoff):
    """Tuned watershed: oversegment on purpose, then merge neighbors whose
    shared boundary is WEAK (RAG hierarchical merge). Only boundaries with
    real support — creases, lit/shadow flips, strong edges — survive, so
    the arbitrary flat-area polygons of plain watershed melt away."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from decompose.plan import merge_small
    from scipy import ndimage
    from skimage import graph as skgraph
    from skimage.color import rgb2lab
    from skimage.morphology import h_minima
    from skimage.segmentation import watershed
    sky = b.sky_mask()
    land = ~sky
    L = rgb2lab(b.rgb)[..., 0].astype(np.float32)

    gx, gy = _depth_normals(b, "Large", 0.02)
    cr = (np.abs(cv2.Sobel(gx, cv2.CV_32F, 1, 0)) +
          np.abs(cv2.Sobel(gy, cv2.CV_32F, 0, 1)))
    cr /= cr.max() + 1e-9
    Lb = cv2.GaussianBlur(L, (0, 0), 0.01 * b.W)
    lg = np.hypot(cv2.Sobel(Lb, cv2.CV_32F, 1, 0),
                  cv2.Sobel(Lb, cv2.CV_32F, 0, 1))
    lg /= lg.max() + 1e-9
    c2 = kmeans1d(Lb[land].reshape(-1)[::5], 2)
    lit = (np.abs(Lb - c2[1]) < np.abs(Lb - c2[0])).astype(np.uint8)
    lse = (cv2.morphologyEx(lit, cv2.MORPH_GRADIENT,
                            np.ones((3, 3), np.uint8)) > 0).astype(
        np.float32)
    lse = cv2.GaussianBlur(lse, (0, 0), 2)

    fields = {"crease": cr, "lum": lg,
              "crease+shadow": np.maximum(cr, lse * 0.8),
              "crease+lum": np.maximum(cr, lg)}
    for fname_, field in fields.items():
        mk, _ = ndimage.label(h_minima(field, 0.01))
        over = watershed(field, mk, mask=land)
        for thresh in (0.03, 0.08, 0.15):
            rag = skgraph.rag_boundary(over, field.astype(np.float64))
            seg = skgraph.merge_hierarchical(
                over, rag, thresh, rag_copy=True, in_place_merge=True,
                merge_func=_rag_merge, weight_func=_rag_weight)
            seg = merge_small(seg.astype(np.int32), 0.006)
            seg[sky] = 0
            b.panel("watershed2", seg, None,
                    f"{fname_} merge<{thresh}",
                    {"field": fname_, "merge_thresh": thresh})


def fam_plan(b: Bakeoff):
    """The layered plan, assembled from each aspect's best finder:
    semantic silhouette + clouds split WITHIN sky + land masses by facing
    (marigold normals, fallback depth-normals) + trees stamped on top."""
    from skimage.color import rgb2lab
    sky = b.sky_mask()
    land = ~sky
    seg_sem, id2label = b.m2f_semantic("large", 1100)
    gs, gnames = b.group(seg_sem, id2label)
    tree_gi = [k for k, v in gnames.items() if v == "tree"][0]
    trees = (gs == tree_gi) & land
    L = rgb2lab(b.rgb)[..., 0].astype(np.float32)

    # clouds: gentle squint posterize INSIDE the sky mask only
    Lb = cv2.GaussianBlur(L, (0, 0), 0.008 * b.W)
    cloud = np.zeros((b.H, b.W), bool)
    if sky.sum() > 0.02 * b.H * b.W:
        c = kmeans1d(Lb[sky].reshape(-1)[::3], 2)
        bright = Lb >= c.mean()
        frac = float((bright & sky).sum() / sky.sum())
        if 0.01 < frac < 0.6:  # skip if sky is cloudless or overcast-flat
            cloud = bright & sky

    try:
        n = b.cached("marigold_normals", lambda: (_ for _ in ()).throw(
            RuntimeError("no cache")))["normals"]
        sources = [("marigold", n)]
    except Exception:
        sources = []
    gx, gy = _depth_normals(b, "Large", 0.04)
    mag = np.hypot(gx, gy) + 1e-8
    sources.append(("depthL", np.stack([gx / mag, gy / mag], -1)))

    for sname, nmap in sources:
        for k in (3, 4):
            feats = (nmap[land].reshape(-1, nmap.shape[-1])
                     .astype(np.float32))
            crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
                    30, 1e-3)
            _, lab, _ = cv2.kmeans(feats, k, None, crit, 3,
                                   cv2.KMEANS_PP_CENTERS)
            for sm in (21, 41):
                for use_trees in (True, False):
                    seg = np.zeros((b.H, b.W), np.uint8)
                    seg[land] = lab.ravel() + 2
                    seg = smooth_labels(seg, sm)
                    seg[sky] = 0
                    seg[cloud] = 1
                    names = {0: "sky", 1: "cloud",
                             **{i + 2: f"face{i}" for i in range(k)}}
                    if use_trees:
                        seg[trees] = k + 2
                        names[k + 2] = "trees"
                    b.panel("plan", seg, names,
                            f"{sname} k{k} sm{sm} trees={use_trees}",
                            {"normals": sname, "k": k, "smooth": sm,
                             "trees": use_trees})


CLIPSEG_PROMPTS = ["sky", "clouds", "mountain", "snow", "forest", "trees",
                   "rock", "grass", "water"]


def fam_clipseg(b: Bakeoff):
    """Text-prompted segmentation WITHOUT the SAM3 gate: CLIPSeg heats one
    map per prompt; argmax composes a named plan from OUR vocabulary."""
    def run():
        from transformers import (CLIPSegForImageSegmentation,
                                  CLIPSegProcessor)
        proc = CLIPSegProcessor.from_pretrained("CIDAS/clipseg-rd64-refined")
        model = CLIPSegForImageSegmentation.from_pretrained(
            "CIDAS/clipseg-rd64-refined")
        inputs = proc(text=CLIPSEG_PROMPTS,
                      images=[b.img] * len(CLIPSEG_PROMPTS),
                      return_tensors="pt", padding=True)
        with torch.no_grad():
            out = model(**inputs)
        logits = out.logits
        if logits.ndim == 2:
            logits = logits[None]
        return {"heat": torch.sigmoid(logits).numpy()}
    heat = b.cached("clipseg", run)["heat"]
    hr = np.stack([cv2.resize(h, (b.W, b.H)) for h in heat])
    names = dict(enumerate(CLIPSEG_PROMPTS))
    names[len(CLIPSEG_PROMPTS)] = "?"
    for thr in (0.35, 0.55):
        for sm in (0, 15):
            seg = hr.argmax(0).astype(np.uint8)
            seg[hr.max(0) < thr] = len(CLIPSEG_PROMPTS)
            b.panel("clipseg", smooth_labels(seg, sm), names,
                    f"argmax t{thr} sm{sm}", {"thr": thr, "smooth": sm})
    for i, pmt in enumerate(CLIPSEG_PROMPTS[:6]):
        b.panel("clipseg", (hr[i] > 0.5).astype(np.uint8), {1: pmt, 0: ""},
                f"mask: {pmt}", {"prompt": pmt})


def fam_upernet(b: Bakeoff):
    def run():
        from transformers import (AutoImageProcessor,
                                  UperNetForSemanticSegmentation)
        name = "openmmlab/upernet-convnext-large"
        proc = AutoImageProcessor.from_pretrained(name)
        model = UperNetForSemanticSegmentation.from_pretrained(name)
        with torch.no_grad():
            out = model(**proc(images=b.img, return_tensors="pt"))
        logits = torch.nn.functional.interpolate(
            out.logits, size=(b.H, b.W), mode="bilinear",
            align_corners=False)
        labels = json.dumps({int(k): v for k, v
                             in model.config.id2label.items()})
        return {"seg": logits.argmax(1)[0].numpy().astype(np.int16),
                "id2label": labels}
    d = b.cached("upernet", run)
    seg = d["seg"]
    id2label = {int(k): v for k, v
                in json.loads(str(d["id2label"])).items()}
    for grouping in ("raw", "artist"):
        s, names = (b.group(seg, id2label) if grouping == "artist"
                    else (seg, {int(i): id2label[int(i)]
                                for i in np.unique(seg)}))
        for sm in (0, 15):
            b.panel("upernet", smooth_labels(s, sm), names,
                    f"upernet-convnext-L {grouping} sm{sm}",
                    {"grouping": grouping, "smooth": sm})


def fam_dino(b: Bakeoff):
    """DINOv2 features clustered — unsupervised semantic-ish parcels."""
    def run():
        from transformers import AutoImageProcessor, Dinov2Model
        proc = AutoImageProcessor.from_pretrained("facebook/dinov2-base")
        model = Dinov2Model.from_pretrained("facebook/dinov2-base")
        try:
            inputs = proc(images=b.img, return_tensors="pt",
                          size={"shortest_edge": 518},
                          do_center_crop=False)
        except Exception:
            inputs = proc(images=b.img, return_tensors="pt")
        with torch.no_grad():
            out = model(**inputs)
        hp = inputs["pixel_values"].shape[2] // 14
        wp = inputs["pixel_values"].shape[3] // 14
        feats = out.last_hidden_state[0, 1:1 + hp * wp].numpy()
        return {"feats": feats.astype(np.float16),
                "grid": np.array([hp, wp])}
    d = b.cached("dinov2", run)
    feats = d["feats"].astype(np.float32)
    hp, wp = [int(x) for x in d["grid"]]
    feats /= np.linalg.norm(feats, axis=1, keepdims=True) + 1e-8
    ys, xs = np.mgrid[0:hp, 0:wp]
    xy = np.stack([xs.ravel() / wp, ys.ravel() / hp], 1).astype(np.float32)
    for k in (6, 10):
        for xyw in (0.0, 0.25):
            f = np.concatenate([feats, xy * xyw * 8], 1)
            crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
                    40, 1e-3)
            _, lab, _ = cv2.kmeans(f, k, None, crit, 3,
                                   cv2.KMEANS_PP_CENTERS)
            seg = cv2.resize(lab.reshape(hp, wp).astype(np.uint8),
                             (b.W, b.H), interpolation=cv2.INTER_NEAREST)
            for sm in (0, 21):
                b.panel("dino", smooth_labels(seg, sm), None,
                        f"dinov2 k{k} xy{xyw} sm{sm}",
                        {"k": k, "xy_weight": xyw, "smooth": sm})


def _marigold_or_depth_normals(b: Bakeoff):
    p = b.out / "cache" / "marigold_normals.npz"
    if p.exists():
        return np.load(p)["normals"].astype(np.float32)
    gx, gy = _depth_normals(b, "Large", 0.04)
    mag = np.hypot(gx, gy) + 1e-8
    return np.stack([gx / mag, gy / mag, np.zeros_like(gx)], -1)


def fam_crossings(b: Bakeoff):
    """Creative overlaps: form (facing) x light x depth — the aspects the
    user validated separately, intersected into richer plans."""
    from skimage.color import rgb2lab
    sky = b.sky_mask()
    land = ~sky
    n = _marigold_or_depth_normals(b)
    L = rgb2lab(b.rgb)[..., 0].astype(np.float32)
    Lb = cv2.GaussianBlur(L, (0, 0), 0.02 * b.W)
    c2 = kmeans1d(Lb[land].reshape(-1)[::5], 2)
    lit = (np.abs(Lb - c2[1]) < np.abs(Lb - c2[0]))
    d = b.depth("Small")

    def faces_k(k, blur):
        nb = cv2.GaussianBlur(n, (0, 0), blur * b.W)
        feats = nb[land].reshape(-1, nb.shape[-1]).astype(np.float32)
        crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
                30, 1e-3)
        _, lab, _ = cv2.kmeans(feats, k, None, crit, 3,
                               cv2.KMEANS_PP_CENTERS)
        seg = np.zeros((b.H, b.W), np.uint8)
        seg[land] = lab.ravel() + 1
        return seg

    for sm in (21, 41):
        f3 = faces_k(3, 0.03)
        seg = np.zeros((b.H, b.W), np.uint8)
        seg[land] = (f3[land] - 1) * 2 + lit[land] + 1
        seg = smooth_labels(seg, sm)
        seg[sky] = 0
        names = {0: "sky"}
        for fi in range(3):
            for li, ln_ in enumerate(("shade", "lit")):
                names[fi * 2 + li + 1] = f"f{fi}/{ln_}"
        b.panel("crossings", seg, names, f"faces3 x lit2 sm{sm}",
                {"mix": "faces3xlit2", "smooth": sm})

    dl = d[land]
    cd = kmeans1d(dl, 3)
    planes = np.abs(d[..., None] - cd[None, None, :]).argmin(2)
    seg = np.zeros((b.H, b.W), np.uint8)
    seg[land] = planes[land] * 2 + lit[land] + 1
    seg = smooth_labels(seg, 21)
    seg[sky] = 0
    names = {0: "sky"}
    for pi in range(3):
        for li, ln_ in enumerate(("shade", "lit")):
            names[pi * 2 + li + 1] = f"d{pi}/{ln_}"
    b.panel("crossings", seg, names, "planes3 x lit2 sm21",
            {"mix": "planes3xlit2"})

    f2 = faces_k(2, 0.04)
    seg = np.zeros((b.H, b.W), np.uint8)
    seg[land] = (planes[land] * 2 + (f2[land] - 1)) + 1
    seg = smooth_labels(seg, 21)
    seg[sky] = 0
    b.panel("crossings", seg, None, "planes3 x faces2 sm21",
            {"mix": "planes3xfaces2"})


def fam_felznorm(b: Bakeoff):
    """Graph segmentation ON THE NORMAL MAP — angular parcels by facing."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from decompose.plan import merge_small
    from skimage.segmentation import felzenszwalb
    n = _marigold_or_depth_normals(b)
    img = ((n + 1) / 2 * 255).astype(np.uint8)
    sky = b.sky_mask()
    for scale in (200, 600, 1400):
        seg = felzenszwalb(img, scale=scale, sigma=1.0,
                           min_size=int(0.004 * b.H * b.W))
        seg = merge_small(seg.astype(np.int32), 0.004)
        seg[sky] = seg.max() + 1
        b.panel("felznorm", seg, None, f"felz-on-normals scale{scale}",
                {"scale": scale})


def fam_watershed3(b: Bakeoff):
    """Fine merge-threshold sweep of the two best watershed2 fields."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from decompose.plan import merge_small
    from scipy import ndimage
    from skimage import graph as skgraph
    from skimage.color import rgb2lab
    from skimage.morphology import h_minima
    from skimage.segmentation import watershed
    sky = b.sky_mask()
    land = ~sky
    L = rgb2lab(b.rgb)[..., 0].astype(np.float32)
    gx, gy = _depth_normals(b, "Large", 0.02)
    cr = (np.abs(cv2.Sobel(gx, cv2.CV_32F, 1, 0)) +
          np.abs(cv2.Sobel(gy, cv2.CV_32F, 0, 1)))
    cr /= cr.max() + 1e-9
    Lb = cv2.GaussianBlur(L, (0, 0), 0.01 * b.W)
    lg = np.hypot(cv2.Sobel(Lb, cv2.CV_32F, 1, 0),
                  cv2.Sobel(Lb, cv2.CV_32F, 0, 1))
    lg /= lg.max() + 1e-9
    c2 = kmeans1d(Lb[land].reshape(-1)[::5], 2)
    lit = (np.abs(Lb - c2[1]) < np.abs(Lb - c2[0])).astype(np.uint8)
    lse = cv2.GaussianBlur(
        (cv2.morphologyEx(lit, cv2.MORPH_GRADIENT,
                          np.ones((3, 3), np.uint8)) > 0
         ).astype(np.float32), (0, 0), 2)
    for fname_, field in (("crease+shadow", np.maximum(cr, lse * 0.8)),
                          ("crease+lum", np.maximum(cr, lg))):
        mk, _ = ndimage.label(h_minima(field, 0.01))
        over = watershed(field, mk, mask=land)
        for thresh in (0.02, 0.05, 0.12, 0.2, 0.3):
            rag = skgraph.rag_boundary(over, field.astype(np.float64))
            seg = skgraph.merge_hierarchical(
                over, rag, thresh, rag_copy=True, in_place_merge=True,
                merge_func=_rag_merge, weight_func=_rag_weight)
            seg = merge_small(seg.astype(np.int32), 0.006)
            seg[sky] = 0
            b.panel("watershed3", seg, None,
                    f"{fname_} merge<{thresh}",
                    {"field": fname_, "merge_thresh": thresh})


def fam_plansheet(b: Bakeoff):
    """Artist's prep sheet: pastel region blocks + black crease lines."""
    sky = b.sky_mask()
    land = ~sky
    n = _marigold_or_depth_normals(b)
    for k in (3, 4):
        nb = cv2.GaussianBlur(n, (0, 0), 0.03 * b.W)
        feats = nb[land].reshape(-1, nb.shape[-1]).astype(np.float32)
        crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
                30, 1e-3)
        _, lab, _ = cv2.kmeans(feats, k, None, crit, 3,
                               cv2.KMEANS_PP_CENTERS)
        seg = np.zeros((b.H, b.W), np.uint8)
        seg[land] = lab.ravel() + 1
        seg = smooth_labels(seg, 31)
        seg[sky] = 0
        for pct in (90, 95):
            ns = cv2.GaussianBlur(n, (0, 0), 0.008 * b.W)
            curv = (np.abs(cv2.Sobel(ns[..., 0], cv2.CV_32F, 1, 0)) +
                    np.abs(cv2.Sobel(ns[..., 1], cv2.CV_32F, 0, 1)))
            lines = curv >= np.percentile(curv[land], pct)
            vis = np.full((b.H, b.W, 3), 248, np.uint8)
            pal = np.array([[235, 240, 248], [214, 228, 244],
                            [236, 232, 218], [222, 238, 226],
                            [240, 226, 226]], np.uint8)
            for rid in range(1, k + 1):
                vis[seg == rid] = pal[rid % len(pal)]
            e = cv2.Canny(seg * 37, 0, 0) > 0
            vis[e] = (120, 130, 150)
            vis[lines & land] = (30, 30, 30)
            import hashlib
            params = {"k": k, "line_pct": pct}
            h = hashlib.md5(json.dumps(params, sort_keys=True).encode()
                            ).hexdigest()[:8]
            i = len([m for m in b.manifest
                     if m["family"] == "plansheet"])
            fname = f"plansheet__{i:03d}_{h}.png"
            cv2.imwrite(str(b.out / "imgs" / fname),
                        cv2.cvtColor(vis, cv2.COLOR_RGB2BGR))
            b.manifest.append({"id": fname[:-4], "family": "plansheet",
                               "title": f"prep sheet k{k} lines p{pct}",
                               "params": params, "img": f"imgs/{fname}"})


def fam_fusion(b: Bakeoff):
    """Trust matrix: each channel contributes ONLY the decision it's
    trusted for. Silhouette <- semantic (posterize can't find it); tone
    LEVELS <- posterize (globally consistent brightness, which region
    maps can't promise); mass BOUNDARIES <- watershed on crease+shadow;
    light <- litshadow. The user's layering thesis, composited."""
    from scipy import ndimage
    from skimage import graph as skgraph
    from skimage.color import rgb2lab
    from skimage.morphology import h_minima
    from skimage.segmentation import watershed
    sky = b.sky_mask()
    land = ~sky
    L = rgb2lab(b.rgb)[..., 0].astype(np.float32)

    def poster_levels(sigma_frac, k):
        Lb = cv2.GaussianBlur(L, (0, 0), sigma_frac * b.W)
        c = kmeans1d(Lb[land].reshape(-1)[::5], k)
        return np.abs(Lb[..., None] - c[None, None, :]).argmin(2)

    # A: silhouette x posterize — sky boundary from semantic, tone levels
    # globally consistent inside the land
    for sig in (0.01, 0.02):
        for k in (3, 4):
            lev = poster_levels(sig, k)
            seg = np.zeros((b.H, b.W), np.uint8)
            seg[land] = lev[land] + 1
            seg = smooth_labels(seg, 15)
            seg[sky] = 0
            names = {0: "sky", **{i + 1: f"L{i}" for i in range(k)}}
            b.panel("fusion", seg, names,
                    f"silhouette x posterize s{sig} k{k}",
                    {"mix": "sil_x_poster", "sigma": sig, "k": k})

    # B: watershed masses COMMITTED to their majority posterize level —
    # angular image-derived boundaries + a consistent global value plan
    gx, gy = _depth_normals(b, "Large", 0.02)
    cr = (np.abs(cv2.Sobel(gx, cv2.CV_32F, 1, 0)) +
          np.abs(cv2.Sobel(gy, cv2.CV_32F, 0, 1)))
    cr /= cr.max() + 1e-9
    Lb = cv2.GaussianBlur(L, (0, 0), 0.01 * b.W)
    c2 = kmeans1d(Lb[land].reshape(-1)[::5], 2)
    lit = (np.abs(Lb - c2[1]) < np.abs(Lb - c2[0])).astype(np.uint8)
    lse = cv2.GaussianBlur(
        (cv2.morphologyEx(lit, cv2.MORPH_GRADIENT,
                          np.ones((3, 3), np.uint8)) > 0
         ).astype(np.float32), (0, 0), 2)
    field = np.maximum(cr, lse * 0.8)
    mk, _ = ndimage.label(h_minima(field, 0.01))
    over = watershed(field, mk, mask=land)
    for merge in (0.12, 0.2):
        rag = skgraph.rag_boundary(over, field.astype(np.float64))
        masses = skgraph.merge_hierarchical(
            over, rag, merge, rag_copy=True, in_place_merge=True,
            merge_func=_rag_merge, weight_func=_rag_weight)
        for k in (3, 4):
            lev = poster_levels(0.012, k)
            seg = np.zeros((b.H, b.W), np.uint8)
            for rid in np.unique(masses[land]):
                m = masses == rid
                vals, cts = np.unique(lev[m & land], return_counts=True)
                seg[m & land] = vals[cts.argmax()] + 1
            seg[sky] = 0
            names = {0: "sky", **{i + 1: f"L{i}" for i in range(k)}}
            b.panel("fusion", seg, names,
                    f"masses(m{merge}) committed to poster k{k}",
                    {"mix": "masses_commit_poster", "merge": merge,
                     "k": k})

    # C: B's best guess x litshadow — value plan split by the sun line
    lev = poster_levels(0.012, 3)
    seg = np.zeros((b.H, b.W), np.uint8)
    seg[land] = (lev[land] * 2 + lit[land]) + 1
    seg = smooth_labels(seg, 15)
    seg[sky] = 0
    names = {0: "sky"}
    for li in range(3):
        for s2, nm in enumerate(("shade", "lit")):
            names[li * 2 + s2 + 1] = f"L{li}/{nm}"
    b.panel("fusion", seg, names, "poster3 x litshadow",
            {"mix": "poster_x_lit"})


FAMILIES = {"m2f": fam_m2f, "depth": fam_depth, "posterize": fam_posterize,
            "segformer": fam_segformer, "panoptic": fam_panoptic,
            "composite": fam_composite, "sam": fam_sam, "sam3": fam_sam3,
            "faces": fam_faces, "creasecut": fam_creasecut,
            "watershed": fam_watershed, "litshadow": fam_litshadow,
            "felz": fam_felz, "normals": fam_normals, "plan": fam_plan,
            "watershed2": fam_watershed2, "clipseg": fam_clipseg,
            "upernet": fam_upernet, "dino": fam_dino,
            "crossings": fam_crossings, "felznorm": fam_felznorm,
            "watershed3": fam_watershed3, "plansheet": fam_plansheet,
            "fusion": fam_fusion}


def write_gallery(out: Path):
    (out / "index.html").write_text(GALLERY_HTML)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("photo", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--families", default="all")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(message)s")
    out = args.out or Path("runs/bakeoff") / args.photo.stem
    b = Bakeoff(args.photo, out)
    write_gallery(out)
    fams = (list(FAMILIES) if args.families == "all"
            else args.families.split(","))
    status = {}
    for name in fams:
        b.manifest = [m for m in b.manifest if m["family"] != name]
        status[name] = "running"
        b.flush(status)
        log.info("=== family %s", name)
        try:
            FAMILIES[name](b)
            status[name] = "done"
        except Exception as e:
            log.error("family %s FAILED: %s", name, e)
            traceback.print_exc()
            status[name] = f"failed: {e}"
        b.flush(status)
    log.info("wrote %d panels -> %s", len(b.manifest), out)


GALLERY_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>bakeoff</title><style>
body{margin:0;font:14px system-ui;background:#111;color:#ddd}
#bar{position:sticky;top:0;background:#1b1b1b;padding:8px 12px;z-index:9;
     display:flex;gap:8px;flex-wrap:wrap;align-items:center}
#bar button{background:#2a2a2a;color:#ccc;border:1px solid #444;
     border-radius:6px;padding:4px 10px;cursor:pointer}
#bar button.on{background:#3b5bdb;color:#fff}
#grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));
     gap:10px;padding:12px}
.card{background:#1c1c1c;border-radius:8px;overflow:hidden;position:relative}
.card img{width:100%;display:block;cursor:pointer}
.card .cap{padding:6px 8px;color:#aaa;font-size:12px}
.card .star{position:absolute;top:6px;right:6px;font-size:20px;
     cursor:pointer;filter:grayscale(1);opacity:.6}
.card .star.on{filter:none;opacity:1}
#lb{position:fixed;inset:0;background:#000d;display:none;z-index:20;
    align-items:center;justify-content:center;flex-direction:column}
#lb img{max-width:96vw;max-height:86vh;object-fit:contain}
#lb .cap{color:#fff;padding:8px}
#photo{position:fixed;bottom:12px;left:12px;width:180px;border:2px solid
    #555;border-radius:6px;z-index:8;cursor:pointer}
</style></head><body>
<div id="bar"><b>bakeoff</b><span id="tabs"></span>
<button id="staronly">★ starred only</button>
<button id="export">Export starred</button><span id="count"></span></div>
<div id="grid"></div>
<img id="photo" title="source photo">
<div id="lb"><img><div class="cap"></div></div>
<script>
let data=null,fam="all",staronly=false,cur=-1;
const stars=new Set(JSON.parse(localStorage.getItem("stars")||"[]"));
function save(){localStorage.setItem("stars",JSON.stringify([...stars]))}
function visible(){return data.panels.filter(p=>(fam==="all"||p.family===fam)
  &&(!staronly||stars.has(p.id)))}
function render(){
  const g=document.getElementById("grid");g.innerHTML="";
  const v=visible();
  document.getElementById("count").textContent=
    ` ${v.length} panels · ${stars.size} starred`;
  v.forEach((p,i)=>{const c=document.createElement("div");c.className="card";
    c.innerHTML=`<img loading="lazy" src="${p.img}">
      <div class="star${stars.has(p.id)?" on":""}">★</div>
      <div class="cap">[${p.family}] ${p.title}</div>`;
    c.querySelector("img").onclick=()=>open(i);
    c.querySelector(".star").onclick=e=>{tog(p.id);
      e.target.classList.toggle("on")};
    g.appendChild(c)});
  const t=document.getElementById("tabs");t.innerHTML="";
  ["all",...new Set(data.panels.map(p=>p.family))].forEach(f=>{
    const b=document.createElement("button");
    b.textContent=f+(data.status&&data.status[f]==="running"?" ⏳":"");
    b.className=f===fam?"on":"";
    b.onclick=()=>{fam=f;render()};t.appendChild(b)})}
function tog(id){stars.has(id)?stars.delete(id):stars.add(id);save()}
function open(i){cur=i;const v=visible();if(!v[i])return;
  const lb=document.getElementById("lb");lb.style.display="flex";
  lb.querySelector("img").src=v[i].img;
  lb.querySelector(".cap").textContent=
   `[${v[i].family}] ${v[i].title} — ${JSON.stringify(v[i].params)}`+
   (stars.has(v[i].id)?" ★":"")}
document.getElementById("lb").onclick=()=>{
  document.getElementById("lb").style.display="none";cur=-1};
document.addEventListener("keydown",e=>{const v=visible();
  if(cur>=0){if(e.key==="ArrowRight")open(Math.min(cur+1,v.length-1));
    if(e.key==="ArrowLeft")open(Math.max(cur-1,0));
    if(e.key==="s"){tog(v[cur].id);open(cur);render()}
    if(e.key==="Escape"){document.getElementById("lb").style.display="none";
      cur=-1}}});
document.getElementById("staronly").onclick=e=>{staronly=!staronly;
  e.target.classList.toggle("on");render()};
document.getElementById("export").onclick=()=>{
  const v=data.panels.filter(p=>stars.has(p.id));
  navigator.clipboard.writeText(JSON.stringify(v,null,1));
  alert("copied "+v.length+" starred panel specs")};
async function poll(){
  try{const r=await fetch("manifest.json?"+Date.now());data=await r.json();
    document.getElementById("photo").src=data.photo;render();
  }catch(e){}
  const running=data&&data.status&&
    Object.values(data.status).some(s=>s==="running");
  setTimeout(poll,running?6000:30000)}
poll();
</script></body></html>
"""

if __name__ == "__main__":
    main()
