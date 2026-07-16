"""Model inference for decomposition. Heavy imports stay inside functions
so `import decompose` is cheap and the CLI can print help without torch."""

import logging

import numpy as np

log = logging.getLogger(__name__)

SAM_MODEL = "facebook/sam-vit-large"  # vit-base under-segments landscapes
DEPTH_MODEL = "depth-anything/Depth-Anything-V2-Small-hf"
NORMALS_MODEL = "prs-eth/marigold-normals-lcm-v0-1"


def run_depth(img) -> np.ndarray:
    """PIL RGB -> HxW float32 in 0..1, higher = nearer to camera."""
    import torch
    from transformers import pipeline

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    pipe = pipeline("depth-estimation", model=DEPTH_MODEL, device=device)
    pred = pipe(img)["predicted_depth"]
    d = torch.nn.functional.interpolate(
        pred[None, None].float(), size=(img.height, img.width),
        mode="bilinear", align_corners=False)[0, 0].cpu().numpy()
    d -= d.min()
    d /= d.max() + 1e-9
    return d.astype(np.float32)


SEMANTIC_MODEL = "facebook/mask2former-swin-large-ade-semantic"


def run_semantic(img):
    """PIL RGB -> (HxW int16 ADE20K labels, {id: name}). Frozen so the
    engine-side plan compiler can consult sky/tree/water masks purely."""
    import torch
    from transformers import (AutoImageProcessor,
                              Mask2FormerForUniversalSegmentation)
    proc = AutoImageProcessor.from_pretrained(SEMANTIC_MODEL)
    model = Mask2FormerForUniversalSegmentation.from_pretrained(
        SEMANTIC_MODEL)
    with torch.no_grad():
        out = model(**proc(images=img, return_tensors="pt"))
    seg = proc.post_process_semantic_segmentation(
        out, target_sizes=[(img.height, img.width)])[0].numpy()
    return seg.astype(np.int16), {int(k): v for k, v
                                  in model.config.id2label.items()}


def run_normals(img) -> np.ndarray:
    """PIL RGB -> HxWx3 float32 surface normals in [-1, 1] (Marigold).
    The single richest artifact for the engine: stroke direction (fall
    line), coherence, texture variance, face clustering, and relightable
    tone all derive from it."""
    import torch
    from diffusers import MarigoldNormalsPipeline

    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    pipe = MarigoldNormalsPipeline.from_pretrained(
        NORMALS_MODEL, torch_dtype=torch.float32).to(dev)
    out = pipe(img, num_inference_steps=4, ensemble_size=1)
    n = np.asarray(out.prediction[0], dtype=np.float32)
    if n.shape[:2] != (img.height, img.width):
        import cv2
        n = cv2.resize(n, (img.width, img.height),
                       interpolation=cv2.INTER_LINEAR)
    return n


def run_sam_masks(img, points_per_crop: int = 32,
                  pred_iou_thresh: float = 0.88,
                  model: str | None = None) -> list[np.ndarray]:
    """PIL RGB -> list of HxW bool masks (unordered, overlapping)."""
    from transformers import pipeline

    # SAM's mask-generation pipeline trips over float64 on MPS; CPU is
    # fast enough for a one-shot offline pass
    pipe = pipeline("mask-generation", model=model or SAM_MODEL,
                    device="cpu")
    kwargs = {"points_per_batch": 64, "pred_iou_thresh": pred_iou_thresh}
    try:
        out = pipe(img, points_per_crop=points_per_crop, **kwargs)
    except TypeError:  # older pipelines lack points_per_crop
        out = pipe(img, **kwargs)
    masks = [np.asarray(m).astype(bool) for m in out["masks"]]
    log.info("sam: %d raw masks", len(masks))
    return masks
