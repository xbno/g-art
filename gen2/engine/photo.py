"""Photo source: image file -> structure_ctx.

structure_ctx = {
    "gray":        HxW float32 0..1 tone image (post contrast/blur/gamma)
    "tone_bands":  list of HxW bool masks, band 0 = lightest
    "edge_map":    HxW bool
    "orientation": HxW float32 radians, direction ALONG structure
                   (smoothed in doubled-angle space)
    "coherence":   HxW float32 0..1, anisotropy of the structure tensor
    "page":        Page mapping working pixels -> mm
}

Renderer modules consume this dict and never see the photo itself.
"""

import cv2
import numpy as np

from .page import Page

DEFAULTS = {
    "work_px_per_mm": 4.0,     # working resolution relative to drawable area
    "clahe_clip": 2.0,
    "blur_mm": 0.8,            # pre-band blur, in page mm
    "gamma": 1.0,
    "n_bands": 5,
    "band_gamma": 1.0,         # >1 pushes thresholds darker (more paper)
    "tensor_window_mm": 2.5,
    "canny_lo": 60,
    "canny_hi": 160,
    # region coherence: how tone-band masks consolidate into drawable
    # shapes. On busy/textured photos raise close_mm and min_area_mm2 so
    # speckle merges into a few large masses (what a human artist draws).
    "region": {"close_mm": 0.0,      # merge islands closer than this
               "open_mm": 0.5,       # then erase specks thinner than this
               "min_area_mm2": 4.0,  # drop surviving islands smaller
               "simplify_mm": 0.3},  # boundary smoothing
}


def load_structure_ctx(path: str, page_size: str = "letter",
                       margin_mm: float = 15.0,
                       params: dict | None = None) -> dict:
    p = {**DEFAULTS, **(params or {})}
    p["region"] = {**DEFAULTS["region"], **(p.get("region") or {})}
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(path)
    bgr = cv2.imread(path, cv2.IMREAD_COLOR)  # for hsv only; the tonal
    # pipeline stays on the grayscale read so goldens are untouched

    # pick portrait/landscape page to match the image
    if "landscape" not in page_size and img.shape[1] > img.shape[0]:
        alt = f"{page_size}-landscape"
        from .page import PAGE_SIZES_MM
        if alt in PAGE_SIZES_MM:
            page_size = alt

    # working resolution: drawable area at work_px_per_mm
    probe = Page.fit_image(page_size, margin_mm, img.shape[1], img.shape[0])
    scale = p["work_px_per_mm"] * probe.mm_per_px
    img = cv2.resize(img, None, fx=scale, fy=scale,
                     interpolation=cv2.INTER_AREA)
    h, w = img.shape
    page = Page.fit_image(page_size, margin_mm, w, h)
    bgr = cv2.resize(bgr, (w, h), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv *= np.array([2.0, 1 / 255.0, 1 / 255.0], np.float32)  # H deg 0-360,
    # S and V 0-1 — the scale zone selectors are written against

    def mm_px(mm: float) -> int:
        return max(int(round(mm / page.mm_per_px)), 1)

    if p["clahe_clip"] > 0:
        clahe = cv2.createCLAHE(clipLimit=p["clahe_clip"],
                                tileGridSize=(8, 8))
        img = clahe.apply(img)
    g = img.astype(np.float32) / 255.0
    k = mm_px(p["blur_mm"]) * 2 + 1
    g = cv2.GaussianBlur(g, (k, k), 0)
    if p["gamma"] != 1.0:
        g = np.power(g, p["gamma"])

    # tone bands: thresholds warped by band_gamma. Absolute by default;
    # band_anchor "quantile" derives them from the image's own histogram —
    # essential for high-key sources (pale engravings) or low-key ones,
    # where absolute thresholds dump everything into one band.
    n = p["n_bands"]
    edges = np.linspace(0.0, 1.0, n + 1) ** p["band_gamma"]
    if p.get("band_anchor") == "quantile":
        edges = np.quantile(g, edges)
    idx = np.clip(np.digitize(g, edges[1:-1]), 0, n - 1)
    # band index 0 must be the LIGHTEST -> invert (high luminance = band 0)
    band_idx = (n - 1) - idx
    tone_bands = [(band_idx == i) for i in range(n)]

    # structure tensor orientation, smoothed in doubled-angle space
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    win = mm_px(p["tensor_window_mm"]) * 2 + 1
    jxx = cv2.GaussianBlur(gx * gx, (win, win), 0)
    jxy = cv2.GaussianBlur(gx * gy, (win, win), 0)
    jyy = cv2.GaussianBlur(gy * gy, (win, win), 0)
    # gradient direction = 0.5*atan2(2Jxy, Jxx-Jyy); structure runs 90° to it
    theta = 0.5 * np.arctan2(2 * jxy, jxx - jyy) + np.pi / 2
    lam = np.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2)
    coherence = lam / (jxx + jyy + 1e-8)

    edge_map = cv2.Canny((g * 255).astype(np.uint8),
                         p["canny_lo"], p["canny_hi"]) > 0

    return {"gray": g, "tone_bands": tone_bands, "edge_map": edge_map,
            "orientation": theta.astype(np.float32),
            "coherence": coherence.astype(np.float32), "page": page,
            "hsv": hsv, "region_params": p["region"]}


def region_to_mask(region, page: Page, shape: tuple[int, int]) -> np.ndarray:
    """Rasterize a shapely region (mm) back to a working-px bool mask, so
    modules see a mask that agrees exactly with the clip polygon."""
    m = np.zeros(shape, dtype=np.uint8)
    geoms = getattr(region, "geoms", [region])
    for poly in geoms:
        if poly.is_empty:
            continue
        ext = np.round(page.mm_to_px(np.asarray(poly.exterior.coords))
                       ).astype(np.int32)
        cv2.fillPoly(m, [ext], 1)
        for ring in poly.interiors:
            hole = np.round(page.mm_to_px(np.asarray(ring.coords))
                            ).astype(np.int32)
            cv2.fillPoly(m, [hole], 0)
    return m.astype(bool)


def mask_to_region(mask: np.ndarray, page: Page,
                   simplify_mm: float = 0.3,
                   min_area_mm2: float = 4.0,
                   open_mm: float = 0.5,
                   close_mm: float = 0.0):
    """Bool mask (working px) -> shapely MultiPolygon in page mm."""
    import shapely
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    m = mask.astype(np.uint8)
    if close_mm > 0:  # merge nearby islands into masses BEFORE despeckling
        kc = max(int(round(close_mm / page.mm_per_px)), 1)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((kc, kc), np.uint8))
    k = max(int(round(open_mm / page.mm_per_px)), 1)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN,
                         np.ones((k, k), np.uint8))
    contours, hierarchy = cv2.findContours(m, cv2.RETR_CCOMP,
                                           cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return shapely.MultiPolygon()
    hierarchy = hierarchy[0]
    polys = []
    for i, c in enumerate(contours):
        if hierarchy[i][3] != -1 or len(c) < 3:  # holes handled below
            continue
        shell = page.px_to_mm(c[:, 0, :].astype(np.float64))
        holes = []
        j = hierarchy[i][2]  # first child
        while j != -1:
            if len(contours[j]) >= 3:
                holes.append(page.px_to_mm(
                    contours[j][:, 0, :].astype(np.float64)))
            j = hierarchy[j][0]
        poly = Polygon(shell, holes)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.area >= min_area_mm2:
            polys.append(poly)
    if not polys:
        return shapely.MultiPolygon()
    region = unary_union(polys)
    return region.simplify(simplify_mm)
